from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shared.config_loader import get_config

from .agent.sleep_config import SleepConfig


@dataclass(frozen=True)
class HardwareSettings:
    max_ram_usage_mb: int = 4000
    target_latency_sec: float = 7


@dataclass(frozen=True)
class AudioSettings:
    chunk_duration: float = 3.0
    sample_rate: int = 16000
    volume_threshold: float = 0.01


@dataclass(frozen=True)
class SttSettings:
    whisper_model_size: str = "small"


@dataclass(frozen=True)
class BreakerSettings:
    failure_threshold: int = 3
    cooldown_seconds: int = 10


@dataclass(frozen=True)
class OllamaSettings:
    host: str = "http://localhost:11434"
    timeout: int = 30
    model: str = ""


@dataclass(frozen=True)
class GroqSettings:
    api_key: str = ""
    model: str = ""


@dataclass(frozen=True)
class LlmSettings:
    model_name: str = "qwen2.5:7b"
    ram_aware: bool = False
    heavy_model: str = "qwen2.5:7b"
    light_model: str = "qwen2.5:7b"
    ram_threshold_gb: float = 6.0
    use_cloud: bool = False
    use_cotcore: bool = False
    use_breaker: bool = False
    temporal_enabled: bool = True
    use_groq: bool = False
    temperature: float = 0.6
    max_tokens: int = 4096
    top_p: float = 0.9
    system_prompt: str = ""
    breaker: BreakerSettings = BreakerSettings()
    ollama: OllamaSettings = OllamaSettings()
    groq: GroqSettings = GroqSettings()


@dataclass(frozen=True)
class AgentSettings:
    enabled: bool = False
    cancel_on_new_input: bool = True
    cancel_grace_ms: int = 0
    memory_max_chars: int = 2000
    metrics_enabled: bool = True
    observability_enabled: bool = True
    event_sink: str = "print"
    sleep: SleepConfig = SleepConfig()


@dataclass(frozen=True)
class HotkeysSettings:
    hide: str = "F9"
    lri_hr: str = "F1"
    lri_dev: str = "F2"
    lri_cto: str = "F3"


@dataclass(frozen=True)
class AppSettings:
    hardware: HardwareSettings
    audio: AudioSettings
    stt: SttSettings
    llm: LlmSettings
    agent: AgentSettings
    hotkeys: HotkeysSettings
    question_keywords: list[str]
    access_protocol_prompt: str


_cfg = get_config()


def _get(path: list[str], default: Any = None) -> Any:
    current: Any = _cfg
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


SETTINGS = AppSettings(
    hardware=HardwareSettings(
        max_ram_usage_mb=int(_get(["hardware", "max_ram_usage_mb"], 4000)),
        target_latency_sec=float(_get(["hardware", "target_latency_sec"], 7)),
    ),
    audio=AudioSettings(
        chunk_duration=float(_get(["audio", "chunk_duration"], 3.0)),
        sample_rate=int(_get(["audio", "sample_rate"], 16000)),
        volume_threshold=float(_get(["audio", "volume_threshold"], 0.01)),
    ),
    stt=SttSettings(
        whisper_model_size=str(_get(["stt", "whisper_model_size"], "small")),
    ),
    llm=LlmSettings(
        model_name=str(_get(["llm", "model_name"], "qwen2.5:7b")),
        ram_aware=bool(_get(["llm", "ram_aware"], False)),
        heavy_model=str(_get(["llm", "heavy_model"], _get(["llm", "model_name"], "qwen2.5:7b"))),
        light_model=str(_get(["llm", "light_model"], _get(["llm", "model_name"], "qwen2.5:7b"))),
        ram_threshold_gb=float(_get(["llm", "ram_threshold_gb"], 6.0)),
        use_cloud=bool(_get(["llm", "use_cloud"], False)),
        use_cotcore=bool(_get(["llm", "use_cotcore"], False)),
        use_breaker=bool(_get(["llm", "use_breaker"], False)),
        temporal_enabled=bool(_get(["llm", "temporal_enabled"], True)),
        use_groq=bool(_get(["llm", "use_groq"], False)),
        temperature=float(_get(["llm", "temperature"], 0.6)),
        max_tokens=int(_get(["llm", "max_tokens"], 4096)),
        top_p=float(_get(["llm", "top_p"], 0.9)),
        system_prompt=str(_get(["llm", "system_prompt"], "")),
        breaker=BreakerSettings(
            failure_threshold=int(_get(["llm", "breaker", "failure_threshold"], 3)),
            cooldown_seconds=int(_get(["llm", "breaker", "cooldown_seconds"], 10)),
        ),
        ollama=OllamaSettings(
            host=str(_get(["llm", "ollama", "host"], "http://localhost:11434")),
            timeout=int(_get(["llm", "ollama", "timeout"], 30)),
            model=str(_get(["llm", "ollama", "model"], "")),
        ),
        groq=GroqSettings(
            api_key=str(_get(["llm", "groq", "api_key"], "")),
            model=str(_get(["llm", "groq", "model"], "")),
        ),
    ),
    agent=AgentSettings(
        enabled=bool(_get(["agent", "enabled"], False)),
        cancel_on_new_input=bool(_get(["agent", "cancel_on_new_input"], True)),
        cancel_grace_ms=int(_get(["agent", "cancel_grace_ms"], 0)),
        memory_max_chars=int(_get(["agent", "memory_max_chars"], 2000)),
        metrics_enabled=bool(_get(["agent", "metrics_enabled"], True)),
        observability_enabled=bool(_get(["agent", "observability_enabled"], True)),
        event_sink=str(_get(["agent", "event_sink"], "print")),
        sleep=SleepConfig(
            idle_timeout=int(_get(["agent", "sleep", "idle_timeout"], 1800)),
            prune_threshold=float(_get(["agent", "sleep", "prune_threshold"], 0.2)),
            active_window=int(_get(["agent", "sleep", "active_window"], 200)),
            reflection_energy=float(_get(["agent", "sleep", "reflection_energy"], 0.05)),
            compost_boost_per_node=float(_get(["agent", "sleep", "compost_boost_per_node"], 0.01)),
            immune_threshold=float(_get(["agent", "sleep", "immune_threshold"], 0.7)),
            immune_decay=float(_get(["agent", "sleep", "immune_decay"], 0.9)),
        ),
    ),
    hotkeys=HotkeysSettings(
        hide=str(_get(["hotkeys", "hide"], "F9")),
        lri_hr=str(_get(["hotkeys", "lri_hr"], "F1")),
        lri_dev=str(_get(["hotkeys", "lri_dev"], "F2")),
        lri_cto=str(_get(["hotkeys", "lri_cto"], "F3")),
    ),
    question_keywords=list(_get(["question_keywords"], [])),
    access_protocol_prompt=str(_get(["access_protocol_prompt"], "")),
)


# Backward-compatible constants
MAX_RAM_USAGE_MB = SETTINGS.hardware.max_ram_usage_mb
TARGET_LATENCY_SEC = SETTINGS.hardware.target_latency_sec
WHISPER_MODEL_SIZE = SETTINGS.stt.whisper_model_size
LLM_MODEL_NAME = SETTINGS.llm.model_name
LLM_RAM_AWARE = SETTINGS.llm.ram_aware
LLM_HEAVY_MODEL = SETTINGS.llm.heavy_model
LLM_LIGHT_MODEL = SETTINGS.llm.light_model
LLM_RAM_THRESHOLD_GB = SETTINGS.llm.ram_threshold_gb
USE_CLOUD_LLM = SETTINGS.llm.use_cloud
USE_COTCORE = SETTINGS.llm.use_cotcore
USE_BREAKER = SETTINGS.llm.use_breaker
BREAKER_THRESHOLD = SETTINGS.llm.breaker.failure_threshold
BREAKER_COOLDOWN = SETTINGS.llm.breaker.cooldown_seconds
TEMPORAL_ENABLED = SETTINGS.llm.temporal_enabled
AGENT_ENABLED = SETTINGS.agent.enabled
AGENT_CANCEL_ON_NEW_INPUT = SETTINGS.agent.cancel_on_new_input
AGENT_CANCEL_GRACE_MS = SETTINGS.agent.cancel_grace_ms
AGENT_MEMORY_MAX_CHARS = SETTINGS.agent.memory_max_chars
AGENT_METRICS_ENABLED = SETTINGS.agent.metrics_enabled
AGENT_OBSERVABILITY_ENABLED = SETTINGS.agent.observability_enabled
AGENT_EVENT_SINK = SETTINGS.agent.event_sink
AUDIO_CHUNK_DURATION = SETTINGS.audio.chunk_duration
CHUNK_DURATION = AUDIO_CHUNK_DURATION
SAMPLE_RATE = SETTINGS.audio.sample_rate
VOLUME_THRESHOLD = SETTINGS.audio.volume_threshold
OLLAMA_HOST = SETTINGS.llm.ollama.host
OLLAMA_TIMEOUT = SETTINGS.llm.ollama.timeout
OLLAMA_MODEL = SETTINGS.llm.ollama.model
GROQ_API_KEY = SETTINGS.llm.groq.api_key
GROQ_MODEL = SETTINGS.llm.groq.model
USE_GROQ = SETTINGS.llm.use_groq
TEMPERATURE = SETTINGS.llm.temperature
MAX_TOKENS = SETTINGS.llm.max_tokens
TOP_P = SETTINGS.llm.top_p
SYSTEM_PROMPT = SETTINGS.llm.system_prompt
QUESTION_KEYWORDS = SETTINGS.question_keywords
KEY_HIDE = SETTINGS.hotkeys.hide
KEY_LRI_HR = SETTINGS.hotkeys.lri_hr
KEY_LRI_DEV = SETTINGS.hotkeys.lri_dev
KEY_LRI_CTO = SETTINGS.hotkeys.lri_cto
ACCESS_PROTOCOL_PROMPT = SETTINGS.access_protocol_prompt
SLEEP_CONFIG = SETTINGS.agent.sleep
