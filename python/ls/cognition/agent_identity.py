from __future__ import annotations

from dataclasses import dataclass, field

from ls.cognition.motivation_engine import NeedCategory


@dataclass
class AgentIdentity:
    id: str
    values: dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.01
    simulated_learning_rate_multiplier: float = 0.2

    def value_for(self, category: NeedCategory) -> float:
        """Return identity weight for category, default 1.0 if not set."""
        return self.values.get(category.value, 1.0)

    def update(self, category: NeedCategory, outcome_effect: float, success: bool) -> None:
        """Slowly update value alignment based on accumulated outcomes.

        success + high effect -> reinforce value
        failure -> slightly decay value
        """
        current = self.values.get(category.value, 1.0)
        if success:
            delta = self.learning_rate * max(outcome_effect, 0.0)
        else:
            delta = -self.learning_rate * 0.5
        self.values[category.value] = _clamp01(current + delta)

    def update_real(self, category: NeedCategory, effect: float, baseline: float = 0.0) -> None:
        """Update identity from real outcomes."""
        self._update_value(category, learning_rate=self.learning_rate, effect=effect, baseline=baseline)

    def update_simulated(self, category: NeedCategory, predicted_effect: float, baseline: float = 0.0) -> None:
        """Update identity from counterfactual outcomes with a lower LR."""
        simulated_lr = self.learning_rate * self.simulated_learning_rate_multiplier
        self._update_value(category, learning_rate=simulated_lr, effect=predicted_effect, baseline=baseline)

    def _update_value(self, category: NeedCategory, learning_rate: float, effect: float, baseline: float) -> None:
        current = self.values.get(category.value, 1.0)
        delta = learning_rate * (effect - baseline)
        self.values[category.value] = _clamp01(current + delta)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
