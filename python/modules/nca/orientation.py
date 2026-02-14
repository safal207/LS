from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .assembly import AgentState


@dataclass
class OrientationCenter:
    """Stores identity anchors and preferences for NCA decision-making."""

    identity: str
    invariants: dict[str, Any] = field(default_factory=dict)
    preferences: dict[str, float] = field(default_factory=dict)
    risk_tolerance: float = 0.5
    exploration_ratio: float = 0.3
    impulsiveness: float = 0.2
    stability_preference: float = 0.8

    def update_from_feedback(self, feedback: dict[str, Any]) -> None:
        preference_updates = feedback.get("preference_updates", {})
        for key, delta in preference_updates.items():
            current = float(self.preferences.get(key, 0.0))
            self.preferences[key] = current + float(delta)

        invariant_updates = feedback.get("invariant_updates", {})
        for key, value in invariant_updates.items():
            self.invariants[key] = value

    def compute_self_consistency(self, state: AgentState) -> float:
        invariants = state.self_state.get("invariants", {})
        preferences = state.self_state.get("preferences", {})
        history = state.history[-8:]

        invariant_score = 1.0
        if invariants.get("avoid_idle_loops"):
            idle_count = sum(1 for event in history if event.get("action") == "idle")
            invariant_score = max(0.0, 1.0 - (idle_count / max(1, len(history))))

        progress_pref = float(preferences.get("progress", 1.0))
        stability_pref = float(preferences.get("stability", 0.2))
        preference_score = 0.5
        if progress_pref + stability_pref > 0:
            preference_score = max(0.0, min(1.0, progress_pref / (progress_pref + stability_pref)))

        stability_score = 1.0
        if len(history) >= 2:
            actions = [event.get("action") for event in history]
            switches = sum(1 for i in range(1, len(actions)) if actions[i] != actions[i - 1])
            normalized_switches = switches / max(1, len(actions) - 1)
            stability_score = max(0.0, 1.0 - normalized_switches * self.impulsiveness)

        weighted = (
            0.35 * invariant_score
            + 0.25 * preference_score
            + 0.25 * stability_score
            + 0.15 * self.stability_preference
        )
        return max(0.0, min(1.0, weighted))


    def update_from_collective_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]:
        collective_drift = bool(feedback.get("collective_drift", False))
        collective_progress = float(feedback.get("collective_progress", 0.0))
        goal_conflict = bool(feedback.get("goal_conflict", False))

        if collective_drift:
            self.impulsiveness = max(0.0, self.impulsiveness - 0.08)

        if collective_progress > 0:
            self.stability_preference = min(1.0, self.stability_preference + 0.06)

        signal: dict[str, Any] = {}
        if goal_conflict:
            signal = {
                "signal_type": "collectivegoalconflict",
                "payload": {
                    "identity": self.identity,
                    "collective_progress": collective_progress,
                },
            }
        return signal


    def update_from_self_model(self, self_model: Any) -> None:
        model_dict = self_model.to_dict() if hasattr(self_model, "to_dict") else {}
        drift = float(model_dict.get("identity_drift_score", 0.0))
        predicted = model_dict.get("predicted_state", {}) if isinstance(model_dict, dict) else {}
        predicted_consistency = float(predicted.get("predictedselfconsistency", 1.0)) if isinstance(predicted, dict) else 1.0

        if drift >= 0.35:
            self.stability_preference = min(1.0, self.stability_preference + 0.08)

        if predicted_consistency < 0.45:
            self.impulsiveness = max(0.0, self.impulsiveness - 0.07)

        if drift >= 0.5:
            self.invariants["identity_shift_detected"] = True

    def update_from_metacognition(self, metafeedback: dict[str, Any]) -> None:
        metadrift = float(metafeedback.get("metadrift", metafeedback.get("meta_drift", 0.0)))
        observer_bias_score = float(metafeedback.get("observerbiasscore", 0.0))
        biases = metafeedback.get("biases", [])

        if metadrift > 0.4:
            self.stability_preference = min(1.0, self.stability_preference + 0.08)

        if observer_bias_score > 0.45:
            self.impulsiveness = max(0.0, self.impulsiveness - 0.08)

        if "oscillation_bias" in biases or "oscillation" in biases:
            self.invariants["meta_stabilizer"] = True

        stability_boost = float(metafeedback.get("stability_boost", 0.0))
        if stability_boost > 0:
            self.stability_preference = min(1.0, self.stability_preference + stability_boost)

        impulsiveness_damp = float(metafeedback.get("impulsiveness_damp", 0.0))
        if impulsiveness_damp > 0:
            self.impulsiveness = max(0.0, self.impulsiveness - impulsiveness_damp)

    def update_from_identity_core(self, identity_core: Any) -> None:
        integrity = float(getattr(identity_core, "identity_integrity", 1.0))
        drift_resistance = float(getattr(identity_core, "drift_resistance", 1.0))
        agency_level = float(getattr(identity_core, "agency_level", 0.0))

        if integrity < 0.55:
            self.stability_preference = min(1.0, self.stability_preference + 0.1)

        if drift_resistance < 0.5:
            self.impulsiveness = max(0.0, self.impulsiveness - 0.08)

        if agency_level > 0.6:
            self.exploration_ratio = min(1.0, self.exploration_ratio + 0.08)

    def personality_profile(self) -> dict[str, float]:
        return {
            "risk_tolerance": self.risk_tolerance,
            "exploration_ratio": self.exploration_ratio,
            "impulsiveness": self.impulsiveness,
            "stability_preference": self.stability_preference,
        }

    # Compatibility with requested interface naming.
    def updatefromfeedback(self, feedback: dict[str, Any]) -> None:
        self.update_from_feedback(feedback)

    def updatefromselfmodel(self, selfmodel: Any) -> None:
        self.update_from_self_model(selfmodel)

    def computeselfconsistency(self, state: AgentState) -> float:
        return self.compute_self_consistency(state)

    def updatefromcollective_feedback(self, feedback: dict[str, Any]) -> dict[str, Any]:
        return self.update_from_collective_feedback(feedback)

    def updatefrommetacognition(self, metafeedback: dict[str, Any]) -> None:
        self.update_from_metacognition(metafeedback)

    def updatefromidentitycore(self, identitycore: Any) -> None:
        self.update_from_identity_core(identitycore)
