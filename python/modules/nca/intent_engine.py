from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class IntentEngine:
    """Builds and manages emergent intentions from internal and world state."""

    active_intents: list[dict[str, Any]] = field(default_factory=list)
    intent_history: list[dict[str, Any]] = field(default_factory=list)
    intent_conflicts: list[dict[str, Any]] = field(default_factory=list)
    intent_strength: float = 0.0
    intent_alignment: float = 1.0

    def generate_intents(self, state: Any, identity_core: Any, self_model: Any) -> list[dict[str, Any]]:
        world_state = getattr(state, "world_state", {}) if hasattr(state, "world_state") else {}
        if not isinstance(world_state, dict):
            world_state = {}

        model_payload = self_model.to_dict() if hasattr(self_model, "to_dict") else {}
        drift = float(model_payload.get("identity_drift_score", 0.0))
        meta_drift = float(model_payload.get("meta_drift_score", 0.0))

        distance_to_goal = abs(int(world_state.get("goal_position", 0)) - int(world_state.get("agent_position", 0)))
        integrity = float(getattr(identity_core, "identity_integrity", 1.0))
        agency = float(getattr(identity_core, "agency_level", 0.0))

        intents: list[dict[str, Any]] = [
            {
                "name": "preserve_identity",
                "type": "stability",
                "desired_mode": "stabilize",
                "priority": max(0.2, 0.55 + (0.4 * drift) + (0.3 * meta_drift)),
                "preferred_actions": ["idle", "forward"],
            },
            {
                "name": "reach_goal",
                "type": "progress",
                "desired_mode": "explore" if distance_to_goal > 1 else "balanced",
                "priority": max(0.2, 0.5 + min(0.35, distance_to_goal * 0.05) + (0.2 * agency)),
                "preferred_actions": ["forward", "left", "right"],
            },
            {
                "name": "improve_collective_alignment",
                "type": "collective",
                "desired_mode": "balanced",
                "priority": max(0.2, 0.45 + (0.3 * (1.0 - integrity))),
                "preferred_actions": ["forward", "idle"],
            },
        ]

        for intent in intents:
            alignment = self.evaluate_intent_alignment(intent, identity_core)
            intent["alignment"] = alignment
            intent["strength"] = max(0.0, min(1.0, float(intent["priority"]) * (0.6 + (0.4 * alignment))))

        self.active_intents = intents
        self.resolve_conflicts()

        if self.active_intents:
            self.intent_strength = sum(float(i.get("strength", 0.0)) for i in self.active_intents) / len(self.active_intents)
            self.intent_alignment = sum(float(i.get("alignment", 0.0)) for i in self.active_intents) / len(self.active_intents)
        else:
            self.intent_strength = 0.0
            self.intent_alignment = 1.0

        snapshot = {
            "t": int(getattr(state, "t", len(self.intent_history))),
            "active_intents": [dict(i) for i in self.active_intents],
            "intent_strength": self.intent_strength,
            "intent_alignment": self.intent_alignment,
            "intent_conflicts": [dict(c) for c in self.intent_conflicts],
        }
        self.intent_history.append(snapshot)
        if len(self.intent_history) > 200:
            self.intent_history = self.intent_history[-200:]
        return self.active_intents

    def evaluate_intent_alignment(self, intent: dict[str, Any], identity_core: Any) -> float:
        if hasattr(identity_core, "evaluate_intent_compatibility"):
            return float(identity_core.evaluate_intent_compatibility(intent))
        return 0.5

    def resolve_conflicts(self) -> list[dict[str, Any]]:
        self.intent_conflicts = []
        for idx, left in enumerate(self.active_intents):
            for right in self.active_intents[idx + 1 :]:
                left_mode = str(left.get("desired_mode", "balanced"))
                right_mode = str(right.get("desired_mode", "balanced"))
                mode_conflict = {left_mode, right_mode} == {"stabilize", "explore"}
                if not mode_conflict:
                    continue
                conflict = {
                    "left": str(left.get("name", "unknown")),
                    "right": str(right.get("name", "unknown")),
                    "severity": abs(float(left.get("priority", 0.0)) - float(right.get("priority", 0.0))),
                    "type": "mode_conflict",
                }
                self.intent_conflicts.append(conflict)

                weaker = left if float(left.get("strength", 0.0)) < float(right.get("strength", 0.0)) else right
                weaker["strength"] = max(0.0, float(weaker.get("strength", 0.0)) - 0.15)

        return self.intent_conflicts

    def select_primary_intent(self) -> dict[str, Any] | None:
        if not self.active_intents:
            return None
        return max(
            self.active_intents,
            key=lambda intent: float(intent.get("strength", 0.0)) * (0.6 + (0.4 * float(intent.get("alignment", 0.0)))),
        )

    # Compatibility aliases requested by specification.
    def generateintents(self, state: Any, identitycore: Any, self_model: Any) -> list[dict[str, Any]]:
        return self.generate_intents(state, identitycore, self_model)

    def evaluateintentalignment(self, intent: dict[str, Any], identity_core: Any) -> float:
        return self.evaluate_intent_alignment(intent, identity_core)

    def selectprimaryintent(self) -> dict[str, Any] | None:
        return self.select_primary_intent()
