import os

# Hardware constraints
MAX_RAM_USAGE_MB = 4000  # 4GB limit
TARGET_LATENCY_SEC = 7   # Max 7 seconds latency

# Model configurations
WHISPER_MODEL_SIZE = "small"  # Options: tiny, base, small (avoid medium/large for CPU)
LLM_MODEL_NAME = "qwen2.5:7b"  # Qwen model now available!
USE_CLOUD_LLM = False  # Set to True for cloud Qwen API

# Audio settings
AUDIO_CHUNK_DURATION = 3.0  # seconds
SAMPLE_RATE = 16000
VOLUME_THRESHOLD = 0.01  # Amplitude threshold for VAD

# Ollama settings
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_TIMEOUT = 30  # seconds

# Groq settings (fallback)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama3-8b-8192"

# System prompt for interview context
SYSTEM_PROMPT = """You are a senior developer interviewing candidates. 
Provide concise, bullet-point answers suitable for technical interviews.
Focus on practical knowledge and real-world applications.
Answer in Russian since the interview is conducted in Russian."""

# Question detection keywords (Russian)
QUESTION_KEYWORDS = [
    "почему", "зачем", "как", "что", "чем", "когда", "где", "объясните",
    "расскажите", "опишите", "в чём", "в чем", "разница", "отличие"
]