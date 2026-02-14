from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .assembly import AgentState
from .causal import CausalGraph
from .world import GridWorld


@dataclass
class TrajectoryOption:
    """Single candidate action and its projected utility score."""

    action: str
    score: float
    details: dict[str, Any]
    uncertainty: float = 0.0
    confidence: float = 1.0
    causal_score: float = 0.0


class TrajectoryPlanner:
    """Generates and ranks action trajectories for the next agent step."""

    def __init__(self, *, causal_graph: CausalGraph | None = None, causal_weight: float = 0.3, self_alignment_weight: float = 0.2, meta_alignment_weight: float = 0.15, initiative_weight: float = 0.12, intent_weight: float = 0.18) -> None:
        self.causal_graph = causal_graph or CausalGraph()
        self.causal_weight = causal_weight
        self.self_alignment_weight = self_alignment_weight
        self.meta_alignment_weight = meta_alignment_weight
        self.initiative_weight = initiative_weight
        self.intent_weight = intent_weight

    def generate(self, world: GridWorld, state: AgentState, initiative: dict[str, Any] | None = None, intent: dict[str, Any] | None = None) -> list[TrajectoryOption]:
        options: list[TrajectoryOption] = []
        for action in world.available_actions():
            projected = world.project(action)
            uncertainty = self.estimate_uncertainty(state, [action])
            causal_score = self.evaluate_causal_score(action, state)
            options.append(
                TrajectoryOption(
                    action=action,
                    score=0.0,
                    uncertainty=uncertainty,
                    causal_score=causal_score,
                    details={"projected_position": projected, "causal_score": causal_score, "initiative": dict(initiative or {}), "intent": dict(intent or {})},
                )
            )
        return options

    def evaluate_causal_score(self, option: str, state: AgentState) -> float:
        world_features = state.world_state.get("causal_features", {}) if isinstance(state.world_state, dict) else {}
        feature_for_action = world_features.get(option, {}) if isinstance(world_features, dict) else {}
        success = float(feature_for_action.get("success_probability", 0.5))
        error = float(feature_for_action.get("error_probability", 0.0))
        drift = float(feature_for_action.get("deviation_probability", 0.0))

        effect = self.causal_graph.estimate_causal_effect(option)
        predicted = self.causal_graph.predict_outcome(option)
        historical_success = float(predicted.get("success_probability", 0.0))
        historical_drift = float(predicted.get("drift_probability", 0.0))

        # Reward historically progressive actions and penalize drift-prone ones.
        return (0.45 * effect) + (0.25 * (success - error - drift)) + (0.2 * historical_success) - (0.3 * historical_drift)

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

    def evaluate(
        self,
        options: list[TrajectoryOption],
        state: AgentState,
        collective_state: dict[str, Any] | None = None,
        self_model: Any | None = None,
        metafeedback: dict[str, Any] | None = None,
        initiative: dict[str, Any] | None = None,
        intent: dict[str, Any] | None = None,
    ) -> list[TrajectoryOption]:
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
            causal_score = option.causal_score
            collective_score = self.evaluate_collective_score(option, state, collective_state or {})
            self_alignment_score = self.evaluate_self_alignment(option, state, self_model)
            meta_alignment_score = self.evaluate_meta_alignment(option, state, self_model, metafeedback or {})
            initiative_score = self.evaluate_initiative(option, initiative)
            intent_score = self.evaluate_intent(option, intent)
            score = (
                base_score
                + (causal_score * self.causal_weight)
                + (collective_score * 0.25)
                + (self_alignment_score * self.self_alignment_weight)
                + (meta_alignment_score * self.meta_alignment_weight)
                + (initiative_score * self.initiative_weight)
                + (intent_score * self.intent_weight)
                - uncertainty_penalty
            )

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
            details["causal_score"] = causal_score
            details["collective_score"] = collective_score
            details["self_alignment_score"] = self_alignment_score
            details["meta_alignment_score"] = meta_alignment_score
            details["initiative_score"] = initiative_score
            details["intent_score"] = intent_score
            evaluated.append(
                TrajectoryOption(
                    action=option.action,
                    score=score,
                    details=details,
                    uncertainty=option.uncertainty,
                    confidence=confidence,
                    causal_score=causal_score,
                )
            )
        return evaluated




    def evaluate_intent(self, option: TrajectoryOption, intent: dict[str, Any] | None) -> float:
        if not intent:
            return 0.0

        preferred_actions = intent.get("preferred_actions", [])
        strength = float(intent.get("strength", 0.0))
        alignment = float(intent.get("alignment", 0.5))
        desired_mode = str(intent.get("desired_mode", "balanced"))

        score = 0.0
        if option.action in preferred_actions:
            score += 0.45

        if desired_mode == "stabilize" and option.action == "idle":
            score += 0.18
        elif desired_mode == "explore" and option.action in ("forward", "left", "right"):
            score += 0.18

        score += 0.22 * strength
        score += 0.15 * alignment
        return score

    def evaluateintent(self, option: TrajectoryOption, intent: dict[str, Any] | None) -> float:
        return self.evaluate_intent(option, intent)

    def evaluate_initiative(self, option: TrajectoryOption, initiative: dict[str, Any] | None) -> float:
        if not initiative:
            return 0.0

        preferred = initiative.get("preferred_actions", [])
        mode = str(initiative.get("mode", "balanced"))
        agency_level = float(initiative.get("agency_level", 0.0))
        integrity = float(initiative.get("identity_integrity", 1.0))

        score = 0.0
        if option.action in preferred:
            score += 0.5

        if mode == "stabilize" and option.action == "idle":
            score += 0.2
        if mode == "explore" and option.action in ("left", "right", "forward"):
            score += 0.2

        score += 0.2 * agency_level
        score += 0.1 * integrity
        return score

    def evaluateinitiative(self, option: TrajectoryOption, initiative: dict[str, Any] | None) -> float:
        return self.evaluate_initiative(option, initiative)

    def evaluate_meta_alignment(
        self,
        option: TrajectoryOption,
        state: AgentState,
        self_model: Any | None,
        metafeedback: dict[str, Any],
    ) -> float:
        _ = state
        _ = self_model
        if not metafeedback:
            return 0.0

        metadrift = float(metafeedback.get("meta_drift", 0.0))
        observer_bias = float(metafeedback.get("orientation_corrections", {}).get("observerbiasscore", 0.0))
        biases = metafeedback.get("biases", [])

        score = 0.4 * (1.0 - metadrift) - 0.25 * observer_bias
        if option.action == "idle" and "repeated_drift" in biases:
            score -= 0.25
        if option.action in ("left", "right") and "oscillation_bias" in biases:
            score -= 0.1
        if option.action == "forward" and metadrift < 0.3:
            score += 0.08
        return score

    def evaluatemetaalignment(self, option: TrajectoryOption, state: AgentState, selfmodel: Any | None, metafeedback: dict[str, Any]) -> float:
        return self.evaluate_meta_alignment(option, state, selfmodel, metafeedback)

    def evaluate_self_alignment(self, option: TrajectoryOption, agent_state: AgentState, self_model: Any | None) -> float:
        if self_model is None:
            return 0.0

        model_dict = self_model.to_dict() if hasattr(self_model, "to_dict") else {}
        drift = float(model_dict.get("identity_drift_score", 0.0))
        predicted = model_dict.get("predicted_state", {}) if isinstance(model_dict, dict) else {}
        predicted_consistency = float(predicted.get("predictedselfconsistency", 1.0)) if isinstance(predicted, dict) else 1.0

        action_penalty = 0.0
        if option.action == "idle" and drift > 0.2:
            action_penalty -= drift
        if option.action in ("left", "right") and predicted_consistency < 0.5:
            action_penalty -= 0.2

        consistency_reward = (predicted_consistency - 0.5) * 0.8
        drift_penalty = -0.7 * drift
        return consistency_reward + drift_penalty + action_penalty

    def evaluateselfalignment(self, option: TrajectoryOption, agentstate: AgentState, selfmodel: Any | None) -> float:
        return self.evaluate_self_alignment(option, agentstate, selfmodel)

    def evaluate_collective_score(
        self,
        option: TrajectoryOption,
        agent_state: AgentState,
        collective_state: dict[str, Any],
    ) -> float:
        if not collective_state:
            return 0.0

        positions = collective_state.get("agent_positions", {})
        projected_pos = int(option.details.get("projected_position", 0))
        self_pos = int(agent_state.world_state.get("agent_position", projected_pos)) if isinstance(agent_state.world_state, dict) else projected_pos

        collision_penalty = 0.0
        for agent_id, position in positions.items():
            _ = agent_id
            if int(position) == projected_pos and projected_pos != self_pos:
                collision_penalty -= 0.6

        progress_boost = 0.2 if option.action != "idle" else -0.1
        shared = collective_state.get("shared_causal", {})
        by_action = shared.get("by_action", {}) if isinstance(shared, dict) else {}
        shared_action = by_action.get(option.action, {}) if isinstance(by_action, dict) else {}
        effect = float(shared_action.get("collective_effect", 0.0))
        drift = float(shared_action.get("collective_drift", 0.0))

        return progress_boost + (0.35 * effect) - (0.5 * drift) + collision_penalty

    def evaluatecollectivescore(
        self,
        option: TrajectoryOption,
        agentstate: AgentState,
        collectivestate: dict[str, Any],
    ) -> float:
        return self.evaluate_collective_score(option, agentstate, collectivestate)

    def choose(self, evaluated: list[TrajectoryOption]) -> TrajectoryOption:
        if not evaluated:
            return TrajectoryOption(action="idle", score=0.0, details={})
        return max(evaluated, key=lambda item: item.score)

    # Compatibility alias for requested naming.
    def estimateuncertainty(self, state: AgentState, actions: list[str]) -> float:
        return self.estimate_uncertainty(state, actions)

    def evaluatecausalscore(self, option: str, state: AgentState) -> float:
        return self.evaluate_causal_score(option, state)
