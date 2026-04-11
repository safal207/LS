from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import RelationalSelf


@dataclass
class RelationalSelfBuilder:
    """Build/update the Relational Self snapshot from graph memory."""

    store: MemoryGraphStore

    def update(
        self,
        *,
        cycle_id: str | None = None,
        source: str = "care_cycle",
        omni_insight: dict[str, Any] | None = None,
        recent_window: int = 25,
    ) -> RelationalSelf:
        return self.store.update_self_from_cycle(
            cycle_id=cycle_id,
            source=source,
            omni_insight=omni_insight,
            recent_window=recent_window,
        )

    def current(self) -> RelationalSelf:
        return self.store.get_relational_self()
