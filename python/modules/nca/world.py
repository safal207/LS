from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


@dataclass
class GridWorld:
    """A tiny 1D discrete world for NCA prototype simulations."""

    size: int = 10
    start_position: int = 0
    goal_position: int = 9
    noise_level: float = 0.0

    def __post_init__(self) -> None:
        self.agent_position = max(0, min(self.size - 1, self.start_position))
        self.goal_position = max(0, min(self.size - 1, self.goal_position))
        self.t = 0
        self._rng = random.Random(42)
        self._last_position = self.agent_position

    def available_actions(self) -> list[str]:
        return ["left", "right", "idle"]

    def project(self, action: str) -> int:
        if action == "left":
            return max(0, self.agent_position - 1)
        if action == "right":
            return min(self.size - 1, self.agent_position + 1)
        return self.agent_position

    def step(self, action: str) -> dict[str, int | bool]:
        before = self.agent_position
        self.agent_position = self.project(action)
        self._last_position = before
        self.t += 1
        return {
            "t": self.t,
            "position_before": before,
            "position_after": self.agent_position,
            "goal_reached": self.agent_position == self.goal_position,
        }

    def apply_noise(self, observations: dict[str, Any]) -> dict[str, Any]:
        noisy = dict(observations)
        if self.noise_level <= 0:
            noisy["observation_uncertainty"] = 0.0
            return noisy

        if self._rng.random() < self.noise_level:
            shift = self._rng.choice([-1, 1])
            noisy["agent_position"] = max(0, min(self.size - 1, noisy["agent_position"] + shift))

        if self._rng.random() < self.noise_level * 0.4:
            noisy.pop("goal_position", None)

        if self._rng.random() < self.noise_level * 0.5:
            noisy["false_signal"] = self._rng.choice(["phantom_obstacle", "echo", "decoy_goal"])

        noisy["observation_uncertainty"] = min(1.0, self.noise_level + self._rng.random() * 0.2)
        return noisy

    def state(self) -> dict[str, Any]:
        base = {
            "t": self.t,
            "agent_position": self.agent_position,
            "goal_position": self.goal_position,
            "size": self.size,
            "noise_level": self.noise_level,
            "previous_agent_position": self._last_position,
        }
        return self.apply_noise(base)

    # Compatibility alias for requested naming.
    def applynoise(self, observations: dict[str, Any]) -> dict[str, Any]:
        return self.apply_noise(observations)
