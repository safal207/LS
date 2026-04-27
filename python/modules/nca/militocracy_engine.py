from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from .utils import MAX_TRACE_LENGTH, get_norm_conflicts

if TYPE_CHECKING:
    from .update_context import UpdateContext


@dataclass
class MilitocracyEngine:
    """
    Phase 11.1: Militocracy Engine
    Models cognitive discipline, command coherence, and structural bias.
    """

    militarydisciplinescore: float = 0.5
    command_coherence: float = 0.5
    discipline_bias: float = 0.5
    ideaqualityscore: float = 0.5
    discipline_score: float = 0.5
    execution_priority: float = 0.5
    override_signal: bool = False
    discipline_trace: list[dict[str, Any]] = field(default_factory=list)

    def update(self, context: UpdateContext) -> dict[str, Any]:
        """Unified update method using deterministic context."""
        # 1. Update from identity
        self.update_from_identity(context.identity_snapshot)

        # 2. Update from autonomy (previous step's autonomy)
        self.update_from_autonomy(context.autonomy_snapshot)

        # 3. Update from culture
        self.update_from_culture(context.culture_snapshot)

        self.discipline_score = max(0.0, min(1.0, 0.5 * self.militarydisciplinescore + 0.3 * self.command_coherence + 0.2 * self.discipline_bias))
        self.ideaqualityscore = max(0.0, min(1.0, 0.5 * self.command_coherence + 0.5 * self.discipline_bias))
        self.execution_priority = max(0.0, min(1.0, 0.6 * self.discipline_score + 0.4 * self.ideaqualityscore))
        # High-urgency tick: ``GlobalTickCoordinator`` promotes agents with this flag in execution order.
        self.override_signal = self.execution_priority >= 0.85

        # 4. Update trace
        snapshot = self.update_trace()

        return {
            "snapshot": self.to_context_snapshot(),
            "trace_snapshot": snapshot
        }

    def to_context_snapshot(self) -> dict[str, Any]:
        """Export state for context propagation."""
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
            "ideaqualityscore": self.ideaqualityscore,
            "idea_quality_score": self.ideaqualityscore,
            "discipline_score": self.discipline_score,
            "execution_priority": self.execution_priority,
            "override_signal": self.override_signal,
        }

    def _get_attr(self, obj: Any, key: str, default: Any) -> Any:
        """Helper to safely get attribute from object or dict."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def update_from_identity(self, identity_core: Any) -> dict[str, float]:
        integrity = float(self._get_attr(identity_core, "identity_integrity", 0.5))
        resistance = float(self._get_attr(identity_core, "drift_resistance", 0.5))
        self.militarydisciplinescore = max(
            0.0,
            min(1.0, 0.6 * integrity + 0.4 * resistance),
        )
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
            "ideaqualityscore": self.ideaqualityscore,
            "idea_quality_score": self.ideaqualityscore,
            "discipline_score": self.discipline_score,
            "execution_priority": self.execution_priority,
            "override_signal": self.override_signal,
        }

    def update_from_autonomy(self, autonomy_engine: Any) -> dict[str, float]:
        alignment = float(self._get_attr(autonomy_engine, "autonomy_level", 0.5))
        # Note: using self.command_coherence for inertia
        self.command_coherence = max(
            0.0,
            min(1.0, 0.7 * self.command_coherence + 0.3 * alignment),
        )
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
            "ideaqualityscore": self.ideaqualityscore,
            "idea_quality_score": self.ideaqualityscore,
            "discipline_score": self.discipline_score,
            "execution_priority": self.execution_priority,
            "override_signal": self.override_signal,
        }

    def update_from_culture(self, culture_engine: Any) -> dict[str, float]:
        if isinstance(culture_engine, dict):
            conflicts = culture_engine.get("norm_conflicts", [])
        else:
            conflicts = get_norm_conflicts(culture_engine)

        count = len(list(conflicts))
        # discipline decays linearly: 0 at ~7 conflicts
        self.discipline_bias = max(
            0.0,
            min(1.0, 1.0 - 0.15 * count),
        )
        return {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
            "ideaqualityscore": self.ideaqualityscore,
            "idea_quality_score": self.ideaqualityscore,
            "discipline_score": self.discipline_score,
            "execution_priority": self.execution_priority,
            "override_signal": self.override_signal,
        }

    def update_trace(self) -> dict[str, Any]:
        entry = {
            "militarydisciplinescore": self.militarydisciplinescore,
            "command_coherence": self.command_coherence,
            "discipline_bias": self.discipline_bias,
            "ideaqualityscore": self.ideaqualityscore,
            "idea_quality_score": self.ideaqualityscore,
            "discipline_score": self.discipline_score,
            "execution_priority": self.execution_priority,
            "override_signal": self.override_signal,
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
    def idea_quality_score(self) -> float:
        return self.ideaqualityscore

    @idea_quality_score.setter
    def idea_quality_score(self, value: float) -> None:
        self.ideaqualityscore = float(value)

    @property
    def military_discipline_score(self) -> float:
        return self.militarydisciplinescore

    @military_discipline_score.setter
    def military_discipline_score(self, value: float) -> None:
        self.militarydisciplinescore = float(value)

    @property
    def militarydiscipline(self) -> float:
        return self.militarydisciplinescore
