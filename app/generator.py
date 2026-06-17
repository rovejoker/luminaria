"""Stable Audio 3 inference wrapper — singleton model, generate WAV from prompt."""
import os
import logging
import time
import torch
import numpy as np
import soundfile as sf
from pathlib import Path
from einops import rearrange

from app.config import MODEL_ID, HF_TOKEN, SAMPLE_RATE, USE_FLOAT16, OUTPUT_DIR

logger = logging.getLogger(__name__)

# --- Module-level singleton ---
_model = None
_model_config = None


def _load_model() -> None:
    """Load the Stable Audio 3 model once and cache it globally."""
    global _model, _model_config
    if _model is not None:
        return

    logger.info(f"Loading Stable Audio 3 model from {MODEL_ID}...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        logger.warning("CUDA not available — model will run on CPU (very slow, expect 30-60 min)")
    else:
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
        logger.info(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GiB")

    model_half = False
    if device == "cuda":
        model_half = USE_FLOAT16

    if HF_TOKEN and "HF_TOKEN" not in os.environ:
        os.environ["HF_TOKEN"] = HF_TOKEN

    from huggingface_hub import snapshot_download
    cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
    logger.info(f"Model cache directory: {cache_dir}")

    from stable_audio_tools import get_pretrained_model
    _model, _model_config = get_pretrained_model(MODEL_ID)

    _model = _model.to(device)
    if model_half:
        _model = _model.to(torch.float16)
    _model.eval()

    logger.info(f"Model loaded on {device} (float16={model_half})")


def generate_audio(prompt: str, duration_seconds: int) -> tuple[str, int]:
    """Generate audio from a prompt and save as WAV.

    Args:
        prompt: English professional music prompt
        duration_seconds: Desired duration (30-120 seconds)

    Returns:
        (output_path, actual_duration_seconds) — path to the saved WAV file

    Raises:
        RuntimeError: If generation fails or times out
    """
    global _model, _model_config
    if _model is None:
        _load_model()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    actual_device = next(_model.parameters()).device.type
    logger.info(f"Model device: {actual_device}, inference device: {device}")

    if actual_device != device:
        logger.warning(f"Model on {actual_device} but inference requested {device} — mismatched")

    if device != "cuda":
        logger.warning(
            "Running on CPU! This will be extremely slow. "
            "Check: (1) torch.cuda.is_available(), (2) Docker --gpus, (3) container runtime"
        )
    sample_rate = _model_config.get("sample_rate", SAMPLE_RATE)
    sample_size = _model_config["sample_size"]

    start_time = time.time()
    logger.info(f"Generating {duration_seconds}s audio for prompt: {prompt[:100]}...")

    try:
        from stable_audio_tools.inference.generation import generate_diffusion_cond_inpaint

        conditioning = [{
            "prompt": prompt,
            "seconds_total": duration_seconds,
        }]

        # Move model to device explicitly
        model = _model
        if next(model.parameters()).device.type != device:
            model = model.to(device)

        with torch.no_grad():
            output = generate_diffusion_cond_inpaint(
                model,
                steps=15,
                cfg_scale=3.0,
                conditioning=conditioning,
                sample_size=sample_size,
                sampler_type="pingpong",
                device=device,
            )

        logger.info("Diffusion complete, processing output...")

        # Rearrange audio batch to a single sequence
        output = rearrange(output, "b d n -> d (b n)")

        # Move to CPU early to free GPU memory
        output = output.cpu()

        # Peak normalize, clip, convert to int16
        output = (
            output.to(torch.float32)
            .div(torch.max(torch.abs(output)))
            .clamp(-1, 1)
            .mul(32767)
            .to(torch.int16)
        )

        # Generate output filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"luminaria_{timestamp}.wav"
        output_path = str(Path(OUTPUT_DIR) / filename)

        # Save WAV
        sf.write(output_path, output.numpy().T, sample_rate)

        elapsed = time.time() - start_time
        actual_duration = output.shape[-1] / sample_rate
        logger.info(f"Generated {actual_duration:.1f}s audio in {elapsed:.1f}s → {filename}")

        # Free GPU memory after generation
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return output_path, int(actual_duration)

    except Exception as e:
        logger.exception("Audio generation failed")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        raise RuntimeError(f"Audio generation failed: {e}") from e


def wav_to_mp3(wav_path: str) -> str:
    """Convert WAV to MP3 using ffmpeg. Returns the MP3 path."""
    import subprocess
    mp3_path = wav_path.replace(".wav", ".mp3")
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path, "-b:a", "192k", "-f", "mp3", mp3_path],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        logger.error(f"ffmpeg conversion failed: {result.stderr}")
        raise RuntimeError(f"MP3 conversion failed: {result.stderr}")
    # Remove the WAV to save space
    Path(wav_path).unlink(missing_ok=True)
    return mp3_path
