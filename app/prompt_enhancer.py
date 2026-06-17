"""DeepSeek Chat API wrapper — translates natural language to music prompts."""
import logging
import httpx
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a professional music prompt engineer for the Stable Audio 3 model. Convert the user's input into a detailed, coherent English paragraph optimized for Stable Audio 3.

Stable Audio 3 is a diffusion model conditioned on a GLOBAL text prompt — it does NOT understand timeline markers or section labels. Read the prompt as a whole.

INSTRUCTIONS:
1. Extract ALL musical information from the user's input regardless of format
2. Synthesize into a FLOWING NARRATIVE PARAGRAPH describing how the music evolves
3. Use phrasing like "builds from... to...", "transitions into", "opens with... then", "gives way to", "returns to"
4. If the input is brief or vague, CREATIVELY EXPAND it into a detailed description — choose appropriate instruments, key, tempo, BPM, and structure matching the mood/genre. Be specific, not generic.
5. If the input contains abstract, poetic, or imagery-driven descriptions (e.g. nature scenes, emotions, stories, visual imagery) with few or no musical terms, TRANSLATE them into concrete musical parameters — map moods to keys (happy/peaceful → C/E/G major, melancholic → D minor, tense → minor keys), atmospheres to instruments (nature/forest → woodwinds, harp; vast/epic → orchestra, choir, reverb; urban/night → electronic, synth pads), and imagery to dynamics/tempo (gentle → soft, slow; dramatic → loud, building crescendo)
6. Cover: instruments, genre/style, mood/atmosphere, tempo/BPM, timbre/texture, dynamics/evolution
7. Include explicit BPM values when you can infer the genre (e.g. house ~128, trap ~140, ballad ~70, dubstep ~140)
8. Keep output 80-250 words
9. Do NOT use timeline markers, brackets, or section labels
10. Output ONLY the prompt text

EXAMPLES:

User: "来一首很嗨的歌"
Assistant: "Opens with a driving four-on-the-floor kick drum and pulsating synth bass at 128 BPM, layered with energetic sawtooth leads and uplifting arpeggios. Builds through filter sweeps and clap fills into a euphoric drop with reese bass, chopped vocal stabs, and a high-energy beat. Features breakdown sections with atmospheric pads and risers, then returns to a powerful festival-style drop with heavy sidechain compression and layered percussion."

User: "舒缓的钢琴曲"
Assistant: "A gentle solo piano piece in C major, slow tempo around 60 BPM, soft dynamics with delicate touch. The melody unfolds gradually with simple chord progressions and subtle rubato, creating a peaceful and contemplative atmosphere. Warm resonant tone with gentle sustain pedal, evoking a quiet rainy afternoon."

User: "dark ambient with horror elements"
Assistant: "A dark ambient soundscape with deep, rumbling sub-bass drones and eerie granular textures. Sparse, distorted percussion echoes in a cavernous reverb space, with unsettling metallic scrapes and whispered noise layers. Slow, ominous pads shift subtly in pitch, creating a sense of dread and isolation. The piece builds gradually with layers of static and低频 rumble, evoking an abandoned industrial underground space."

User: "upbeat jazz"
Assistant: "A lively jazz ensemble piece in swing feel at around 180 BPM, featuring a bright trumpet melody over walking bass and ride cymbal-driven drums. The piano comps with lively voicings, and the arrangement trades solos between trumpet and tenor saxophone. The energy builds through a trading-fours section into a dynamic shout chorus, then returns to the head melody with a crisp, upbeat finish."

User: "森林中清晨的阳光，薄雾缭绕，鸟鸣声"
Assistant: "Opens with delicate woodwind and harp arpeggios in G major, moderate tempo around 80 BPM, evoking a calm forest dawn. Gentle string pads create a warm, misty atmosphere as a solo flute melody enters, bright and airy. Light pizzicato strings suggest scattered birdsong and dewdrops. The piece subtly expands with soft french horn harmonics and distant chimes, then settles back to a peaceful solo piano coda, rich with sustain pedal resonance."

If the input is already a well-formed English narrative prompt fitting this style (no brackets/timelines), return it as-is."""  # fmt: off


async def enhance_prompt(user_input: str) -> tuple[str, bool]:
    """Enhance user input into a professional music prompt via DeepSeek.

    Returns:
        (enhanced_prompt, was_enhanced) — if enhancement fails, returns (user_input, False).
    """
    # Skip if no API key configured
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY.startswith("sk-your-"):
        logger.warning("DeepSeek API key not configured, using raw input")
        return user_input, False

    # Estimate tokens and adjust temperature based on input richness
    input_length = len(user_input)
    max_tokens = min(1000, max(300, int(input_length * 1.5)))
    temperature = 0.85 if input_length < 80 else 0.7

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
                        {"role": "user", "content": user_input}
                    ],
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            if response.status_code == 200:
                data = response.json()
                enhanced = data["choices"][0]["message"]["content"].strip()
                if enhanced and len(enhanced) >= 10:
                    logger.info(f"Prompt enhanced ({len(enhanced)} chars): {enhanced[:120]}...")
                    return enhanced, True
            else:
                logger.warning(f"DeepSeek API returned {response.status_code}: {response.text[:200]}")
    except httpx.TimeoutException:
        logger.warning("DeepSeek API timeout, using raw input")
    except Exception as e:
        logger.warning(f"DeepSeek API error: {e}")

    return user_input, False
