from __future__ import annotations

import os
from typing import Any

try:
    from shared.config_loader import get_config
except ImportError:
    from .shared.config_loader import get_config

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
LLM_RAM_AWARE = _get(["llm", "ram_aware"], False)
LLM_HEAVY_MODEL = _get(["llm", "heavy_model"], "qwen2.5:7b")
LLM_LIGHT_MODEL = _get(["llm", "light_model"], "qwen2.5:1.5b")
LLM_RAM_THRESHOLD_GB = _get(["llm", "ram_threshold_gb"], 8.0)
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
AGENT_OBSERVABILITY_ENABLED = _get(["agent", "observability_enabled"], True)
AGENT_EVENT_SINK = _get(["agent", "event_sink"], "print")

# Audio settings
AUDIO_CHUNK_DURATION = _get(["audio", "chunk_duration"], 3.0)
CHUNK_DURATION = AUDIO_CHUNK_DURATION
SAMPLE_RATE = _get(["audio", "sample_rate"], 16000)
VOLUME_THRESHOLD = _get(["audio", "volume_threshold"], 0.01)

# Ollama settings
OLLAMA_HOST = _get(["llm", "ollama", "host"], "http://localhost:11434")
OLLAMA_TIMEOUT = _get(["llm", "ollama", "timeout"], 30)
OLLAMA_MODEL = _get(["llm", "ollama", "model"], "")
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", _get(["llm", "ollama", "num_predict"], 220)))
os.environ.setdefault("OLLAMA_NUM_PREDICT", str(OLLAMA_NUM_PREDICT))

# Routed backend settings
LLM_BACKEND = os.getenv("LLM_BACKEND", _get(["llm", "backend"], ""))
LLM_FALLBACK_BACKEND = os.getenv("LLM_FALLBACK_BACKEND", _get(["llm", "fallback_backend"], ""))
LLM_MERITOCRACY_ENABLED = str(os.getenv("LLM_MERITOCRACY_ENABLED", _get(["llm", "meritocracy", "enabled"], False))).strip().lower() in {"1", "true", "yes", "on"}
LLM_MERITOCRACY_BACKENDS = os.getenv("LLM_MERITOCRACY_BACKENDS", _get(["llm", "meritocracy", "backends"], "gonka,mimo,cloud,local"))
LLM_MERITOCRACY_MIN_OVERALL = float(os.getenv("LLM_MERITOCRACY_MIN_OVERALL", _get(["llm", "meritocracy", "min_overall"], 0.35)))
LLM_MERITOCRACY_MIN_RELEVANCE = float(os.getenv("LLM_MERITOCRACY_MIN_RELEVANCE", _get(["llm", "meritocracy", "min_relevance"], 0.25)))
LLM_MERITOCRACY_MIN_THREAD_RELEVANCE = float(os.getenv("LLM_MERITOCRACY_MIN_THREAD_RELEVANCE", _get(["llm", "meritocracy", "min_thread_relevance"], 0.25)))
LLM_MERITOCRACY_MAX_HALLUCINATION_RISK = float(os.getenv("LLM_MERITOCRACY_MAX_HALLUCINATION_RISK", _get(["llm", "meritocracy", "max_hallucination_risk"], 0.65)))

# Groq / generic cloud settings
GROQ_API_KEY = os.getenv("GROQ_API_KEY", _get(["llm", "groq", "api_key"], ""))
GROQ_MODEL = os.getenv("GROQ_MODEL", _get(["llm", "groq", "model"], ""))
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", _get(["llm", "groq", "base_url"], "https://api.groq.com/openai/v1"))
GROQ_TIMEOUT_SEC = float(os.getenv("GROQ_TIMEOUT_SEC", _get(["llm", "groq", "timeout_sec"], 120)))
USE_GROQ = _get(["llm", "use_groq"], False)

# Gonka settings
GONKA_ENABLED = str(os.getenv("GONKA_ENABLED", _get(["llm", "gonka", "enabled"], False))).strip().lower() in {"1", "true", "yes", "on"}
GONKA_API_KEY = os.getenv("GONKA_API_KEY", _get(["llm", "gonka", "api_key"], ""))
GONKA_BASE_URL = os.getenv("GONKA_BASE_URL", _get(["llm", "gonka", "base_url"], "https://api.gonkagate.com/v1"))
GONKA_MODEL = os.getenv("GONKA_MODEL", _get(["llm", "gonka", "model"], "qwen/qwen3-235b-a22b-instruct-2507-fp8"))
GONKA_TIMEOUT_SEC = float(os.getenv("GONKA_TIMEOUT_SEC", _get(["llm", "gonka", "timeout_sec"], 120)))

# Xiaomi MiMo settings
MIMO_ENABLED = str(os.getenv("MIMO_ENABLED", _get(["llm", "mimo", "enabled"], False))).strip().lower() in {"1", "true", "yes", "on"}
MIMO_API_KEY = os.getenv("MIMO_API_KEY", _get(["llm", "mimo", "api_key"], ""))
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", _get(["llm", "mimo", "base_url"], "https://api.xiaomimimo.com/anthropic"))
MIMO_MODEL = os.getenv("MIMO_MODEL", _get(["llm", "mimo", "model"], "mimo-v2-flash"))
MIMO_TIMEOUT_SEC = float(os.getenv("MIMO_TIMEOUT_SEC", _get(["llm", "mimo", "timeout_sec"], 120)))

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

# SmartEar perception layer
SMART_EAR_W_ASR     = _get(["smart_ear", "weights", "asr"],     0.50)
SMART_EAR_W_CONTEXT = _get(["smart_ear", "weights", "context"], 0.25)
SMART_EAR_W_VOCAB   = _get(["smart_ear", "weights", "vocab"],   0.25)
SMART_EAR_THRESHOLD = _get(["smart_ear", "threshold"],          0.25)
SMART_EAR_LOW_WORD_PROB      = _get(["smart_ear", "low_word_prob"],      0.50)
SMART_EAR_VOCAB_SIMILARITY   = _get(["smart_ear", "vocab_similarity"],   0.60)
SMART_EAR_SELECTION_MARGIN   = _get(["smart_ear", "selection_margin"],   1)
SMART_EAR_VOCAB_MIN_LENGTH   = _get(["smart_ear", "vocab_min_length"],   3)
SMART_EAR_VOCAB_REFRESH_EVERY = _get(["smart_ear", "vocab_refresh_every"], 60)
SMART_EAR_DOMAIN_PACKS  = _get(["smart_ear", "domain_packs"],  [])          # e.g. ["web_dev","devops"]
SMART_EAR_AUDIT_LOG     = _get(["smart_ear", "audit_log"],     "")          # path to JSONL log (empty = disabled)
SMART_EAR_AUDIT_MAX_MB  = _get(["smart_ear", "audit_max_mb"],  10)          # max log file size before rotation

# ReflexArc cognitive thresholds
REFLEX_RESONANCE_WEIGHT  = _get(["cognitive", "reflex", "resonance_weight"],  0.4)
REFLEX_PAIN_WEIGHT       = _get(["cognitive", "reflex", "pain_weight"],        0.4)
REFLEX_CORTISOL_WEIGHT   = _get(["cognitive", "reflex", "cortisol_weight"],    0.2)
REFLEX_THREAT_BOOST      = _get(["cognitive", "reflex", "threat_boost"],       0.5)
REFLEX_DANGER_THRESHOLD  = _get(["cognitive", "reflex", "danger_threshold"],   0.85)
REFLEX_LEARN_STRENGTH    = _get(["cognitive", "reflex", "learn_strength"],     0.6)
REFLEX_LOW_RESONANCE     = _get(["cognitive", "reflex", "low_resonance"],      0.3)
