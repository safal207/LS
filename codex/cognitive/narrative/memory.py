from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

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
