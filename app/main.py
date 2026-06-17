"""FastAPI application — routes, SSE streaming, concurrency control."""
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

from app.config import OUTPUT_DIR, BASE_DIR, GENERATION_TIMEOUT_SECONDS, PORT, HOST
from app.models import GenerateRequest, GenerateResponse, HistoryItem, HistoryList
from app.database import init_db, insert_generation, get_history, get_generation, delete_generation
from app.prompt_enhancer import enhance_prompt
from app.generator import generate_audio, wav_to_mp3

import torch

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("luminaria")

# --- Concurrency lock: only one generation at a time ---
_gen_lock = asyncio.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, create directories."""
    init_db()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    logger.info("LuminAria server started")
    yield


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


# --- Generate endpoint with SSE ---
@app.post("/api/generate")
async def generate(request: GenerateRequest):
    """Submit a music generation request. Returns SSE stream with progress."""
    if _gen_lock.locked():
        raise HTTPException(status_code=429, detail="Another generation is in progress. Please wait.")

    async def event_stream():
        async with _gen_lock:
            async def push(stage: str, message: str):
                return {"event": "status", "data": f'{{"stage":"{stage}","message":"{message}"}}'}

            # Stage 1: Enhance prompt
            yield await push("enhancing", "正在优化提示词...")
            enhanced_prompt, was_enhanced = await enhance_prompt(request.user_input)

            # Stage 2: Generate audio
            yield await push("generating", "正在生成音乐，预计需要 30-60 秒..." +
                             ("（注意：运行在 CPU 上，可能需要 30-60 分钟）" if not torch.cuda.is_available() else ""))

            try:
                wav_path, actual_duration = await asyncio.wait_for(
                    asyncio.to_thread(generate_audio, enhanced_prompt, request.duration),
                    timeout=GENERATION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                error_data = json.dumps({"stage": "error", "message": f"生成超时（{GENERATION_TIMEOUT_SECONDS}s），模型可能运行在 CPU 上"})
                yield {"event": "error", "data": error_data}
                return
            except RuntimeError as e:
                error_data = json.dumps({"stage": "error", "message": str(e)})
                yield {"event": "error", "data": error_data}
                return

            # Stage 3: Convert to MP3
            yield await push("converting", "正在转换音频格式...")
            try:
                mp3_path = await asyncio.to_thread(wav_to_mp3, wav_path)
            except RuntimeError as e:
                error_data = json.dumps({"stage": "error", "message": str(e)})
                yield {"event": "error", "data": error_data}
                return

            # Stage 4: Save to DB
            filename = os.path.basename(mp3_path)
            row_id = insert_generation(
                user_input=request.user_input,
                prompt_enhanced=enhanced_prompt if was_enhanced else None,
                duration=request.duration,
                filename=filename,
                enhanced=was_enhanced,
            )

            # Stage 5: Complete
            complete_data = json.dumps({
                "id": row_id,
                "user_input": request.user_input,
                "prompt_enhanced": enhanced_prompt if was_enhanced else None,
                "duration": request.duration,
                "filename": filename,
                "enhanced": was_enhanced,
                "created_at": "",  # filled by DB
            })
            yield {"event": "complete", "data": complete_data}

    return EventSourceResponse(event_stream(), ping=15)


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
    from app.database import delete_all_generations

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
