from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import MAX_TRACE_LENGTH, get_norm_conflicts


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

    def update_from_identity(self, identity_core: Any) -> dict[str, float]:
        integrity = float(getattr(identity_core, "identity_integrity", 0.5))
        resistance = float(getattr(identity_core, "drift_resistance", 0.5))
        self.militarydisciplinescore = max(
            0.0,
            min(1.0, 0.6 * integrity + 0.4 * resistance),
        )
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }

    def update_from_autonomy(self, autonomy_engine: Any) -> dict[str, float]:
        alignment = float(getattr(autonomy_engine, "autonomy_level", 0.5))
        # Note: using self.command_coherence for inertia
        self.command_coherence = max(
            0.0,
            min(1.0, 0.7 * self.command_coherence + 0.3 * alignment),
        )
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }

    def update_from_culture(self, culture_engine: Any) -> dict[str, float]:
        conflicts = len(get_norm_conflicts(culture_engine))
        # discipline decays linearly: 0 at ~7 conflicts
        self.discipline_bias = max(
            0.0,
            min(1.0, 1.0 - 0.15 * conflicts),
        )
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
        }
        self.discipline_trace.append(entry)
        if len(self.discipline_trace) > MAX_TRACE_LENGTH:
            self.discipline_trace = self.discipline_trace[-MAX_TRACE_LENGTH:]
        return entry

    # Compatibility aliases (camelCase delegates to snake_case primary)
    def updatefromidentity(self, identitycore: Any) -> dict[str, float]:
        return self.update_from_identity(identitycore)

    def updatefromautonomy(self, autonomy: Any) -> dict[str, float]:
        return self.update_from_autonomy(autonomy)

    def updatefromculture(self, culture: Any) -> dict[str, float]:
        return self.update_from_culture(culture)

    def updatetrace(self) -> dict[str, Any]:
        return self.update_trace()

    @property
    def militarydiscipline(self) -> float:
        return self.militarydisciplinescore
