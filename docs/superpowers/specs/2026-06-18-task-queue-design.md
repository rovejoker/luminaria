# LuminAria 任务队列与取消功能设计

## 概述

为 LuminAria 音乐生成平台添加任务队列和任务取消能力。用户无需等待前一个任务完成即可提交多个生成任务，并可随时取消进行中或排队中的任务。

## 动机

当前系统使用 `asyncio.Lock()` 全局锁，同一时间只能处理一个生成请求，其他请求收到 429。用户必须等待一个任务完全结束后才能提交下一个。缺少取消机制，生成一旦开始只能等待完成或超时。

## 方案：内存任务队列 + 全局 SSE + 取消端点

### 核心架构

```
POST /api/generate ──→ TaskQueue ──→ Worker (单线程) ──→ 完成
                       ↕ 广播
GET  /api/events   ←── SSE Broadcaster (全局)
                       ↕
POST /api/tasks/{id}/cancel
```

- `TaskQueue` 是 `asyncio.Queue` 封装，任务按序排队
- `Worker` 是后台 `asyncio.Task`，一个接一个处理队列中的任务
- `SSE Broadcaster` 是 `asyncio.Event` + 队列的发布/订阅模式，所有客户端共享同一事件流
- `cancel` 设置任务的取消标志，worker 在每阶段前检查

### 取消策略

GPU 扩散推理 (`generate_diffusion_cond_inpaint`) 是 30-60 秒的阻塞调用，无法真正中断。因此取消是**协作式**的：

1. **排队中** → 立即移除，无需等待
2. **提示词优化阶段** → 立即停止
3. **GPU 推理阶段** → 等当前推理跑完但丢弃生成的 WAV 文件，跳过后续步骤
4. **格式转换阶段** → 立即停止，删除临时 WAV 文件

所有取消操作确保不残留临时文件。模型保持加载在 GPU 内存中不释放。

### 后端改动

#### `app/queue.py` (新文件)

```python
class TaskQueue:
    """任务队列管理器——单个 worker 顺序消费"""
    - task_queue: asyncio.Queue       # 待处理任务
    - cancel_events: dict[str, Event] # 任务取消信号
    - active_task_id: str | None      # 当前处理中的任务
    - _worker: asyncio.Task           # 后台 worker
    
    async def enqueue(user_input, duration) → task_id
    async def cancel(task_id) → bool
    async def get_status(task_id) → TaskInfo
    def get_queue_snapshot() → list[TaskInfo]  # 全部队列状态
    async def _run_worker()  # 永久循环：取任务 → 执行 → 广播完成
    async def _execute_task(task)  # 每阶段前检查取消
```

#### `app/main.py` 改动

| 端点 | 改动 |
|------|------|
| `POST /api/generate` | 改为立即返回 `{task_id}`，将任务入队 |
| `GET /api/events` | 新端点，全局 SSE 流推送所有状态变更 |
| `POST /api/tasks/{task_id}/cancel` | 新端点，取消指定任务 |
| `GET /api/tasks` | 新端点，返回队列快照（可选） |
| `POST /api/generate` (旧) | 移除锁逻辑 |

**SSE 事件格式：**

```json
// 队列更新（任何任务状态变化时广播）
{"type": "queue_update", "queue": [TaskInfo, ...]}

// 单个任务丰富事件（可选字段）
{"type": "task_status", "task_id": "...", "status": "processing", "stage": "generating", "progress": 40}

// 任务完成
{"type": "task_complete", "task_id": "...", "result": {完整 GenerateResponse}}

// 任务错误
{"type": "task_error", "task_id": "...", "message": "..."}
```

#### `app/models.py` 新增

```python
class TaskStatus(str, enum):
    QUEUED = "queued"        # 排队中
    ENHANCING = "enhancing"  # 优化提示词
    GENERATING = "generating"  # 生成中
    CONVERTING = "converting"  # 转换中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消

class TaskInfo(BaseModel):
    task_id: str
    status: TaskStatus
    user_input: str
    duration: int
    progress: int           # 0-100
    message: str            # 当前阶段消息
    position: int           # 队列中的位置
    result: GenerateResponse | None  # 完成时有
    error: str | None       # 失败时有
    created_at: str
```

#### `app/generator.py` 改动

- `generate_audio()` 接受可选的 `cancel_event: threading.Event` 参数
- 在推理前后检查取消信号

### 前端布局

```
┌──────────────────────────────────────────────────────────┐
│                     Top Bar                              │
├───────────┬──────────────────────────┬───────────────────┤
│           │                          │   ▼ 任务队列       │
│  (留空)   │  提示词输入              │                   │
│  未来     │  时长选择                │  ● 进行中          │
│  高级     │  [生成音乐/添加任务]      │  "轻柔的钢琴曲..." │
│  设置     │  状态指示                │  45% ■■■□□□        │
│           │  结果 + 播放器           │  [取消]            │
│           │                          │                   │
│           │                          │  ○ 排队中 (2)     │
│           │                          │  "爵士萨克斯..."  │
│           │                          │  [取消]            │
│           │                          │  "电子节拍..."    │
│           │                          │  [取消]            │
└───────────┴──────────────────────────┴───────────────────┘
```

- 使用 `display: grid` 实现三栏布局
- 左侧留空（future: 高级设置面板）
- 中间为现有生成器 + 播放器（保持不变）
- 右侧为队列面板

### 按钮行为

| 状态 | 按钮文字 | 行为 |
|------|----------|------|
| 队列为空 + 有输入 | 生成音乐 | 提交任务 → 入队 → 开始处理 |
| 队列非空 + 有输入 | 添加任务 | 提交任务 → 入队（排到尾部） |
| 生成中 + 无排队（队列唯一任务） | 生成音乐 (disabled) | — |
| 生成中 + 有排队 | 添加任务 | 提交任务 → 入队（排到尾部） |
| 无输入 | disabled | — |

### 队列面板设计（维多利亚风格）

- 标题：`♬ 任务队列`
- 当前任务卡片：金色边框 + 进度条 + 取消按钮
- 排队任务卡片：暗色边框 + 序号 + 取消按钮
- 已完成/已取消任务在队列中保留 5 秒后自动移除
- 空队列显示：暗金色文字 "暂无排队任务"
- 取消按钮鼠标悬停变红色

### 布局适配（响应式）

- 桌面 ≥ 960px：三栏 grid
- 平板 < 960px：两栏（左栏隐藏/可切换）+ 中间 + 右栏
- 手机 < 600px：单栏，队列面板通过顶部按钮切换浮层（类似历史记录）

### 错误处理

- 队列满时（上限 20 个排队任务）拒绝入队
- SSE 连接断开自动重连
- Worker 崩溃自动重启
- 取消已完成/不存在的任务返回 404

### 测试

- 启动应用，测试多任务提交
- 测试取消排队中的任务
- 测试取消生成中的任务（验证文件被清理）
- 测试 SSE 重连
- 验证布局适配

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 新建 | `app/queue.py` |
| 修改 | `app/main.py` |
| 修改 | `app/models.py` |
| 修改 | `app/generator.py` |
| 修改 | `static/index.html` |
| 修改 | `static/style.css` |
| 修改 | `static/script.js` |
