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
        snapshot = self.store.update_self_from_cycle(
            cycle_id=cycle_id,
            source=source,
            omni_insight=omni_insight,
            recent_window=recent_window,
        )
        self.store.evolve_attachment_bond(
            conversation_frequency=min(1.0, max(0.0, recent_window / 25.0)),
            conversation_quality=float(snapshot.self_coherence_score or 0.0),
            user_feedback_signal=float(snapshot.bond_strength or 0.0),
            omni_signal=dict(omni_insight or {}),
            shared_relational_delta=abs(float(snapshot.self_coherence_score or 0.0) - 0.5),
            source=source,
        )
        # Phase 2.4: pull the latest aggregated emotional_summary into the
        # returned snapshot so callers always see a consistent picture.
        # The stored JSON is already updated by update_self_from_cycle (which
        # carries over emotional_summary) — we refresh the in-memory object.
        refreshed = self.store.get_relational_self()
        snapshot.emotional_summary = dict(refreshed.emotional_summary or {})
        return snapshot

    def current(self) -> RelationalSelf:
        return self.store.get_relational_self()
