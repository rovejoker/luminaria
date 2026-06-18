"""FastAPI application — routes, SSE streaming, task queue."""
import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from app.config import OUTPUT_DIR, BASE_DIR
from app.models import GenerateRequest, GenerateResponse, HistoryItem, HistoryList
from app.database import init_db, insert_generation, get_history, get_generation, delete_generation, delete_all_generations
from app.prompt_enhancer import enhance_prompt
from app.queue import TaskQueue, SSEBroadcaster

import torch

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("luminaria")

# --- Task queue with SSE broadcast ---
_broadcaster = SSEBroadcaster()
_task_queue = TaskQueue(_broadcaster)


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


app = FastAPI(title="LuminAria", version="1.0.0", lifespan=lifespan)


# --- Static files ---
STATIC_DIR = Path(BASE_DIR) / "static"
STATIC_DIR.mkdir(exist_ok=True)


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the SPA frontend."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>LuminAria</h1><p>Static files not found.</p>", status_code=404)


# Mount /static for CSS/JS, and /output for audio files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


# --- Health check ---
@app.get("/api/health")
async def health():
    gpu_available = torch.cuda.is_available()
    return {
        "status": "ok",
        "gpu": gpu_available,
        "gpu_name": torch.cuda.get_device_name(0) if gpu_available else None,
    }


# --- Generate endpoint — enqueue task, return immediately ---
@app.post("/api/generate")
async def generate(request: GenerateRequest):
    """Submit a generation request. Returns task_id immediately."""
    try:
        task_id = await _task_queue.enqueue(request.user_input, request.duration)
        return {"task_id": task_id, "status": "queued"}
    except RuntimeError as e:
        raise HTTPException(status_code=429, detail=str(e))


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


# --- History endpoints ---
@app.get("/api/history", response_model=HistoryList)
async def list_history():
    """Get all generation history, newest first."""
    items = get_history()
    return HistoryList(items=[
        HistoryItem(
            id=item["id"],
            created_at=item["created_at"],
            user_input=item["user_input"],
            duration=item["duration"],
            filename=item["filename"],
            enhanced=bool(item["enhanced"]),
        )
        for item in items
    ])


@app.get("/api/history/{generation_id}")
async def get_history_item(generation_id: int):
    """Get a single generation by ID."""
    item = get_generation(generation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    return {
        "id": item["id"],
        "created_at": item["created_at"],
        "user_input": item["user_input"],
        "prompt_enhanced": item["prompt_enhanced"],
        "duration": item["duration"],
        "filename": item["filename"],
        "enhanced": bool(item["enhanced"]),
    }


@app.delete("/api/history/{generation_id}")
async def delete_history_item(generation_id: int):
    """Delete a generation and its audio file."""
    item = get_generation(generation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    # Delete audio file
    audio_path = Path(OUTPUT_DIR) / item["filename"]
    if audio_path.exists():
        audio_path.unlink()

    # Delete DB record
    delete_generation(generation_id)
    return {"detail": "Deleted"}


@app.delete("/api/history")
async def delete_all_history():
    """Delete ALL generations and their audio files."""
    filenames = delete_all_generations()
    for fname in filenames:
        audio_path = Path(OUTPUT_DIR) / fname
        if audio_path.exists():
            audio_path.unlink()
    return {"detail": f"Deleted {len(filenames)} records"}


# --- Main entry point ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
