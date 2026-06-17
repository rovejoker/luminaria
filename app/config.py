"""Application configuration — single source of truth for all settings."""
import os

# --- Paths ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "luminaria.db")

# --- Model ---
# stable-audio-3 库支持两种方式指定模型：
#   - "medium" → 自动映射到 stabilityai/stable-audio-3-medium
#   - "stabilityai/stable-audio-3-medium" → 显式指定 HF repo ID
# hf-mirror.com 不会绕过 gated model 的权限验证，需 HF_TOKEN
MODEL_ID = "stabilityai/stable-audio-3-medium"
HF_TOKEN = os.getenv("HF_TOKEN", "")
SAMPLE_RATE = 44100
USE_FLOAT16 = True

# --- Generation ---
MAX_DURATION_SECONDS = 120
MIN_DURATION_SECONDS = 15
DURATION_STEP = 5
DURATION_OPTIONS = [30, 60, 90, 120]  # displayed as 30s, 1min, 1min30s, 2min
GENERATION_TIMEOUT_SECONDS = 180

# --- DeepSeek ---
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_TIMEOUT_SECONDS = 30

# --- Server ---
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# --- Ensure directories exist ---
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
