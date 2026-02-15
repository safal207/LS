from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MilitocracyEngine:
    """
    Phase 11.1: Militocracy Engine
    Models cognitive discipline, command coherence, and structural bias.
    """

    militarydisciplinescore: float = 0.5
    command_coherence: float = 0.5
    discipline_bias: float = 0.5
    discipline_trace: list[dict[str, Any]] = field(default_factory=list)

    def updatefromidentity(self, identitycore: Any) -> None:
        integrity = float(getattr(identitycore, "identity_integrity", 0.5))
        resistance = float(getattr(identitycore, "drift_resistance", 0.5))
        self.militarydisciplinescore = max(
            0.0,
            min(1.0, 0.6 * integrity + 0.4 * resistance),
        )

    def updatefromautonomy(self, autonomy: Any) -> None:
        alignment = float(getattr(autonomy, "autonomy_level", 0.5))
        self.command_coherence = max(
            0.0,
            min(1.0, 0.7 * self.command_coherence + 0.3 * alignment),
        )

    def updatefromculture(self, culture: Any) -> None:
        conflicts = len(getattr(culture, "norm_conflicts", []))
        self.discipline_bias = max(
            0.0,
            min(1.0, 1.0 - 0.15 * conflicts),
        )

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "militarydisciplinescore": self.militarydisciplinescore,
            "commandcoherence": self.command_coherence,
            "disciplinebias": self.discipline_bias,
        }
        self.discipline_trace.append(entry)
        if len(self.discipline_trace) > 200:
            self.discipline_trace = self.discipline_trace[-200:]
        return entry

    # Compatibility aliases (Part A implementation uses updatefrom*, existing code uses update_from_*)
    def update_from_identity(self, identity_core: Any) -> dict[str, float]:
        self.updatefromidentity(identity_core)
        return {"militarydisciplinescore": self.militarydisciplinescore}

    def update_from_autonomy(self, autonomy_engine: Any) -> dict[str, float]:
        self.updatefromautonomy(autonomy_engine)
        return {"command_coherence": self.command_coherence}

    def update_from_culture(self, culture_engine: Any) -> dict[str, float]:
        self.updatefromculture(culture_engine)
        return {"discipline_bias": self.discipline_bias}

    @property
    def militarydiscipline(self) -> float:
        return self.militarydisciplinescore
