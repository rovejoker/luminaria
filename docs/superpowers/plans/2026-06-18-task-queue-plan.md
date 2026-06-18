# Task Queue & Cancel 功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 LuminAria 添加内存任务队列和任务取消功能

**Architecture:** 新建 `app/queue.py` 提供 `TaskQueue`（`asyncio.Queue` + 后台 worker）+ `SSEBroadcaster`（发布/订阅），替换 `main.py` 中的 `asyncio.Lock()`。前端改为三栏布局，通过全局 SSE `/api/events` 订阅队列状态。

**Tech Stack:** Python 3.11+ asyncio, FastAPI, SSE, JavaScript EventSource

---

### Task 1: 新建 `app/models.py` — 添加 TaskInfo 等模型

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: 在尾部追加 TaskStatus 枚举和 TaskInfo 模型**

```python
import enum


class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    ENHANCING = "enhancing"
    GENERATING = "generating"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo(BaseModel):
    """Task in the generation queue."""
    task_id: str
    status: TaskStatus
    user_input: str
    duration: int
    progress: int = 0          # 0-100
    message: str = ""
    position: int = 0          # 0 = active, 1+ = queue position
    created_at: str = ""
    result: GenerateResponse | None = None
    error: str | None = None
```

- [ ] **Step 2: 验证导入无错误**

Run: `python -c "from app.models import TaskStatus, TaskInfo; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/models.py
git commit -m "feat: add TaskStatus and TaskInfo models"
```

---

### Task 2: 新建 `app/queue.py` — 任务队列 + SSE 广播器

**Files:**
- Create: `app/queue.py`

- [ ] **Step 1: 写入完整 queue.py**

```python
"""Async task queue with SSE broadcaster — TaskQueue + SSEBroadcaster."""
import asyncio
import json
import logging
import os
import time
import threading
import uuid
from datetime import datetime
from pathlib import Path

from app.config import GENERATION_TIMEOUT_SECONDS
from app.models import TaskStatus

logger = logging.getLogger(__name__)


class SSEBroadcaster:
    """Simple pub/sub — one asyncio.Queue per subscriber."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=128)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def broadcast(self, event: str, data: dict):
        payload = json.dumps(data, ensure_ascii=False)
        dead: list[asyncio.Queue] = []
        for q in self._subscribers:
            try:
                q.put_nowait({"event": event, "data": payload})
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._subscribers.remove(q)


class QueuedTask:
    """Internal task with cancel event and state."""
    def __init__(self, task_id: str, user_input: str, duration: int):
        self.task_id = task_id
        self.user_input = user_input
        self.duration = duration
        self.status = TaskStatus.QUEUED
        self.progress = 0
        self.message = "排队中"
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cancel_event = threading.Event()
        self.result: dict | None = None
        self.error: str | None = None

    def to_dict(self, position: int) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "user_input": self.user_input,
            "duration": self.duration,
            "progress": self.progress,
            "message": self.message,
            "position": position,
            "created_at": self.created_at,
            "result": self.result,
            "error": self.error,
        }


class TaskQueue:
    """Ordered task queue with a single background worker.

    Features:
    - One-at-a-time GPU execution (prevents OOM)
    - Per-task cancel via threading.Event
    - SSE broadcast on every state change
    - Auto-cleanup of files on cancel
    """

    def __init__(self, broadcaster: SSEBroadcaster, max_queued: int = 20):
        self._broadcaster = broadcaster
        self._max_queued = max_queued
        self._pending: list[QueuedTask] = []     # ordered, not yet started
        self._tasks: dict[str, QueuedTask] = {}  # all tasks (for lookup)
        self._active: QueuedTask | None = None
        self._queue_event = asyncio.Event()      # signals worker
        self._worker: asyncio.Task | None = None

    async def start(self):
        self._worker = asyncio.create_task(self._run_worker())

    async def stop(self):
        if self._worker:
            self._worker.cancel()

    async def enqueue(self, user_input: str, duration: int) -> str:
        if len(self._pending) >= self._max_queued:
            raise RuntimeError("队列已满（最多 20 个排队任务）")
        task_id = uuid.uuid4().hex[:12]
        task = QueuedTask(task_id, user_input, duration)
        self._pending.append(task)
        self._tasks[task_id] = task
        self._queue_event.set()
        await self._broadcast()
        return task_id

    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if not task:
            return False
        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
            return False
        task.cancel_event.set()
        if task in self._pending:
            self._pending.remove(task)
            task.status = TaskStatus.CANCELLED
            task.message = "已取消"
            await self._broadcast()
        # Active tasks: worker will check cancel_event and clean up
        return True

    def get_snapshot(self) -> list[dict]:
        """Return ordered list: active (position=0), then queued (1+)."""
        items: list[dict] = []
        if self._active and self._active.status not in (
            TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED
        ):
            items.append(self._active.to_dict(0))
        for i, t in enumerate(self._pending, start=1):
            items.append(t.to_dict(i))
        return items

    async def _broadcast(self):
        await self._broadcaster.broadcast("queue_update", {"queue": self.get_snapshot()})

    async def _run_worker(self):
        while True:
            await self._queue_event.wait()
            self._queue_event.clear()
            if not self._pending:
                continue
            task = self._pending.pop(0)
            self._active = task
            await self._broadcast()
            try:
                await self._execute_task(task)
            except Exception as e:
                logger.exception(f"Task {task.task_id} worker error")
                task.status = TaskStatus.FAILED
                task.error = f"内部错误: {e}"
                await self._broadcast()
            self._active = None
            # If more tasks pending, wake up
            if self._pending:
                self._queue_event.set()

    async def _execute_task(self, task: QueuedTask):
        # Lazy imports to avoid circular deps at module level
        from app.prompt_enhancer import enhance_prompt
        from app.generator import generate_audio, wav_to_mp3
        from app.database import insert_generation

        # --- Stage 1: Enhance prompt ---
        if task.cancel_event.is_set():
            await self._finalize_cancelled(task)
            return
        task.status = TaskStatus.ENHANCING
        task.progress = 10
        task.message = "正在优化提示词..."
        await self._broadcast()

        try:
            enhanced_prompt, was_enhanced = await asyncio.wait_for(
                enhance_prompt(task.user_input), timeout=30
            )
        except Exception:
            enhanced_prompt, was_enhanced = task.user_input, False

        if task.cancel_event.is_set():
            await self._finalize_cancelled(task)
            return

        # --- Stage 2: Generate audio ---
        task.status = TaskStatus.GENERATING
        task.progress = 40
        task.message = "正在生成音乐..."
        await self._broadcast()

        wav_path = None
        try:
            wav_path, actual_duration = await asyncio.wait_for(
                asyncio.to_thread(generate_audio, enhanced_prompt, task.duration),
                timeout=GENERATION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"生成超时（{GENERATION_TIMEOUT_SECONDS}s）"
            await self._broadcast()
            return
        except RuntimeError as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            await self._broadcast()
            return

        if task.cancel_event.is_set():
            if wav_path and os.path.exists(wav_path):
                Path(wav_path).unlink(missing_ok=True)
            await self._finalize_cancelled(task)
            return

        # --- Stage 3: Convert to MP3 ---
        task.status = TaskStatus.CONVERTING
        task.progress = 80
        task.message = "正在转换音频格式..."
        await self._broadcast()

        if task.cancel_event.is_set():
            if wav_path and os.path.exists(wav_path):
                Path(wav_path).unlink(missing_ok=True)
            await self._finalize_cancelled(task)
            return

        try:
            mp3_path = await asyncio.to_thread(wav_to_mp3, wav_path)
        except RuntimeError as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            await self._broadcast()
            return

        if task.cancel_event.is_set():
            if mp3_path and os.path.exists(mp3_path):
                Path(mp3_path).unlink(missing_ok=True)
            await self._finalize_cancelled(task)
            return

        # --- Stage 4: Save to DB ---
        filename = os.path.basename(mp3_path)
        row_id = insert_generation(
            user_input=task.user_input,
            prompt_enhanced=enhanced_prompt if was_enhanced else None,
            duration=task.duration,
            filename=filename,
            enhanced=was_enhanced,
        )

        # --- Complete ---
        task.status = TaskStatus.COMPLETED
        task.progress = 100
        task.message = "生成完成"
        task.result = {
            "id": row_id,
            "user_input": task.user_input,
            "prompt_enhanced": enhanced_prompt if was_enhanced else None,
            "duration": task.duration,
            "filename": filename,
            "enhanced": was_enhanced,
            "created_at": task.created_at,
        }
        await self._broadcast()

    async def _finalize_cancelled(self, task: QueuedTask):
        task.status = TaskStatus.CANCELLED
        task.message = "已取消"
        task.progress = 0
        await self._broadcast()
```

- [ ] **Step 2: 验证导入**

Run: `python -c "from app.queue import TaskQueue, SSEBroadcaster; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add app/queue.py
git commit -m "feat: add TaskQueue and SSEBroadcaster"
```

---

### Task 3: 修改 `app/main.py` — 替换锁为队列

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: 修改文件头部的导入和全局变量**

替换：
```python
# --- Concurrency lock: only one generation at a time ---
_gen_lock = asyncio.Lock()
```

为：
```python
from app.queue import TaskQueue, SSEBroadcaster

# --- Task queue with SSE broadcast ---
_broadcaster = SSEBroadcaster()
_task_queue = TaskQueue(_broadcaster)
```

替换 `lifespan` 中启动/停止逻辑：

替换：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, create directories."""
    init_db()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info("LuminAria server started")
    yield
```

为：
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, start task queue worker."""
    init_db()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    await _task_queue.start()
    logger.info("LuminAria server started")
    yield
    await _task_queue.stop()
    logger.info("LuminAria server stopped")
```

- [ ] **Step 2: 替换 `/api/generate` 端点**

将整个 `@app.post("/api/generate")` 替换为：
```python
@app.post("/api/generate")
async def generate(request: GenerateRequest):
    """Submit a generation request. Returns task_id immediately."""
    try:
        task_id = await _task_queue.enqueue(request.user_input, request.duration)
        return {"task_id": task_id, "status": "queued"}
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))
```

- [ ] **Step 3: 添加 `/api/events` SSE 推送端点和 `/api/tasks/{task_id}/cancel` 取消端点**

在 `generate` 端点之后、历史记录端点之前添加：
```python
# --- SSE events stream for queue updates ---
@app.get("/api/events")
async def event_stream(request: Request):
    """Global SSE stream — broadcasts queue state to all clients."""
    queue = _broadcaster.subscribe()

    async def generate():
        try:
            # Send initial snapshot immediately
            snapshot = _task_queue.get_snapshot()
            yield {"event": "queue_update", "data": json.dumps({"queue": snapshot}, ensure_ascii=False)}

            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            _broadcaster.unsubscribe(queue)

    return EventSourceResponse(generate(), ping=15)


# --- Cancel a task ---
@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a queued or in-progress task."""
    ok = await _task_queue.cancel(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found or already finished")
    return {"detail": "Cancelled"}


# --- Get queue snapshot ---
@app.get("/api/tasks")
async def list_tasks():
    """Return current queue snapshot."""
    return {"queue": _task_queue.get_snapshot()}
```

- [ ] **Step 4: 移除不再使用的旧导入**

检查 `main.py` 中是否还用了 `asyncio.Lock`、`GenerateResponse` 等——`GenerateResponse` 在 history endpoints 不再直接使用（不过保留也无妨）。确认 `generate_audio` 和 `wav_to_mp3` 的直接导入可以保留（通过 queue.py 的延迟导入调用，但 main.py 本身不再直接调用它们）。

移除不再需要的导入行：
- ~~`from app.generator import generate_audio, wav_to_mp3`~~ (它们还在 generator.py 中，main.py 不再直接引用)
- 保留 `from app.models import GenerateRequest, ...` 等必要的

```python
# 只移除 generator 相关的直接导入，因为 main.py 不再直接调用它们
```

实际上，可以保留这些导入——Python 不会报错，只是不使用了。但为了整洁可以移除。我会在 plan 中标注。

- [ ] **Step 5: 验证运行**

Run: `python -c "from app.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add app/main.py
git commit -m "feat: replace asyncio.Lock with TaskQueue, add SSE events and cancel endpoint"
```

---

### Task 4: 前端 HTML — 三栏布局 + 队列面板

**Files:**
- Modify: `static/index.html`
- Modify: `static/style.css`

- [ ] **Step 1: 修改 HTML main-content 为三栏布局**

将 `<main class="main-content">` 内部的现有内容改为三栏结构：

```html
<main class="main-content">
    <!-- Left: empty (future: advanced settings) -->
    <aside class="left-panel"></aside>

    <!-- Center: input + status + result -->
    <section class="center-panel">
        <!-- Input section -->
        <section class="input-section">
            <label for="promptInput" class="input-label">描述你想要的音乐...</label>
            <textarea id="promptInput" class="prompt-input" rows="3"
                placeholder="例如：轻柔的钢琴曲，像下雨天的咖啡馆"></textarea>

            <div class="duration-group">
                <div class="duration-row">
                    <span class="duration-label">时 长</span>
                    <input type="range" id="durationSlider" min="15" max="120" step="5" value="90">
                    <span id="durationValue" class="duration-value">90秒</span>
                </div>
                <div class="duration-ticks">
                    <span>15秒</span>
                    <span>30秒</span>
                    <span>60秒</span>
                    <span>90秒</span>
                    <span>120秒</span>
                </div>
                <div class="duration-options" id="durationOptions">
                    <button class="dur-btn" data-duration="30">30秒</button>
                    <button class="dur-btn" data-duration="60">60秒</button>
                    <button class="dur-btn active" data-duration="90">90秒</button>
                    <button class="dur-btn" data-duration="120">120秒</button>
                </div>
            </div>

            <button id="generateBtn" class="btn-generate">生成音乐</button>
        </section>

        <!-- Status area -->
        <section id="statusSection" class="status-section hidden">
            <div id="statusMessage" class="status-message"></div>
            <div class="progress-bar"><div id="progressFill" class="progress-fill"></div></div>
        </section>

        <!-- Result section -->
        <section id="resultSection" class="result-section hidden">
            <!-- Collapsible prompt (same as before) -->
            ...
        </section>
    </section>

    <!-- Right: queue panel -->
    <aside class="right-panel">
        <div class="queue-panel">
            <h3 class="queue-title">♬ 任务队列</h3>
            <div id="queueList" class="queue-list"></div>
        </div>
    </aside>
</main>
```

注意填充 result-section 里的 collapsible prompt 和 record-player，与原来保持一致。

- [ ] **Step 2: 添加 CSS 三栏布局和队列面板样式**

在 `style.css` 中添加：

```css
/* ===== Three-column layout ===== */
.main-content {
  display: grid;
  grid-template-columns: 1fr 2fr 1fr;
  gap: 20px;
  align-items: start;
}

.left-panel {
  /* reserved for future advanced settings */
  min-height: 200px;
}

.center-panel {
  min-width: 0; /* prevent overflow */
}

.right-panel {
  position: sticky;
  top: 20px;
}

/* ===== Queue Panel ===== */
.queue-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}

.queue-title {
  font-family: var(--font-display);
  font-size: 1rem;
  color: var(--gold);
  letter-spacing: 2px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.queue-item {
  background: var(--bg-input);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
  transition: var(--transition);
}
.queue-item.active {
  border-color: var(--gold);
  border-style: double;
}
.queue-item.cancelled {
  opacity: 0.5;
  border-color: var(--danger-border);
}
.queue-item.completed {
  border-color: rgba(201, 168, 76, 0.3);
}

.qi-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 6px;
  gap: 8px;
}

.qi-status-badge {
  font-size: 0.65rem;
  padding: 2px 8px;
  border-radius: 3px;
  white-space: nowrap;
  flex-shrink: 0;
}
.qi-status-badge.queued {
  background: rgba(201, 168, 76, 0.1);
  color: var(--gold-dim);
  border: 1px solid rgba(201, 168, 76, 0.2);
}
.qi-status-badge.generating,
.qi-status-badge.enhancing,
.qi-status-badge.converting {
  background: rgba(201, 168, 76, 0.15);
  color: var(--gold);
  border: 1px solid rgba(201, 168, 76, 0.3);
}
.qi-status-badge.completed {
  background: rgba(76, 168, 100, 0.1);
  color: #6a9a6a;
  border: 1px solid rgba(76, 168, 100, 0.2);
}
.qi-status-badge.failed {
  background: rgba(139, 74, 74, 0.15);
  color: var(--danger);
  border: 1px solid rgba(139, 74, 74, 0.3);
}
.qi-status-badge.cancelled {
  background: rgba(139, 74, 74, 0.1);
  color: #8b6a6a;
  border: 1px solid rgba(139, 74, 74, 0.2);
}

.qi-prompt {
  font-size: 0.8rem;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.qi-progress {
  margin: 6px 0;
  height: 3px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
}
.qi-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--gold-dim), var(--gold-bright));
  border-radius: 2px;
  transition: width 0.3s ease;
}

.qi-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.qi-message {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.qi-cancel-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 2px 10px;
  border-radius: 3px;
  cursor: pointer;
  font-family: var(--font-body);
  font-size: 0.7rem;
  transition: var(--transition);
}
.qi-cancel-btn:hover {
  border-color: var(--danger);
  color: var(--danger);
}
.qi-cancel-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.queue-empty {
  text-align: center;
  color: var(--text-muted);
  font-size: 0.8rem;
  padding: 32px 0;
  font-family: var(--font-body);
}

/* ===== Responsive ===== */
@media (max-width: 960px) {
  .main-content {
    grid-template-columns: 1fr 2fr;
  }
  .left-panel {
    display: none;
  }
}

@media (max-width: 600px) {
  .main-content {
    grid-template-columns: 1fr;
  }
  .right-panel {
    display: none; /* could be toggled via button */
  }
}
```

- [ ] **Step 3: 提交 HTML+CSS 改动**

```bash
git add static/index.html static/style.css
git commit -m "feat: three-column layout with queue panel"
```

---

### Task 5: 前端 JS — SSE 连接 + 队列渲染 + 生成流程改写

**Files:**
- Modify: `static/script.js`

- [ ] **Step 1: 替换 `state` 对象**

替换现有的 `const state = { ... }` 为：

```javascript
const state = {
    duration: 90,
    generating: false,     // true when any task is actively generating
    audioFilename: null,
    promptExpanded: false,
    taskQueue: [],         // current queue snapshot from SSE
    eventSource: null,     // global SSE connection
};
```

- [ ] **Step 2: 替换 generate 按钮点击事件**

将 `generateBtn.addEventListener('click', ...)` 整个替换为：

```javascript
// --- Generate / Add to queue ---
generateBtn.addEventListener('click', async () => {
    const userInput = promptInput.value.trim();
    if (!userInput || state.generating) return;

    try {
        const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_input: userInput, duration: state.duration }),
        });

        if (response.status === 429) {
            const err = await response.json();
            showStatus(err.detail || '队列已满', 0);
            return;
        }
        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: '请求失败' }));
            showStatus(`错误: ${err.detail}`, 0);
            return;
        }

        const data = await response.json();
        console.log(`Task submitted: ${data.task_id}`);

        // Clear input after submission
        promptInput.value = '';
    } catch (err) {
        showStatus(`网络错误: ${err.message}`, 0);
    }
});
```

- [ ] **Step 3: 添加 SSE 连接函数**

在 `generateBtn` 事件后添加：

```javascript
// --- Global SSE connection ---
function connectEventStream() {
    if (state.eventSource) {
        state.eventSource.close();
    }

    const es = new EventSource('/api/events');
    state.eventSource = es;

    es.addEventListener('queue_update', (e) => {
        try {
            const data = JSON.parse(e.data);
            state.taskQueue = data.queue || [];
            renderQueuePanel();
            updateGenerateButton();
            handleCompletedTask();
        } catch (err) {
            console.error('SSE parse error:', err);
        }
    });

    es.onerror = () => {
        es.close();
        state.eventSource = null;
        setTimeout(connectEventStream, 3000);
    };
}
```

- [ ] **Step 4: 添加队列面板渲染函数**

```javascript
// --- Queue panel ---
function renderQueuePanel() {
    const container = document.getElementById('queueList');
    if (!container) return;

    const queue = state.taskQueue;
    if (!queue || queue.length === 0) {
        container.innerHTML = '<div class="queue-empty">暂无排队任务</div>';
        return;
    }

    container.innerHTML = queue.map((item, idx) => {
        const isActive = idx === 0;
        const statusClass = item.status;
        const statusLabels = {
            queued: '排队中',
            enhancing: '优化提示词',
            generating: '生成中',
            converting: '转换中',
            completed: '已完成',
            failed: '失败',
            cancelled: '已取消',
        };
        const label = statusLabels[item.status] || item.status;
        const canCancel = ['queued', 'enhancing', 'generating', 'converting'].includes(item.status);

        return `
            <div class="queue-item ${isActive ? 'active' : ''} ${['cancelled', 'failed'].includes(item.status) ? 'cancelled' : ''} ${item.status === 'completed' ? 'completed' : ''}">
                <div class="qi-header">
                    <span class="qi-prompt" title="${escapeHtml(item.user_input)}">${escapeHtml(item.user_input)}</span>
                    <span class="qi-status-badge ${item.status}">${label}</span>
                </div>
                ${['generating', 'enhancing', 'converting'].includes(item.status) ? `
                    <div class="qi-progress">
                        <div class="qi-progress-fill" style="width:${item.progress}%"></div>
                    </div>
                ` : ''}
                <div class="qi-footer">
                    <span class="qi-message">${isActive ? escapeHtml(item.message) : ''}</span>
                    ${canCancel ? `<button class="qi-cancel-btn" onclick="cancelTask('${item.task_id}')">取消</button>` : ''}
                </div>
            </div>
        `;
    }).join('');
}
```

- [ ] **Step 5: 添加取消和按钮更新函数**

```javascript
async function cancelTask(taskId) {
    try {
        const res = await fetch(`/api/tasks/${taskId}/cancel`, { method: 'POST' });
        if (!res.ok) {
            console.error('Cancel failed');
        }
    } catch (err) {
        console.error('Cancel error:', err);
    }
}

function updateGenerateButton() {
    const queue = state.taskQueue;
    const hasActive = queue.length > 0 && queue[0].status !== 'completed';
    const hasQueue = queue.length > 1 || (queue.length === 1 && queue[0].status !== 'completed');

    if (hasActive) {
        state.generating = true;
        generateBtn.disabled = true;
        generateBtn.textContent = '🎵 生成音乐中...';
        // Show status for active task
        const active = queue[0];
        showStatus(active.message, active.progress);
    } else {
        state.generating = false;
        generateBtn.disabled = false;

        if (queue.length === 0 || (queue.length === 1 && queue[0].status === 'completed')) {
            generateBtn.textContent = '生成音乐';
            hideStatus();
        } else {
            generateBtn.textContent = '添加任务';
            hideStatus();
        }
    }
}

function handleCompletedTask() {
    const queue = state.taskQueue;
    // Check if the first (or any) task just completed
    for (const item of queue) {
        if (item.status === 'completed' && item.result) {
            showResult(
                item.result.prompt_enhanced,
                item.result.filename,
                item.result.enhanced
            );
            // Clear result-based status
            hideStatus();
            break;
        }
    }
}
```

- [ ] **Step 6: 修改 `showResult` 信号绑定防止重复**

`showResult` 中 `audioPlayer.addEventListener('loadedmetadata', ...)` 使用了 `{ once: true }`，确保不会因多次调用而产生多条 listener——当前实现已经是 `once: true`，所以 OK。

- [ ] **Step 7: 在页面加载时启动 SSE 连接**

在文件底部附近（init 位置）添加：
```javascript
// --- Init ---
connectEventStream();
```

- [ ] **Step 8: 移除旧代码**

移除不再使用的：
- `generateBtn` 的旧 click handler（已替换）
- `handleSSEEvent` 函数（不再从 POST 响应中解析 SSE）
- `statusSection` 和 `status-` 相关的逻辑（由 `updateGenerateButton` 替代）
  注意：实际上 `showStatus` / `hideStatus` 还可以用，保留它们。

确认需要移除的：
- `state.generating` 的手动设置（由 SSE 驱动）
- 旧的 `handleSSEEvent` —— 替换为 `renderQueuePanel` + `updateGenerateButton`

等一下——`showStatus` 和 `hideStatus` 仍然有用（用于网络错误、队列满等情况），保留。
`resetGenerateBtn` 仍然有用，保留。

- [ ] **Step 9: 手动测试显示逻辑**

将 `script.js` 中的 `DOMContentLoaded` 或内联脚本确保 `connectEventStream()` 被调用。在 `script.js` 末尾添加。

- [ ] **Step 10: Commit**

```bash
git add static/script.js
git commit -m "feat: SSE event stream, queue panel rendering, task cancel"
```

---

### Verification

```bash
cd "E:\课程文件\网络编程\期末作业"

# 1. Python 导入验证
python -c "
from app.queue import TaskQueue, SSEBroadcaster
from app.models import TaskStatus, TaskInfo
from app.main import app
print('All imports OK')
"

# 2. 启动服务器
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 浏览器测试 (需要等服务器启动后)
# - 打开 http://localhost:8000
# - 验证三栏布局
# - 提交一个生成任务 → 确认右侧队列面板显示任务
# - 提交第二个任务 → 确认显示"排队中"
# - 点击取消 → 确认队列更新
# - 完成的任务显示在播放器中

# 4. API 测试
curl -s http://localhost:8000/api/tasks
curl -s -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{"user_input":"test music","duration":30}'
```
