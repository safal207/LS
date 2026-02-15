from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SynergyEngine:
    """Phase 11.1 layer for cooperative cognitive synergy."""

    synergy_index: float = 0.5
    cooperative_efficiency: float = 0.5
    collective_synergy: float = 0.5
    synergy_trace: list[dict[str, Any]] = field(default_factory=list)

    def update_from_social(self, social_engine: Any) -> dict[str, float]:
        cooperation = float(getattr(social_engine, "cooperation_score", 0.5))
        conflict = float(getattr(social_engine, "socialconflictscore", 0.0))
        self.cooperative_efficiency = max(
            0.0,
            min(1.0, cooperation * (1.0 - (0.5 * conflict))),
        )
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
        }

    def update_from_culture(self, culture_engine: Any) -> dict[str, float]:
        alignment = float(getattr(culture_engine, "culturalalignmentscore", 0.5))
        civilization_state = dict(getattr(culture_engine, "civilization_state", {}))
        # Note: civilizationmaturityscore defaults to 0.5 during cold start until collective update runs.
        maturity = float(civilization_state.get("civilizationmaturityscore", 0.5))
        self.synergy_index = max(
            0.0,
            min(
                1.0,
                (0.4 * alignment) + (0.3 * maturity) + (0.3 * self.cooperative_efficiency),
            ),
        )
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
        }

    def update_from_collective(self, multiagent_system: Any) -> dict[str, float]:
        values: list[float] = []
        for agent in list(getattr(multiagent_system, "agents", [])):
            engine = getattr(agent, "synergy", None)
            if engine is None:
                continue
            values.append(float(getattr(engine, "synergy_index", 0.5)))

        if values:
            self.collective_synergy = sum(values) / len(values)
        else:
            self.collective_synergy = self.synergy_index
        return {
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
        }

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "t": len(self.synergy_trace),
            "synergy_index": self.synergy_index,
            "cooperative_efficiency": self.cooperative_efficiency,
            "collective_synergy": self.collective_synergy,
        }
        self.synergy_trace.append(entry)
        if len(self.synergy_trace) > 200:
            self.synergy_trace = self.synergy_trace[-200:]
        return entry

    # Compatibility aliases
    def updatefromsocial(self, social_engine: Any) -> dict[str, float]:
        return self.update_from_social(social_engine)

    def updatefromculture(self, culture_engine: Any) -> dict[str, float]:
        return self.update_from_culture(culture_engine)

    def updatefromcollective(self, multiagent_system: Any) -> dict[str, float]:
        return self.update_from_collective(multiagent_system)

    def updatetrace(self) -> dict[str, Any]:
        return self.update_trace()
