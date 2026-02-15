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

    def updatefromsocial(self, social: Any) -> None:
        cooperation = float(getattr(social, "cooperation_score", 0.5))
        conflict = float(getattr(social, "socialconflictscore", 0.0))
        self.cooperative_efficiency = max(
            0.0,
            min(1.0, cooperation * (1.0 - 0.5 * conflict)),
        )

    def updatefromculture(self, culture: Any) -> None:
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

    def updatefromcollective(self, multi: Any) -> None:
        values = []
        # Support both list (my previous implementation) and dict (user diff suggestion) for robustness
        agents_collection = getattr(multi, "agents", [])
        if isinstance(agents_collection, dict):
            iterator = agents_collection.values()
        else:
            iterator = agents_collection

        for agent in iterator:
            culture = getattr(agent, "culture", None)
            if culture:
                values.append(
                    float(
                        getattr(culture, "civilization_state", {}).get(
                            "civilizationmaturityscore", 0.5
                        )
                    )
                )
        if values:
            self.collective_synergy = sum(values) / len(values)

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "synergyindex": self.synergy_index,
            "cooperativeefficiency": self.cooperative_efficiency,
            "collectivesynergy": self.collective_synergy,
        }
        self.synergy_trace.append(entry)
        if len(self.synergy_trace) > 200:
            self.synergy_trace = self.synergy_trace[-200:]
        return entry

    # Compatibility aliases
    def update_from_social(self, social: Any) -> dict[str, float]:
        self.updatefromsocial(social)
        return {"cooperative_efficiency": self.cooperative_efficiency}

    def update_from_culture(self, culture: Any) -> dict[str, float]:
        self.updatefromculture(culture)
        return {"synergy_index": self.synergy_index}

    def update_from_collective(self, multi: Any) -> dict[str, float]:
        self.updatefromcollective(multi)
        return {"collective_synergy": self.collective_synergy}
