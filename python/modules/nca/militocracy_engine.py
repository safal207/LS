from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MilitocracyEngine:
    """Phase 11.1 layer for cognitive discipline and command coherence."""

    militarydisciplinescore: float = 0.5
    command_coherence: float = 0.5
    discipline_bias: float = 0.5
    discipline_trace: list[dict[str, Any]] = field(default_factory=list)

    def update_from_identity(self, identity_core: Any) -> dict[str, float]:
        integrity = float(getattr(identity_core, "identity_integrity", 0.5))
        resistance = float(getattr(identity_core, "drift_resistance", 0.5))
        self.militarydisciplinescore = max(0.0, min(1.0, (0.6 * integrity) + (0.4 * resistance)))
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }

    def update_from_autonomy(self, autonomy_engine: Any) -> dict[str, float]:
        autonomy_level = float(getattr(autonomy_engine, "autonomy_level", 0.5))
        regulation = float(getattr(autonomy_engine, "selfregulationstrength", 0.5))
        self.command_coherence = max(
            0.0,
            min(1.0, (0.55 * self.command_coherence) + (0.3 * autonomy_level) + (0.15 * regulation)),
        )
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }

    def update_from_culture(self, culture_engine: Any) -> dict[str, float]:
        conflicts = getattr(culture_engine, "norm_conflicts", getattr(culture_engine, "normconflicts", []))
        alignment = float(getattr(culture_engine, "culturalalignmentscore", 0.5))
        conflict_ratio = min(1.0, len(list(conflicts)) / 5.0)
        self.discipline_bias = max(0.0, min(1.0, (0.6 * alignment) + (0.4 * (1.0 - conflict_ratio))))
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "t": len(self.discipline_trace),
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }
        self.discipline_trace.append(entry)
        if len(self.discipline_trace) > 200:
            self.discipline_trace = self.discipline_trace[-200:]
        return entry

    # Compatibility aliases
    def updatefromidentity(self, identity_core: Any) -> dict[str, float]:
        return self.update_from_identity(identity_core)

    def updatefromautonomy(self, autonomy_engine: Any) -> dict[str, float]:
        return self.update_from_autonomy(autonomy_engine)

    def updatefromculture(self, culture_engine: Any) -> dict[str, float]:
        return self.update_from_culture(culture_engine)

    def updatetrace(self) -> dict[str, Any]:
        return self.update_trace()

    @property
    def militarydiscipline(self) -> float:
        return self.militarydisciplinescore
