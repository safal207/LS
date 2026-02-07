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
            timestamp=datetime.now(timezone.utc).isoformat(),
            tags=list(tags or []),
        )
        self.bus.publish(frame)
        return frame
