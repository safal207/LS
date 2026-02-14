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
    slippery_zone: tuple[int, ...] = ()
    blocked_zone: tuple[int, ...] = ()
    reward_zone: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        self.agent_position = max(0, min(self.size - 1, self.start_position))
        self.goal_position = max(0, min(self.size - 1, self.goal_position))
        self.t = 0
        self._rng = random.Random(42)
        self._last_position = self.agent_position
        if not self.slippery_zone:
            self.slippery_zone = (max(1, self.size // 3),)
        if not self.blocked_zone:
            self.blocked_zone = (max(2, (self.size // 2) - 1),)
        if not self.reward_zone:
            self.reward_zone = (max(1, self.goal_position - 1), self.goal_position)

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
        projected = self.project(action)
        if projected in self.blocked_zone and action != "idle":
            projected = before
        elif projected in self.slippery_zone and action != "idle" and self._rng.random() < 0.35:
            projected = max(0, min(self.size - 1, projected + self._rng.choice([-1, 1])))
        self.agent_position = projected
        self._last_position = before
        self.t += 1
        return {
            "t": self.t,
            "position_before": before,
            "position_after": self.agent_position,
            "goal_reached": self.agent_position == self.goal_position,
        }

    def causal_features(self) -> dict[str, dict[str, float]]:
        features: dict[str, dict[str, float]] = {}
        for action in self.available_actions():
            projected = self.project(action)
            success_probability = 0.75
            error_probability = 0.05
            deviation_probability = 0.05

            if action == "idle":
                success_probability = 0.15
                deviation_probability = 0.2
            if projected in self.slippery_zone:
                success_probability -= 0.2
                deviation_probability += 0.35
            if projected in self.blocked_zone and action != "idle":
                success_probability -= 0.45
                error_probability += 0.35
            if projected in self.reward_zone:
                success_probability += 0.2

            features[action] = {
                "success_probability": max(0.0, min(1.0, success_probability)),
                "error_probability": max(0.0, min(1.0, error_probability)),
                "deviation_probability": max(0.0, min(1.0, deviation_probability)),
            }
        return features

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
            "slippery_zone": list(self.slippery_zone),
            "blocked_zone": list(self.blocked_zone),
            "reward_zone": list(self.reward_zone),
            "causal_features": self.causal_features(),
        }
        return self.apply_noise(base)

    # Compatibility alias for requested naming.
    def applynoise(self, observations: dict[str, Any]) -> dict[str, Any]:
        return self.apply_noise(observations)

    def causalfeatures(self) -> dict[str, dict[str, float]]:
        return self.causal_features()
