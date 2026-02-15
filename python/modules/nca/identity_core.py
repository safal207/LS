from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import normalize_traditions, MAX_NORM_CONFLICTS


@dataclass
class IdentityCore:
    """Phase 6 identity kernel for long-term stabilization and initiative generation."""

    core_traits: dict[str, float] = field(
        default_factory=lambda: {
            "consistency": 0.7,
            "adaptability": 0.55,
            "cooperation": 0.6,
            "curiosity": 0.5,
        }
    )
    longtermgoals: list[dict[str, Any]] = field(
        default_factory=lambda: [
            {"name": "preserve_identity", "priority": 0.9},
            {"name": "sustain_progress", "priority": 0.8},
            {"name": "improve_collective_alignment", "priority": 0.65},
        ]
    )
    identity_integrity: float = 0.85
    drift_resistance: float = 0.7
    agency_level: float = 0.45
    intentalignmentscore: float = 1.0
    intent_resistance: float = 0.55
    autonomyalignmentscore: float = 1.0
    autonomy_resistance: float = 0.45
    valuealignmentscore: float = 1.0
    value_resistance: float = 0.4
    socialalignmentscore: float = 1.0
    social_resistance: float = 0.35
    culturalidentityscore: float = 1.0
    cultural_resistance: float = 0.3
    militocracyalignmentscore: float = 1.0
    synergyalignmentscore: float = 1.0
    culturalpreferenceprofile: dict[str, float] = field(
        default_factory=lambda: {
            "cooperation": 0.75,
            "stability": 0.72,
            "tradition": 0.62,
        }
    )
    selfdirectionpreference: dict[str, float] = field(
        default_factory=lambda: {
            "stabilize": 0.7,
            "explore": 0.6,
            "balanced": 0.75,
        }
    )
    intentpreferenceprofile: dict[str, float] = field(
        default_factory=lambda: {
            "stability": 0.7,
            "progress": 0.75,
            "collective": 0.6,
            "exploration": 0.55,
        }
    )
    socialpreferenceprofile: dict[str, float] = field(
        default_factory=lambda: {
            "stability": 0.72,
            "cooperation": 0.78,
            "exploration": 0.58,
            "balanced": 0.8,
        }
    )
    valuepreferenceprofile: dict[str, float] = field(
        default_factory=lambda: {
            "identity_preservation": 0.78,
            "collective_good": 0.66,
            "goal_progress": 0.72,
            "ethical_stability": 0.82,
            "adaptive_learning": 0.58,
        }
    )

    def update_from_self_model(self, self_model: Any) -> None:
        payload = self_model.to_dict() if hasattr(self_model, "to_dict") else {}
        drift = float(payload.get("identity_drift_score", 0.0))
        predicted = payload.get("predicted_state", {}) if isinstance(payload, dict) else {}
        predicted_consistency = float(predicted.get("predictedselfconsistency", 1.0)) if isinstance(predicted, dict) else 1.0
        stability_score = float(payload.get("longterm_stability_score", 1.0))

        self.identity_integrity = max(
            0.0,
            min(
                1.0,
                (0.45 * self.identity_integrity) + (0.3 * predicted_consistency) + (0.25 * stability_score) - (0.35 * drift),
            ),
        )
        self.drift_resistance = max(0.0, min(1.0, (0.6 * self.drift_resistance) + (0.4 * (1.0 - drift))))
        self.agency_level = max(0.0, min(1.0, (0.6 * self.agency_level) + (0.4 * (0.4 + (predicted_consistency * 0.6)))))

    def update_from_meta(self, meta_feedback: dict[str, Any]) -> None:
        metadrift = float(meta_feedback.get("meta_drift", 0.0))
        agency_bias = float(meta_feedback.get("agency_bias", 0.0))
        initiative_conflict = float(meta_feedback.get("initiative_conflict", 0.0))
        identity_integrity_drift = float(meta_feedback.get("identity_integrity_drift", 0.0))

        self.identity_integrity = max(0.0, min(1.0, self.identity_integrity - (0.25 * metadrift) - (0.35 * identity_integrity_drift)))
        self.drift_resistance = max(0.0, min(1.0, self.drift_resistance - (0.2 * metadrift) - (0.3 * initiative_conflict)))
        self.agency_level = max(0.0, min(1.0, self.agency_level + (0.2 * (1.0 - agency_bias)) - (0.2 * initiative_conflict)))
        self.intent_resistance = max(0.0, min(1.0, self.intent_resistance + (0.1 * metadrift) + (0.15 * initiative_conflict)))

    def stabilize_identity(self) -> None:
        if self.identity_integrity < 0.55:
            self.core_traits["consistency"] = min(1.0, self.core_traits.get("consistency", 0.7) + 0.08)
            self.core_traits["adaptability"] = max(0.0, self.core_traits.get("adaptability", 0.55) - 0.04)

        if self.drift_resistance < 0.5:
            self.drift_resistance = min(1.0, self.drift_resistance + 0.06)

        if self.agency_level > 0.75:
            self.core_traits["curiosity"] = min(1.0, self.core_traits.get("curiosity", 0.5) + 0.04)

    def evaluate_integrity(self) -> float:
        trait_floor = min(self.core_traits.values()) if self.core_traits else 1.0
        result = (0.5 * self.identity_integrity) + (0.3 * self.drift_resistance) + (0.2 * trait_floor)
        self.identity_integrity = max(0.0, min(1.0, result))
        return self.identity_integrity

    def generate_initiative(self) -> dict[str, Any]:
        integrity = self.evaluate_integrity()
        if integrity < 0.45:
            mode = "stabilize"
            preferred_actions = ["idle", "forward"]
        elif self.agency_level > 0.65:
            mode = "explore"
            preferred_actions = ["forward", "left", "right"]
        else:
            mode = "balanced"
            preferred_actions = ["forward", "idle"]

        goal = max(self.longtermgoals, key=lambda item: float(item.get("priority", 0.0)), default={"name": "maintain"})
        return {
            "mode": mode,
            "identity_integrity": integrity,
            "agency_level": self.agency_level,
            "drift_resistance": self.drift_resistance,
            "preferred_actions": preferred_actions,
            "primary_goal": goal.get("name", "maintain"),
        }

    def evaluate_intent_compatibility(self, intent: dict[str, Any]) -> float:
        intent_type = str(intent.get("type", "progress")).lower()
        preferred = float(self.intentpreferenceprofile.get(intent_type, 0.6))
        desired_mode = str(intent.get("desired_mode", "balanced")).lower()
        priority = float(intent.get("priority", 0.5))

        consistency = float(self.core_traits.get("consistency", 0.6))
        adaptability = float(self.core_traits.get("adaptability", 0.6))
        cooperation = float(self.core_traits.get("cooperation", 0.6))
        curiosity = float(self.core_traits.get("curiosity", 0.5))

        mode_fit = 0.6
        if desired_mode == "stabilize":
            mode_fit = 0.5 * consistency + 0.5 * self.drift_resistance
        elif desired_mode == "explore":
            mode_fit = 0.55 * curiosity + 0.45 * adaptability
        elif desired_mode == "balanced":
            mode_fit = 0.4 * consistency + 0.3 * adaptability + 0.3 * cooperation

        resistance_penalty = self.intent_resistance * max(0.0, priority - self.agency_level)
        score = max(
            0.0,
            min(
                1.0,
                (0.4 * preferred) + (0.4 * mode_fit) + (0.2 * self.identity_integrity) - (0.2 * resistance_penalty),
            ),
        )
        self.intentalignmentscore = score
        return score

    def evaluate_strategy_compatibility(self, strategy: dict[str, Any] | None) -> float:
        if not strategy:
            self.autonomyalignmentscore = 0.5
            return self.autonomyalignmentscore

        mode = str(strategy.get("mode", "balanced")).lower()
        preference = float(self.selfdirectionpreference.get(mode, 0.6))
        alignment = float(strategy.get("alignment", 0.5))
        strength = float(strategy.get("strength", 0.5))
        consistency = float(self.core_traits.get("consistency", 0.6))
        adaptability = float(self.core_traits.get("adaptability", 0.6))

        mode_fit = 0.6 * consistency + 0.4 * self.drift_resistance if mode == "stabilize" else 0.55 * adaptability + 0.45 * self.agency_level if mode == "explore" else 0.4 * consistency + 0.3 * adaptability + 0.3 * self.identity_integrity
        resistance_penalty = self.autonomy_resistance * max(0.0, strength - self.agency_level)

        self.autonomyalignmentscore = max(0.0, min(1.0, (0.35 * preference) + (0.3 * alignment) + (0.2 * mode_fit) + (0.15 * self.identity_integrity) - (0.2 * resistance_penalty)))
        return self.autonomyalignmentscore

    def evaluate_value_compatibility(self, values: Any) -> float:
        if values is None:
            self.valuealignmentscore = 0.5
            return self.valuealignmentscore

        core_values = dict(getattr(values, "core_values", {}))
        if not core_values:
            self.valuealignmentscore = 0.5
            return self.valuealignmentscore

        combined = 0.0
        total = 0.0
        for name, preference in self.valuepreferenceprofile.items():
            combined += float(preference) * float(core_values.get(name, preference))
            total += float(preference)

        normalized = combined / total if total > 0 else 0.5
        resistance_penalty = self.value_resistance * max(0.0, 1.0 - normalized)
        self.valuealignmentscore = max(0.0, min(1.0, normalized - (0.2 * resistance_penalty)))
        return self.valuealignmentscore


    def evaluate_social_compatibility(self, social_engine: Any) -> float:
        if social_engine is None:
            self.socialalignmentscore = 0.5
            return self.socialalignmentscore

        cooperation = float(getattr(social_engine, "cooperation_score", 0.5))
        conflict = float(getattr(social_engine, "socialconflictscore", 0.0))
        intent_alignment = float(getattr(social_engine, "collectiveintentalignment", 0.5))

        preference_fit = (
            0.45 * float(self.socialpreferenceprofile.get("cooperation", 0.7))
            + 0.3 * float(self.socialpreferenceprofile.get("balanced", 0.7))
            + 0.25 * float(self.socialpreferenceprofile.get("stability", 0.7))
        )
        resistance_penalty = self.social_resistance * max(0.0, conflict - cooperation)
        self.socialalignmentscore = max(
            0.0,
            min(
                1.0,
                (0.35 * cooperation) + (0.3 * intent_alignment) + (0.2 * self.identity_integrity) + (0.15 * preference_fit) - (0.2 * resistance_penalty),
            ),
        )
        return self.socialalignmentscore

    def evaluatesocialcompatibility(self, social_engine: Any) -> float:
        return self.evaluate_social_compatibility(social_engine)


    def evaluate_cultural_compatibility(self, culture_engine: Any) -> float:
        if culture_engine is None:
            self.culturalidentityscore = 0.5
            return self.culturalidentityscore

        norms = dict(getattr(culture_engine, "norms", {}))
        # Use shared normalization
        traditions = normalize_traditions(getattr(culture_engine, "traditions", {}))

        conflicts = getattr(culture_engine, "norm_conflicts", getattr(culture_engine, "normconflicts", []))
        conflict = min(1.0, len(list(conflicts)) / MAX_NORM_CONFLICTS)

        cooperation_fit = float(norms.get("cooperation", self.culturalpreferenceprofile.get("cooperation", 0.7)))
        stability_fit = float(norms.get("stability", self.culturalpreferenceprofile.get("stability", 0.7)))
        tradition_fit = 1.0 if traditions else self.culturalpreferenceprofile.get("tradition", 0.6)

        base = (0.35 * cooperation_fit) + (0.3 * stability_fit) + (0.2 * tradition_fit) + (0.15 * self.identity_integrity)
        penalty = 0.2 * self.cultural_resistance * conflict
        self.culturalidentityscore = max(0.0, min(1.0, base - penalty))
        return self.culturalidentityscore

    def evaluateculturalcompatibility(self, culture_engine: Any) -> float:
        return self.evaluate_cultural_compatibility(culture_engine)


    def evaluate_militocracy_compatibility(self, militocracy_engine: Any) -> float:
        if militocracy_engine is None:
            self.militocracyalignmentscore = 0.5
            return self.militocracyalignmentscore

        discipline = float(getattr(militocracy_engine, "militarydisciplinescore", 0.5))
        command = float(getattr(militocracy_engine, "command_coherence", 0.5))
        resistance_penalty = self.intent_resistance * max(0.0, command - self.agency_level)
        self.militocracyalignmentscore = max(
            0.0,
            min(1.0, (0.45 * discipline) + (0.35 * command) + (0.2 * self.identity_integrity) - (0.15 * resistance_penalty)),
        )
        return self.militocracyalignmentscore

    def evaluatemilitocracycompatibility(self, militocracy_engine: Any) -> float:
        return self.evaluate_militocracy_compatibility(militocracy_engine)

    def evaluate_synergy_compatibility(self, synergy_engine: Any) -> float:
        if synergy_engine is None:
            self.synergyalignmentscore = 0.5
            return self.synergyalignmentscore

        synergy_index = float(getattr(synergy_engine, "synergy_index", 0.5))
        efficiency = float(getattr(synergy_engine, "cooperative_efficiency", 0.5))
        self.synergyalignmentscore = max(
            0.0,
            min(1.0, (0.45 * synergy_index) + (0.35 * efficiency) + (0.2 * self.socialalignmentscore)),
        )
        return self.synergyalignmentscore

    def evaluatesynergycompatibility(self, synergy_engine: Any) -> float:
        return self.evaluate_synergy_compatibility(synergy_engine)

    # Compatibility aliases requested by specification.
    def updatefromselfmodel(self, selfmodel: Any) -> None:
        self.update_from_self_model(selfmodel)

    def updatefrommeta(self, meta_feedback: dict[str, Any]) -> None:
        self.update_from_meta(meta_feedback)

    def stabilizeidentity(self) -> None:
        self.stabilize_identity()

    def evaluateintegrity(self) -> float:
        return self.evaluate_integrity()

    def generateinitiative(self) -> dict[str, Any]:
        return self.generate_initiative()

    def evaluateintentcompatibility(self, intent: dict[str, Any]) -> float:
        return self.evaluate_intent_compatibility(intent)

    def evaluatestrategycompatibility(self, strategy: dict[str, Any] | None) -> float:
        return self.evaluate_strategy_compatibility(strategy)

    def evaluatevaluecompatibility(self, values: Any) -> float:
        return self.evaluate_value_compatibility(values)

    def evaluatesocialcompatibilityalias(self, social_engine: Any) -> float:
        return self.evaluate_social_compatibility(social_engine)
