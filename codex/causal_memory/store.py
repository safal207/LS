from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    model: str
    model_type: str
    inputs: Dict[str, Any]
    outputs: Dict[str, Any]
    parameters: Dict[str, Any]
    hardware: Dict[str, Any]
    metrics: Dict[str, Any]
    success: bool
    error: str | None = None
    tags: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def build(
        cls,
        *,
        model: str,
        model_type: str,
        inputs: Dict[str, Any] | None = None,
        outputs: Dict[str, Any] | None = None,
        parameters: Dict[str, Any] | None = None,
        hardware: Dict[str, Any] | None = None,
        metrics: Dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
        tags: List[str] | None = None,
    ) -> "MemoryRecord":
        return cls(
            record_id=str(uuid.uuid4()),
            model=model,
            model_type=model_type,
            inputs=dict(inputs or {}),
            outputs=dict(outputs or {}),
            parameters=dict(parameters or {}),
            hardware=dict(hardware or {}),
            metrics=dict(metrics or {}),
            success=success,
            error=error,
            tags=list(tags or []),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "record_id": self.record_id,
            "model": self.model,
            "model_type": self.model_type,
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "parameters": dict(self.parameters),
            "hardware": dict(self.hardware),
            "metrics": dict(self.metrics),
            "success": self.success,
            "timestamp": self.timestamp,
        }
        if self.error:
            payload["error"] = self.error
        if self.tags:
            payload["tags"] = list(self.tags)
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MemoryRecord":
        return cls(
            record_id=payload["record_id"],
            model=payload["model"],
            model_type=payload.get("model_type", "unknown"),
            inputs=dict(payload.get("inputs", {})),
            outputs=dict(payload.get("outputs", {})),
            parameters=dict(payload.get("parameters", {})),
            hardware=dict(payload.get("hardware", {})),
            metrics=dict(payload.get("metrics", {})),
            success=payload.get("success", True),
            error=payload.get("error"),
            tags=list(payload.get("tags", [])),
            timestamp=payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
        )


class MemoryStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, record: MemoryRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.to_dict(), sort_keys=True))
            handle.write("\n")

    def load_all(self) -> List[MemoryRecord]:
        if not self.path.exists():
            return []
        return [MemoryRecord.from_dict(payload) for payload in self._iter_payloads()]

    def filter(
        self,
        *,
        model: str | None = None,
        success: bool | None = None,
    ) -> Iterable[MemoryRecord]:
        for record in self.load_all():
            if model is not None and record.model != model:
                continue
            if success is not None and record.success is not success:
                continue
            yield record

    def _iter_payloads(self) -> Iterable[Dict[str, Any]]:
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)
