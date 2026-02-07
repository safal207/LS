from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict

from .bus import WorkspaceBus
from .schema import GlobalFrame


@dataclass
class GlobalBroadcaster:
    bus: WorkspaceBus

    def broadcast(
        self,
        *,
        task_type: str,
        thread_id: str,
        system_state: str,
        self_model: Dict[str, Any],
        affective: Dict[str, Any],
        capu_features: Dict[str, float],
        decision: Dict[str, Any],
        memory_refs: Dict[str, str],
        hardware: Dict[str, Any] | None = None,
        narrative_refs: Dict[str, str] | None = None,
        active_thread_id: str | None = None,
        thread_priorities: Dict[str, float] | None = None,
        attention_distribution: Dict[str, float] | None = None,
        tags: list[str] | None = None,
    ) -> GlobalFrame:
        frame = GlobalFrame(
            task_type=task_type,
            thread_id=thread_id,
            system_state=system_state,
            self_model=dict(self_model),
            affective=dict(affective),
            capu_features=dict(capu_features),
            decision=dict(decision),
            memory_refs=dict(memory_refs),
            hardware=dict(hardware or {}),
            narrative_refs=dict(narrative_refs or {}),
            timestamp=datetime.now(timezone.utc).isoformat(),
            tags=list(tags or []),
            active_thread_id=active_thread_id,
            thread_priorities=dict(thread_priorities or {}),
            attention_distribution=dict(attention_distribution or {}),
        )
        self.bus.publish(frame)
        return frame
