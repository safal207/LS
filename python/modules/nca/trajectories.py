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
    uncertainty: float = 0.0
    confidence: float = 1.0


class TrajectoryPlanner:
    """Generates and ranks action trajectories for the next agent step."""

    def generate(self, world: GridWorld, state: AgentState) -> list[TrajectoryOption]:
        options: list[TrajectoryOption] = []
        for action in world.available_actions():
            projected = world.project(action)
            uncertainty = self.estimate_uncertainty(state, [action])
            options.append(
                TrajectoryOption(
                    action=action,
                    score=0.0,
                    uncertainty=uncertainty,
                    details={"projected_position": projected},
                )
            )
        return options

    def estimate_uncertainty(self, state: AgentState, actions: list[str]) -> float:
        world_noise = float(state.world_state.get("noise_level", 0.0))
        observation_uncertainty = float(state.world_state.get("observation_uncertainty", 0.0))
        risk = 0.0
        for action in actions:
            if action == "idle":
                risk += 0.15
            elif action in ("left", "right"):
                risk += 0.08
            else:
                risk += 0.12
        risk /= max(1, len(actions))
        return max(0.0, min(1.0, (0.45 * world_noise) + (0.35 * observation_uncertainty) + (0.2 * risk)))

    def evaluate(self, options: list[TrajectoryOption], state: AgentState) -> list[TrajectoryOption]:
        prefs = state.self_state.get("preferences", {})
        personality = state.self_state.get("personality", {})
        micro_goals = state.self_state.get("micro_goals", [])
        progress_weight = float(prefs.get("progress", 1.0))
        stability_weight = float(prefs.get("stability", 0.2))
        risk_tolerance = float(personality.get("risk_tolerance", 0.5))
        exploration_ratio = float(personality.get("exploration_ratio", 0.3))

        evaluated: list[TrajectoryOption] = []
        for option in options:
            projected_pos = option.details["projected_position"]
            target = state.world_state.get("goal_position", projected_pos)
            distance = abs(target - projected_pos)
            progress_score = -distance
            stability_penalty = -1.0 if option.action == "idle" else 0.0

            micro_goal_bonus = 0.0
            for goal in micro_goals:
                if projected_pos == goal.get("target_position"):
                    micro_goal_bonus += 0.6

            base_score = (
                (progress_weight * progress_score)
                + (stability_weight * stability_penalty)
                + micro_goal_bonus
                + (exploration_ratio * (0.2 if option.action != "idle" else -0.1))
            )
            uncertainty_penalty = option.uncertainty * (1.0 - risk_tolerance)
            score = base_score - uncertainty_penalty

            invariant_fit = 1.0
            invariants = state.self_state.get("invariants", {})
            if invariants.get("avoid_idle_loops") and option.action == "idle":
                invariant_fit = 0.3

            micro_goal_fit = 0.5 if micro_goals else 0.8
            if micro_goals:
                micro_goal_fit = 1.0 if micro_goal_bonus > 0 else 0.4

            confidence = max(
                0.0,
                min(
                    1.0,
                    (1.0 - option.uncertainty) * 0.5
                    + invariant_fit * 0.25
                    + micro_goal_fit * 0.25,
                ),
            )

            details = dict(option.details)
            details["confidence"] = confidence
            details["uncertainty_penalty"] = uncertainty_penalty
            evaluated.append(
                TrajectoryOption(
                    action=option.action,
                    score=score,
                    details=details,
                    uncertainty=option.uncertainty,
                    confidence=confidence,
                )
            )
        return evaluated

    def choose(self, evaluated: list[TrajectoryOption]) -> TrajectoryOption:
        if not evaluated:
            return TrajectoryOption(action="idle", score=0.0, details={})
        return max(evaluated, key=lambda item: item.score)

    # Compatibility alias for requested naming.
    def estimateuncertainty(self, state: AgentState, actions: list[str]) -> float:
        return self.estimate_uncertainty(state, actions)
