from __future__ import annotations

from typing import Any

from shared.config_loader import get_config

_cfg = get_config()


def _get(path: list[str], default: Any = None) -> Any:
    current: Any = _cfg
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


# Hardware constraints
MAX_RAM_USAGE_MB = _get(["hardware", "max_ram_usage_mb"], 4000)
TARGET_LATENCY_SEC = _get(["hardware", "target_latency_sec"], 7)

# Model configurations
WHISPER_MODEL_SIZE = _get(["stt", "whisper_model_size"], "small")
LLM_MODEL_NAME = _get(["llm", "model_name"], "qwen2.5:7b")
USE_CLOUD_LLM = _get(["llm", "use_cloud"], False)
USE_COTCORE = _get(["llm", "use_cotcore"], False)
USE_BREAKER = _get(["llm", "use_breaker"], False)
BREAKER_THRESHOLD = _get(["llm", "breaker", "failure_threshold"], 3)
BREAKER_COOLDOWN = _get(["llm", "breaker", "cooldown_seconds"], 10)
TEMPORAL_ENABLED = _get(["llm", "temporal_enabled"], True)
AGENT_ENABLED = _get(["agent", "enabled"], False)
AGENT_CANCEL_ON_NEW_INPUT = _get(["agent", "cancel_on_new_input"], True)
AGENT_CANCEL_GRACE_MS = _get(["agent", "cancel_grace_ms"], 0)
AGENT_MEMORY_MAX_CHARS = _get(["agent", "memory_max_chars"], 2000)
AGENT_METRICS_ENABLED = _get(["agent", "metrics_enabled"], True)

# Audio settings
AUDIO_CHUNK_DURATION = _get(["audio", "chunk_duration"], 3.0)
CHUNK_DURATION = AUDIO_CHUNK_DURATION
SAMPLE_RATE = _get(["audio", "sample_rate"], 16000)
VOLUME_THRESHOLD = _get(["audio", "volume_threshold"], 0.01)

# Ollama settings
OLLAMA_HOST = _get(["llm", "ollama", "host"], "http://localhost:11434")
OLLAMA_TIMEOUT = _get(["llm", "ollama", "timeout"], 30)
OLLAMA_MODEL = _get(["llm", "ollama", "model"], "")

# Groq settings (fallback)
GROQ_API_KEY = _get(["llm", "groq", "api_key"], "")
GROQ_MODEL = _get(["llm", "groq", "model"], "")
USE_GROQ = _get(["llm", "use_groq"], False)

# Model generation settings (GhostGPT)
TEMPERATURE = _get(["llm", "temperature"], 0.6)
MAX_TOKENS = _get(["llm", "max_tokens"], 4096)
TOP_P = _get(["llm", "top_p"], 0.9)

# System prompt for interview context
SYSTEM_PROMPT = _get(["llm", "system_prompt"], "")

# Question detection keywords
QUESTION_KEYWORDS = _get(["question_keywords"], [])

# Hotkeys (GhostGPT)
KEY_HIDE = _get(["hotkeys", "hide"], "F9")
KEY_LRI_HR = _get(["hotkeys", "lri_hr"], "F1")
KEY_LRI_DEV = _get(["hotkeys", "lri_dev"], "F2")
KEY_LRI_CTO = _get(["hotkeys", "lri_cto"], "F3")

# Access protocol prompt (GhostGPT)
ACCESS_PROTOCOL_PROMPT = _get(["access_protocol_prompt"], "")
