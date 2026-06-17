"""DeepSeek Chat API wrapper — translates natural language to music prompts."""
import logging
import httpx
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional music prompt engineer. Your task is to convert the user's natural language description into a professional music prompt that the Stable Audio 3 model can understand.

Rules:
1. Output in English (the model works much better with English prompts)
2. Include descriptions across these dimensions:
   - Instruments (specific types, e.g. "grand piano", "nylon-string guitar", "string section")
   - Music genre/style (e.g. "ambient", "classical", "jazz ballad", "orchestral")
   - Mood/atmosphere (e.g. "contemplative", "uplifting", "melancholic", "peaceful")
   - Tempo hints (e.g. "slow tempo", "moderate groove", "allegro")
   - Timbre/texture (e.g. "warm tone", "bright", "ethereal", "rich harmonics")
   - Dynamics (e.g. "builds gradually", "soft dynamics", "crescendo")
3. Use comma-separated tag-style phrases, NOT complete sentences
4. Keep output between 50-150 words
5. Do NOT add unrelated instruments or genres
6. If user specifies instrumental/pure music, do NOT include any vocal/voice/lyrics descriptions
7. If user specifies a tempo or BPM, include it verbatim in the output"""


def _is_likely_professional_prompt(text: str) -> bool:
    """Heuristic: if input is already in English with music terms, skip enhancement."""
    music_terms = ["bpm", "tempo", "piano", "orchestral", "ambient", "guitar", "jazz",
                   "classical", "electronic", "drum", "bass", "violin", "synth", "beat",
                   "groove", "melody", "chord", "reverb", "dynamics", "arpeggio"]
    text_lower = text.lower()
    # Count how many music terms appear
    hits = sum(1 for term in music_terms if term in text_lower)
    # If >= 3 music terms AND text is mostly ASCII (English), consider it professional
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    return hits >= 3 and ascii_ratio > 0.7


async def enhance_prompt(user_input: str) -> tuple[str, bool]:
    """Enhance user input into a professional music prompt via DeepSeek.

    Returns:
        (enhanced_prompt, was_enhanced) — if enhancement fails, returns (user_input, False).
    """
    # Skip if already looks like a professional prompt
    if _is_likely_professional_prompt(user_input):
        logger.info("Input already appears to be a professional prompt, skipping enhancement")
        return user_input, False

    # Skip if no API key configured
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("sk-your-"):
        logger.warning("DeepSeek API key not configured, using raw input")
        return user_input, False

    try:
        async with httpx.AsyncClient(timeout=DEEPSEEK_TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Convert this to a music generation prompt: {user_input}"}
                    ],
                    "max_tokens": 200,
                    "temperature": 0.7,
                },
            )
            if response.status_code == 200:
                data = response.json()
                enhanced = data["choices"][0]["message"]["content"].strip()
                # Sanity check: must be non-empty and mostly ASCII
                if enhanced and len(enhanced) >= 10:
                    logger.info(f"Prompt enhanced: {enhanced[:100]}...")
                    return enhanced, True
            else:
                logger.warning(f"DeepSeek API returned {response.status_code}: {response.text[:200]}")
    except httpx.TimeoutException:
        logger.warning("DeepSeek API timeout, using raw input")
    except Exception as e:
        logger.warning(f"DeepSeek API error: {e}")

    # Fallback: return user input as-is
    return user_input, False
