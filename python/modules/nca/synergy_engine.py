from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from .utils import MAX_TRACE_LENGTH

if TYPE_CHECKING:
    from .update_context import UpdateContext


@dataclass
class SynergyEngine:
    """
    Phase 11.1: Synergy Engine
    Models cooperative efficiency, synergy index, and collective synergy.
    """

    synergy_index: float = 0.5
    cooperative_efficiency: float = 0.5
    collective_synergy: float = 0.5
    sharedgoalpressure: float = 0.5
    cooperative_priority: float = 0.5
    collectivealignmentscore: float = 0.5
    synergy_trace: list[dict[str, Any]] = field(default_factory=list)

    def update(self, context: UpdateContext) -> dict[str, Any]:
        """Unified update method using deterministic context."""
        # 1. Update from social
        self.update_from_social(context.social_snapshot)

        # 2. Update from culture
        self.update_from_culture(context.culture_snapshot)

        # 3. Update from collective
        self.update_from_collective(context.collective_state)

        # 4. Update trace
        snapshot = self.update_trace()

        return {
            "snapshot": self.to_context_snapshot(),
            "trace_snapshot": snapshot
        }

    def to_context_snapshot(self) -> dict[str, Any]:
        """Export state for context propagation."""
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
            "sharedgoalpressure": self.sharedgoalpressure,
            "shared_goal_pressure": self.sharedgoalpressure,
            "cooperative_priority": self.cooperative_priority,
            "collectivealignmentscore": self.collectivealignmentscore,
            "collective_alignment_score": self.collectivealignmentscore,
        }

    def _get_attr(self, obj: Any, key: str, default: Any) -> Any:
        """Helper to safely get attribute from object or dict."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def update_from_social(self, social: Any) -> dict[str, float]:
        cooperation = float(self._get_attr(social, "cooperation_score", 0.5))
        conflict = float(self._get_attr(social, "socialconflictscore", 0.0))
        self.cooperative_efficiency = max(
            0.0,
            min(1.0, cooperation * (1.0 - 0.5 * conflict)),
        )
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
            "sharedgoalpressure": self.sharedgoalpressure,
            "shared_goal_pressure": self.sharedgoalpressure,
            "cooperative_priority": self.cooperative_priority,
            "collectivealignmentscore": self.collectivealignmentscore,
            "collective_alignment_score": self.collectivealignmentscore,
        }

    def update_from_culture(self, culture: Any) -> dict[str, float]:
        alignment = float(self._get_attr(culture, "culturalalignmentscore", 0.5))
        # Note: civilizationmaturityscore defaults to 0.5 during cold start until collective update runs.
        # Safe access to civilization_state which might be None in some contexts
        civ_state = self._get_attr(culture, "civilization_state", {}) or {}
        maturity = float(civ_state.get("civilizationmaturityscore", 0.5))

        self.synergy_index = max(
            0.0,
            min(
                1.0,
                0.4 * alignment
                + 0.3 * maturity
                + 0.3 * self.cooperative_efficiency,
            ),
        )
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
            "sharedgoalpressure": self.sharedgoalpressure,
            "shared_goal_pressure": self.sharedgoalpressure,
            "cooperative_priority": self.cooperative_priority,
            "collectivealignmentscore": self.collectivealignmentscore,
            "collective_alignment_score": self.collectivealignmentscore,
        }

    def update_from_collective(self, multi: Any) -> dict[str, float]:
        # Cleanly read from the pre-computed collective state in MultiAgentSystem
        self.collective_synergy = float(self._get_attr(multi, "collectivesynergy", 0.5))
        self.sharedgoalpressure = float(self._get_attr(multi, "sharedgoalpressure", 0.5))
        self.collectivealignmentscore = float(self._get_attr(multi, "collectivemetaalignment", self.synergy_index))
        self.cooperative_priority = max(
            0.0,
            min(1.0, 0.6 * self.cooperative_efficiency + 0.4 * self.sharedgoalpressure),
        )
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
            "sharedgoalpressure": self.sharedgoalpressure,
            "shared_goal_pressure": self.sharedgoalpressure,
            "cooperative_priority": self.cooperative_priority,
            "collectivealignmentscore": self.collectivealignmentscore,
            "collective_alignment_score": self.collectivealignmentscore,
        }

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
            "sharedgoalpressure": self.sharedgoalpressure,
            "shared_goal_pressure": self.sharedgoalpressure,
            "cooperative_priority": self.cooperative_priority,
            "collectivealignmentscore": self.collectivealignmentscore,
            "collective_alignment_score": self.collectivealignmentscore,
        }
        self.synergy_trace.append(entry)
        if len(self.synergy_trace) > MAX_TRACE_LENGTH:
            self.synergy_trace = self.synergy_trace[-MAX_TRACE_LENGTH:]
        return entry


    @property
    def shared_goal_pressure(self) -> float:
        return self.sharedgoalpressure

    @shared_goal_pressure.setter
    def shared_goal_pressure(self, value: float) -> None:
        self.sharedgoalpressure = float(value)

    @property
    def collective_alignment_score(self) -> float:
        return self.collectivealignmentscore

    @collective_alignment_score.setter
    def collective_alignment_score(self, value: float) -> None:
        self.collectivealignmentscore = float(value)

    # Compatibility aliases (camelCase delegates to snake_case primary)
    def updatefromsocial(self, social: Any) -> dict[str, float]:
        return self.update_from_social(social)

    def updatefromculture(self, culture: Any) -> dict[str, float]:
        return self.update_from_culture(culture)

    def updatefromcollective(self, multi: Any) -> dict[str, float]:
        return self.update_from_collective(multi)

    def updatetrace(self) -> dict[str, Any]:
        return self.update_trace()
