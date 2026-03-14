from __future__ import annotations

from dataclasses import dataclass



@dataclass
class CognitiveEnergyModel:
    """Computes cycle-level cognitive energy and per-goal allocations."""

    decay_factor: float = 0.9
    allocation_threshold: float = 0.02
    base_energy: float = 0.2
    ce: float = 0.5

    def compute_cycle_energy(
        self,
        *,
        focus: float,
        stress: float,
        momentum_bonus: float,
        resonance_bonus: float,
    ) -> float:
        base = self.base_energy + (focus * (1.0 - stress)) + momentum_bonus + resonance_bonus
        self.ce = _clamp01(base)
        return self.ce

    def allocate_for_goal(self, ce: float, alignment: float, attractor_influence: float) -> float:
        # Keep attractor in a positive gain band [0, 1] for multiplicative allocation.
        attractor_gain = _clamp01(0.5 + (0.5 * attractor_influence))
        return _clamp01(ce * _clamp01(alignment) * attractor_gain)

    def is_goal_activated(self, ce_goal: float, threshold: float | None = None) -> bool:
        return ce_goal >= (threshold if threshold is not None else self.allocation_threshold)

    def decay(self) -> float:
        self.ce = _clamp01(self.ce * self.decay_factor)
        return self.ce



def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
