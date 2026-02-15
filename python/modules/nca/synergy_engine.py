from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SynergyEngine:
    """
    Phase 11.1: Synergy Engine
    Models cooperative efficiency, synergy index, and collective synergy.
    """

    synergy_index: float = 0.5
    cooperative_efficiency: float = 0.5
    collective_synergy: float = 0.5
    synergy_trace: list[dict[str, Any]] = field(default_factory=list)

    def update_from_social(self, social: Any) -> dict[str, float]:
        cooperation = float(getattr(social, "cooperation_score", 0.5))
        conflict = float(getattr(social, "socialconflictscore", 0.0))
        self.cooperative_efficiency = max(
            0.0,
            min(1.0, cooperation * (1.0 - 0.5 * conflict)),
        )
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
        }

    def update_from_culture(self, culture: Any) -> dict[str, float]:
        alignment = float(getattr(culture, "culturalalignmentscore", 0.5))
        # Note: civilizationmaturityscore defaults to 0.5 during cold start until collective update runs.
        maturity = float(
            getattr(culture, "civilization_state", {}).get("civilizationmaturityscore", 0.5)
        )
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
        }

    def update_from_collective(self, multi: Any) -> dict[str, float]:
        # Cleanly read from the pre-computed collective state in MultiAgentSystem
        # This resolves the semantic discrepancy noted in code review.
        self.collective_synergy = float(getattr(multi, "collectivesynergy", 0.5))
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
        }

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
        }
        self.synergy_trace.append(entry)
        if len(self.synergy_trace) > 200:
            self.synergy_trace = self.synergy_trace[-200:]
        return entry

    # Compatibility aliases (camelCase delegates to snake_case primary)
    def updatefromsocial(self, social: Any) -> dict[str, float]:
        return self.update_from_social(social)

    def updatefromculture(self, culture: Any) -> dict[str, float]:
        return self.update_from_culture(culture)

    def updatefromcollective(self, multi: Any) -> dict[str, float]:
        return self.update_from_collective(multi)

    def updatetrace(self) -> dict[str, Any]:
        return self.update_trace()
