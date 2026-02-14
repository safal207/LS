from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .assembly import AgentState
from .world import GridWorld


@dataclass
class TrajectoryOption:
    """Single candidate action and its projected utility score."""

    action: str
    score: float
    details: dict[str, Any]


class TrajectoryPlanner:
    """Generates and ranks action trajectories for the next agent step."""

    def generate(self, world: GridWorld, state: AgentState) -> list[TrajectoryOption]:
        options: list[TrajectoryOption] = []
        for action in world.available_actions():
            projected = world.project(action)
            options.append(
                TrajectoryOption(
                    action=action,
                    score=0.0,
                    details={"projected_position": projected},
                )
            )
        return options

    def evaluate(self, options: list[TrajectoryOption], state: AgentState) -> list[TrajectoryOption]:
        prefs = state.self_state.get("preferences", {})
        progress_weight = float(prefs.get("progress", 1.0))
        stability_weight = float(prefs.get("stability", 0.2))

        evaluated: list[TrajectoryOption] = []
        for option in options:
            projected_pos = option.details["projected_position"]
            target = state.world_state.get("goal_position", projected_pos)
            distance = abs(target - projected_pos)
            progress_score = -distance
            stability_penalty = -1.0 if option.action == "idle" else 0.0
            score = (progress_weight * progress_score) + (stability_weight * stability_penalty)
            evaluated.append(
                TrajectoryOption(action=option.action, score=score, details=dict(option.details))
            )
        return evaluated

    def choose(self, evaluated: list[TrajectoryOption]) -> TrajectoryOption:
        if not evaluated:
            return TrajectoryOption(action="idle", score=0.0, details={})
        return max(evaluated, key=lambda item: item.score)
