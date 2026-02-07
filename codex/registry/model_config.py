from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable

ALLOWED_MODEL_TYPES = {"llm", "stt", "vad", "embeddings", "custom"}
REQUIRED_FIELDS = {"type", "path"}
OPTIONAL_FIELDS = {"context", "quant", "device", "ram_required", "description"}


class ModelConfigError(ValueError):
    """Raised when a model configuration is invalid."""


@dataclass(frozen=True)
class ModelConfig:
    name: str
    type: str
    path: str
    context: int | None = None
    quant: str | None = None
    device: str | None = None
    ram_required: str | None = None
    description: str | None = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "ModelConfig":
        validate_config(name, data)
        extras = {
            key: value
            for key, value in data.items()
            if key not in REQUIRED_FIELDS and key not in OPTIONAL_FIELDS
        }
        return cls(
            name=name,
            type=data["type"],
            path=data["path"],
            context=data.get("context"),
            quant=data.get("quant"),
            device=data.get("device"),
            ram_required=data.get("ram_required"),
            description=data.get("description"),
            extras=extras,
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "type": self.type,
            "path": self.path,
        }
        if self.context is not None:
            payload["context"] = self.context
        if self.quant is not None:
            payload["quant"] = self.quant
        if self.device is not None:
            payload["device"] = self.device
        if self.ram_required is not None:
            payload["ram_required"] = self.ram_required
        if self.description is not None:
            payload["description"] = self.description
        payload.update(self.extras)
        return payload


def validate_config(name: str, data: Dict[str, Any]) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ModelConfigError("Model name must be a non-empty string.")
    if not isinstance(data, dict):
        raise ModelConfigError("Model config must be a dictionary.")
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ModelConfigError(f"Missing required fields: {sorted(missing)}")
    model_type = data.get("type")
    if model_type not in ALLOWED_MODEL_TYPES:
        raise ModelConfigError(
            f"Invalid model type '{model_type}'. Allowed: {sorted(ALLOWED_MODEL_TYPES)}"
        )
    path = data.get("path")
    if not isinstance(path, str) or not path.strip():
        raise ModelConfigError("Model path must be a non-empty string.")
    context = data.get("context")
    if context is not None and not isinstance(context, int):
        raise ModelConfigError("Model context must be an integer if provided.")
    for field_name in ("quant", "device", "ram_required", "description"):
        value = data.get(field_name)
        if value is not None and not isinstance(value, str):
            raise ModelConfigError(f"Model {field_name} must be a string if provided.")


def format_model_entry(name: str, data: Dict[str, Any]) -> str:
    model_type = data.get("type", "custom").upper()
    details: Iterable[str] = []
    quant = data.get("quant")
    device = data.get("device")
    if quant and device:
        details = [quant, device]
    elif quant:
        details = [quant]
    elif device:
        details = [device]
    detail_text = f" ({', '.join(details)})" if details else ""
    return f"[{model_type}] {name}{detail_text}"


DEFAULT_MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "whisper-small-int8": {
        "type": "stt",
        "path": "models/whisper-small-int8",
        "quant": "int8",
        "device": "cpu",
        "ram_required": "1GB",
    },
    "whisper-medium-int8": {
        "type": "stt",
        "path": "models/whisper-medium-int8",
        "quant": "int8",
        "device": "cpu",
        "ram_required": "2GB",
    },
    "phi3-mini-4k": {
        "type": "llm",
        "path": "models/phi3-mini-4k",
        "context": 4096,
        "quant": "q4",
        "device": "cpu",
        "ram_required": "2GB",
    },
    "qwen2.5-1.5b": {
        "type": "llm",
        "path": "models/qwen2.5-1.5b",
        "context": 4096,
        "quant": "fp16",
        "device": "gpu",
        "ram_required": "4GB",
    },
    "llama3.2-3b": {
        "type": "llm",
        "path": "models/llama3.2-3b",
        "context": 4096,
        "quant": "q4",
        "device": "gpu",
        "ram_required": "6GB",
    },
    "silero-vad": {
        "type": "vad",
        "path": "models/silero-vad",
        "device": "cpu",
        "ram_required": "256MB",
    },
}
