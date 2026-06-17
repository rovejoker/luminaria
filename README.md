# LuminAria — AI 音乐生成平台

基于 Stable Audio 3 Medium 的 AI 音乐生成工具，支持自然语言描述生成纯音乐。

## 技术栈

- **模型**: Stable Audio 3 Medium (stabilityai/stable-audio-3-medium)
- **后端**: FastAPI + Uvicorn
- **前端**: 原生 HTML/CSS/JS（暗夜鎏金风格）
- **提示词增强**: DeepSeek Chat API
- **部署**: Docker + NVIDIA GPU

## 快速开始

### 前置要求

1. Docker Desktop（WSL2 后端）
2. NVIDIA GPU + nvidia-container-toolkit

验证 GPU 可用：
```bash
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### 配置

```bash
cp .env.example .env
# 编辑 .env，填入 DeepSeek API Key（可选，不填则不使用提示词增强）
```

### 启动

```bash
docker compose up -d --build
```

首次启动会从 hf-mirror.com 下载模型（约 3-5GB），后续启动使用缓存卷。

### 使用

浏览器打开 http://localhost:8000

1. 输入音乐描述（中文或英文）
2. 选择时长（30s / 1min / 1min30s / 2min）
3. 点击"生成音乐"
4. 在线播放或下载 MP3

## 项目结构

```
luminaria/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置文件
│   ├── models.py            # Pydantic 数据模型
│   ├── database.py          # SQLite 数据库操作
│   ├── generator.py         # Stable Audio 3 推理封装
│   └── prompt_enhancer.py   # DeepSeek 提示词增强
├── static/                  # 前端文件
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## API 文档

启动后访问 http://localhost:8000/docs 查看 Swagger 文档。

## 许可证

本项目基于 Stable Audio 3 Medium（Stability AI Community License），仅限非商业用途。
