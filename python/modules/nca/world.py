from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GridWorld:
    """A tiny 1D discrete world for NCA prototype simulations."""

    size: int = 10
    start_position: int = 0
    goal_position: int = 9

    def __post_init__(self) -> None:
        self.agent_position = max(0, min(self.size - 1, self.start_position))
        self.goal_position = max(0, min(self.size - 1, self.goal_position))
        self.t = 0

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
        self.t += 1
        return {
            "t": self.t,
            "position_before": before,
            "position_after": self.agent_position,
            "goal_reached": self.agent_position == self.goal_position,
        }

    def state(self) -> dict[str, int]:
        return {
            "t": self.t,
            "agent_position": self.agent_position,
            "goal_position": self.goal_position,
            "size": self.size,
        }
