"""Async task queue with SSE broadcaster — TaskQueue + SSEBroadcaster."""
import asyncio
import json
import logging
import os
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
        self._pending: list[QueuedTask] = []
        self._tasks: dict[str, QueuedTask] = {}
        self._active: QueuedTask | None = None
        self._queue_event = asyncio.Event()
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
            if self._pending:
                self._queue_event.set()

    async def _execute_task(self, task: QueuedTask):
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
