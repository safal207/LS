from __future__ import annotations

from dataclasses import dataclass, field

from ls.cognition.motivation_engine import NeedCategory


@dataclass
class AgentIdentity:
    id: str
    values: dict[str, float] = field(default_factory=dict)
    learning_rate: float = 0.01

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


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))

