from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from codex.causal_memory.layer import CausalMemoryLayer
from codex.causal_memory.store import MemoryRecord

from .base import NarrativeEvent


class NarrativeMemoryLayer:
    def __init__(self, causal_memory: CausalMemoryLayer) -> None:
        self.causal_memory = causal_memory

    def record_event(
        self,
        event: NarrativeEvent,
        *,
        frame: Dict[str, Any],
        agent_outputs: Dict[str, Any],
    ) -> MemoryRecord:
        payload = asdict(event)
        inputs = {"frame": dict(frame), "agent_outputs": dict(agent_outputs)}
        outputs = {"narrative": payload}
        return self.causal_memory.record_task(
            model="narrative_memory",
            model_type="narrative",
            inputs=inputs,
            outputs=outputs,
            tags=["narrative"],
        )

    def latest_context(self) -> Optional[Dict[str, Any]]:
        records = self._sorted_records()
        if not records:
            return None
        latest = records[-1]
        narrative = latest.outputs.get("narrative", {})
        source_frame = narrative.get("source_frame", {})
        return {
            "record_id": latest.record_id,
            "timestamp": latest.timestamp,
            "text": narrative.get("text"),
            "task_type": source_frame.get("task_type"),
            "system_state": source_frame.get("system_state"),
            "decision_choice": source_frame.get("decision", {}).get("choice"),
        }

    def timeline(self, *, limit: int = 10) -> List[Dict[str, Any]]:
        records = self._sorted_records()
        if limit:
            records = records[-limit:]
        return [
            self._timeline_entry(record)
            for record in records
        ]

    def _sorted_records(self) -> List[MemoryRecord]:
        records = list(self.causal_memory.store.filter(model="narrative_memory"))
        records.sort(key=lambda record: _safe_parse_timestamp(record.timestamp))
        return records

    @staticmethod
    def _timeline_entry(record: MemoryRecord) -> Dict[str, Any]:
        narrative = record.outputs.get("narrative", {})
        source_frame = narrative.get("source_frame", {})
        return {
            "record_id": record.record_id,
            "timestamp": record.timestamp,
            "text": narrative.get("text"),
            "task_type": source_frame.get("task_type"),
            "system_state": source_frame.get("system_state"),
            "decision_choice": source_frame.get("decision", {}).get("choice"),
        }


def _safe_parse_timestamp(timestamp: str) -> datetime:
    try:
        return datetime.fromisoformat(timestamp)
    except ValueError:
        return datetime.min
