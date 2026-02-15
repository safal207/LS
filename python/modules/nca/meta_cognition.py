from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetaCognitionEngine:
    """Recursive meta-cognition layer for bias detection and self-correction."""

    max_history: int = 120
    correction_strength: float = 0.06
    history: list[dict[str, Any]] = field(default_factory=list)
    latest_feedback: dict[str, Any] = field(default_factory=dict)
    intent_drift: float = 0.0
    intent_bias: float = 0.0
    intentconflictscore: float = 0.0
    autonomy_drift: float = 0.0
    autonomy_bias: float = 0.0
    selfdirectionconflict: float = 0.0
    value_drift: float = 0.0
    value_bias: float = 0.0
    ethicalconflictscore: float = 0.0
    social_drift: float = 0.0
    cooperation_bias: float = 0.0
    groupconflictscore: float = 0.0
    cultural_drift: float = 0.0
    culturalconflictbias: float = 0.0
    civilizationstabilityscore: float = 1.0

    def analyze_cognition(self, state: Any, self_model: Any, meta_report: Any) -> dict[str, Any]:
        model_dict = self_model.to_dict() if hasattr(self_model, "to_dict") else {}
        model_drift = float(model_dict.get("identity_drift_score", 0.0))
        cognitive_trace = model_dict.get("cognitive_trace", {}) if isinstance(model_dict, dict) else {}
        cognitive_patterns = model_dict.get("cognitive_patterns", []) if isinstance(model_dict, dict) else []

        report_dict = self._normalize_report(meta_report)
        agency_markers = model_dict.get("agency_markers", []) if isinstance(model_dict, dict) else []
        intent_trace = model_dict.get("intent_trace", []) if isinstance(model_dict, dict) else []
        intent_conflicts = model_dict.get("intentconflictmarkers", []) if isinstance(model_dict, dict) else []
        autonomy_trace = model_dict.get("autonomy_trace", []) if isinstance(model_dict, dict) else []
        selfdirection_markers = model_dict.get("selfdirectionmarkers", []) if isinstance(model_dict, dict) else []
        longterm_stability_score = float(model_dict.get("longterm_stability_score", model_dict.get("longtermstability_score", 1.0))) if isinstance(model_dict, dict) else 1.0
        value_trace = model_dict.get("value_trace", []) if isinstance(model_dict, dict) else []
        ethical_markers = model_dict.get("ethical_markers", []) if isinstance(model_dict, dict) else []
        social_trace = model_dict.get("social_trace", []) if isinstance(model_dict, dict) else []
        cooperation_markers = model_dict.get("cooperation_markers", []) if isinstance(model_dict, dict) else []
        self_consistency = float(report_dict.get("self_consistency", 1.0))
        observer_bias_score = float(report_dict.get("observerbiasscore", 0.0))
        observer_meta_drift = float(report_dict.get("meta_drift", 0.0))

        agency_bias = 0.0
        if agency_markers:
            low_markers = sum(1 for m in agency_markers[-8:] if str(m.get("agency_signal", "")) == "low")
            agency_bias = low_markers / max(1, len(agency_markers[-8:]))

        initiative_conflict = 0.0
        if observer_meta_drift > 0.45 and model_drift > 0.4:
            initiative_conflict = min(1.0, (observer_meta_drift + model_drift) / 2.0)

        identity_integrity_drift = max(0.0, min(1.0, 1.0 - longterm_stability_score))

        self.intent_drift = 0.0
        self.intent_bias = 0.0
        self.intentconflictscore = 0.0
        if intent_trace:
            recent_intents = intent_trace[-8:]
            self.intent_drift = sum(max(0.0, 1.0 - float(i.get("intent_alignment", 1.0))) for i in recent_intents) / max(1, len(recent_intents))
            self.intent_bias = sum(float(i.get("intent_strength", 0.0)) for i in recent_intents) / max(1, len(recent_intents))
        if intent_conflicts:
            recent_conflicts = intent_conflicts[-8:]
            self.intentconflictscore = sum(float(i.get("conflict_score", 0.0)) for i in recent_conflicts) / max(1, len(recent_conflicts))

        self.autonomy_drift = 0.0
        self.autonomy_bias = 0.0
        self.selfdirectionconflict = 0.0
        if autonomy_trace:
            recent_autonomy = autonomy_trace[-8:]
            self.autonomy_drift = sum(max(0.0, 1.0 - float(a.get("autonomy_level", 1.0))) for a in recent_autonomy) / max(1, len(recent_autonomy))
            self.selfdirectionconflict = sum(min(1.0, float(a.get("conflict_count", 0.0)) / 3.0) for a in recent_autonomy) / max(1, len(recent_autonomy))
        if selfdirection_markers:
            recent_markers = selfdirection_markers[-8:]
            low_signals = sum(1 for m in recent_markers if str(m.get("autonomy_signal", "")) == "low")
            self.autonomy_bias = low_signals / max(1, len(recent_markers))

        self.value_drift = 0.0
        self.value_bias = 0.0
        self.ethicalconflictscore = 0.0
        if value_trace:
            recent_values = value_trace[-8:]
            self.value_drift = sum(float(v.get("preference_drift", 0.0)) for v in recent_values) / max(1, len(recent_values))
            self.value_bias = sum(max(0.0, 1.0 - float(v.get("valuealignmentscore", 1.0))) for v in recent_values) / max(1, len(recent_values))
            self.ethicalconflictscore = sum(min(1.0, float(v.get("conflict_count", 0.0)) / 3.0) for v in recent_values) / max(1, len(recent_values))
        if ethical_markers:
            recent_markers = ethical_markers[-8:]
            warning_ratio = sum(1 for marker in recent_markers if str(marker.get("ethical_signal", "stable")) == "warning") / max(1, len(recent_markers))
            self.value_bias = max(self.value_bias, warning_ratio)

        self.social_drift = 0.0
        self.cooperation_bias = 0.0
        self.groupconflictscore = 0.0
        if social_trace:
            recent_social = social_trace[-8:]
            self.social_drift = sum(max(0.0, 1.0 - float(v.get("cooperation_score", 1.0))) for v in recent_social) / max(1, len(recent_social))
            self.groupconflictscore = sum(float(v.get("socialconflictscore", 0.0)) for v in recent_social) / max(1, len(recent_social))
        if cooperation_markers:
            recent_coop = cooperation_markers[-8:]
            low_signals = sum(1 for marker in recent_coop if str(marker.get("cooperation_signal", "moderate")) == "low")
            self.cooperation_bias = low_signals / max(1, len(recent_coop))

        self.cultural_drift = max(0.0, min(1.0, (0.5 * self.social_drift) + (0.5 * self.value_drift)))
        self.culturalconflictbias = max(0.0, min(1.0, (0.6 * self.groupconflictscore) + (0.4 * self.ethicalconflictscore)))
        self.civilizationstabilityscore = max(0.0, min(1.0, 1.0 - ((0.6 * self.cultural_drift) + (0.4 * self.culturalconflictbias))))

        biases = self.detect_cognitive_biases(
            {
                "state": state,
                "selfmodeldrift": model_drift,
                "meta_report": report_dict,
                "cognitive_trace": cognitive_trace,
                "cognitive_patterns": cognitive_patterns,
                "agency_bias": agency_bias,
                "initiative_conflict": initiative_conflict,
                "identity_integrity_drift": identity_integrity_drift,
                "intent_drift": self.intent_drift,
                "intent_bias": self.intent_bias,
                "intent_conflict_score": self.intentconflictscore,
                "autonomy_drift": self.autonomy_drift,
                "autonomy_bias": self.autonomy_bias,
                "selfdirectionconflict": self.selfdirectionconflict,
                "value_drift": self.value_drift,
                "value_bias": self.value_bias,
                "ethicalconflictscore": self.ethicalconflictscore,
                "social_drift": self.social_drift,
                "cooperation_bias": self.cooperation_bias,
                "cultural_drift": self.cultural_drift,
                "culturalconflictbias": self.culturalconflictbias,
                "civilizationstabilityscore": self.civilizationstabilityscore,
                "groupconflictscore": self.groupconflictscore,
            }
        )

        metadrift = max(
            0.0,
            min(
                1.0,
                (0.35 * model_drift)
                + (0.25 * observer_meta_drift)
                + (0.15 * max(0.0, 1.0 - self_consistency))
                + (0.15 * identity_integrity_drift)
                + (0.1 * initiative_conflict)
                + (0.08 * self.intent_drift)
                + (0.07 * self.intentconflictscore)
                + (0.08 * self.autonomy_drift)
                + (0.06 * self.selfdirectionconflict)
                + (0.08 * self.value_drift)
                + (0.07 * self.ethicalconflictscore)
                + (0.08 * self.cultural_drift)
            ),
        )

        planner_corrections = {
            "metaalignmentweight": 0.15,
            "risk_penalty": 0.1 if metadrift > 0.45 else 0.0,
            "idle_penalty": 0.12 if "impulsiveness_spike" in biases else 0.0,
            "exploration_damp": 0.08 if "oscillation_bias" in biases else 0.0,
            "initiative_damp": 0.08 if initiative_conflict > 0.45 else 0.0,
            "intent_damp": 0.1 if self.intentconflictscore > 0.35 else 0.0,
            "autonomy_damp": 0.1 if self.selfdirectionconflict > 0.35 else 0.0,
            "value_damp": 0.1 if self.ethicalconflictscore > 0.35 else 0.0,
        }
        observer_corrections = {
            "raise_thresholds": metadrift > 0.55,
            "observerbiasscore": observer_bias_score,
            "meta_consistency_target": max(0.45, 1.0 - metadrift),
        }
        orientation_corrections = {
            "metadrift": metadrift,
            "observerbiasscore": observer_bias_score,
            "biases": list(biases),
            "stability_boost": 0.08 if metadrift > 0.4 else 0.02,
            "impulsiveness_damp": 0.06 if observer_bias_score > 0.45 else 0.0,
            "initiative_conflict": initiative_conflict,
            "intent_drift": self.intent_drift,
            "intent_bias": self.intent_bias,
            "intentconflictscore": self.intentconflictscore,
            "autonomy_drift": self.autonomy_drift,
            "autonomy_bias": self.autonomy_bias,
            "selfdirectionconflict": self.selfdirectionconflict,
            "value_drift": self.value_drift,
            "value_bias": self.value_bias,
            "ethicalconflictscore": self.ethicalconflictscore,
            "social_drift": self.social_drift,
            "cooperation_bias": self.cooperation_bias,
            "cultural_drift": self.cultural_drift,
            "culturalconflictbias": self.culturalconflictbias,
            "civilizationstabilityscore": self.civilizationstabilityscore,
            "groupconflictscore": self.groupconflictscore,
        }

        feedback = {
            "biases": biases,
            "meta_drift": metadrift,
            "planner_corrections": planner_corrections,
            "observer_corrections": observer_corrections,
            "orientation_corrections": orientation_corrections,
            "agency_bias": agency_bias,
            "initiative_conflict": initiative_conflict,
            "identity_integrity_drift": identity_integrity_drift,
            "intent_drift": self.intent_drift,
            "intent_bias": self.intent_bias,
            "intentconflictscore": self.intentconflictscore,
            "autonomy_drift": self.autonomy_drift,
            "autonomy_bias": self.autonomy_bias,
            "selfdirectionconflict": self.selfdirectionconflict,
            "value_drift": self.value_drift,
            "value_bias": self.value_bias,
            "ethicalconflictscore": self.ethicalconflictscore,
            "social_drift": self.social_drift,
            "cooperation_bias": self.cooperation_bias,
            "cultural_drift": self.cultural_drift,
            "culturalconflictbias": self.culturalconflictbias,
            "civilizationstabilityscore": self.civilizationstabilityscore,
            "groupconflictscore": self.groupconflictscore,
        }
        self.latest_feedback = feedback
        self.history.append(feedback)
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history :]
        return feedback

    @property
    def latestfeedback(self) -> dict[str, Any]:
        """Compatibility alias for compact-name integrations."""
        return self.latest_feedback

    def _normalize_report(self, meta_report: Any) -> dict[str, Any]:
        if isinstance(meta_report, dict):
            return dict(meta_report)
        if hasattr(meta_report, "__dict__"):
            return {k: getattr(meta_report, k) for k in vars(meta_report)}
        return {}

    def detect_cognitive_biases(self, history: Any) -> list[str]:
        if isinstance(history, dict):
            trace = history.get("cognitive_trace", {})
            report = history.get("meta_report", {})
            model_drift = float(history.get("selfmodeldrift", 0.0))
            patterns = history.get("cognitive_patterns", [])
            agency_bias = float(history.get("agency_bias", 0.0))
            initiative_conflict = float(history.get("initiative_conflict", 0.0))
            identity_integrity_drift = float(history.get("identity_integrity_drift", 0.0))
            intent_drift = float(history.get("intent_drift", 0.0))
            intent_bias = float(history.get("intent_bias", 0.0))
            intent_conflict_score = float(history.get("intent_conflict_score", history.get("intentconflictscore", 0.0)))
            autonomy_drift = float(history.get("autonomy_drift", 0.0))
            autonomy_bias = float(history.get("autonomy_bias", 0.0))
            selfdirectionconflict = float(history.get("selfdirectionconflict", 0.0))
            value_drift = float(history.get("value_drift", 0.0))
            value_bias = float(history.get("value_bias", 0.0))
            ethicalconflictscore = float(history.get("ethicalconflictscore", 0.0))
            social_drift = float(history.get("social_drift", 0.0))
            cooperation_bias = float(history.get("cooperation_bias", 0.0))
            groupconflictscore = float(history.get("groupconflictscore", 0.0))
        else:
            trace = {}
            report = {}
            model_drift = 0.0
            patterns = []
            agency_bias = 0.0
            initiative_conflict = 0.0
            identity_integrity_drift = 0.0
            intent_drift = 0.0
            intent_bias = 0.0
            intent_conflict_score = 0.0
            autonomy_drift = 0.0
            autonomy_bias = 0.0
            selfdirectionconflict = 0.0
            value_drift = 0.0
            value_bias = 0.0
            ethicalconflictscore = 0.0
            social_drift = 0.0
            cooperation_bias = 0.0
            groupconflictscore = 0.0

        biases: list[str] = []
        if float(trace.get("impulsiveness_spikes", 0.0)) > 0.18:
            biases.append("impulsiveness_spike")
        if float(trace.get("over_correction", 0.0)) > 0.16:
            biases.append("over_correction")
        if float(trace.get("oscillation", 0.0)) > 0.18:
            biases.append("oscillation_bias")
        if float(trace.get("repeated_drift", 0.0)) > 0.2 or model_drift > 0.45:
            biases.append("repeated_drift")
        if float(report.get("meta_drift", 0.0)) > 0.35:
            biases.append("meta_drift")
        if agency_bias > 0.5:
            biases.append("agency_bias")
        if initiative_conflict > 0.4:
            biases.append("initiative_conflict")
        if identity_integrity_drift > 0.35:
            biases.append("identity_integrity_drift")
        if intent_drift > 0.3:
            biases.append("intent_drift")
        if intent_conflict_score > 0.3:
            biases.append("intent_conflict")
        if intent_bias > 0.75:
            biases.append("intent_bias")
        if autonomy_drift > 0.3:
            biases.append("autonomy_drift")
        if autonomy_bias > 0.5:
            biases.append("autonomy_bias")
        if selfdirectionconflict > 0.35:
            biases.append("selfdirection_conflict")
        if value_drift > 0.25:
            biases.append("value_drift")
        if value_bias > 0.45:
            biases.append("value_bias")
        if ethicalconflictscore > 0.3:
            biases.append("ethical_conflict")
        if social_drift > 0.3:
            biases.append("social_drift")
        if cooperation_bias > 0.5:
            biases.append("cooperation_bias")
        if groupconflictscore > 0.35:
            biases.append("group_conflict")

        for pattern in patterns[-6:]:
            label = str(pattern.get("pattern", "")).lower()
            if label and label not in biases:
                biases.append(label)

        return biases

    def suggest_corrections(self) -> dict[str, Any]:
        if not self.latest_feedback:
            return {
                "planner": {},
                "observer": {},
                "orientation": {},
            }
        return {
            "planner": dict(self.latest_feedback.get("planner_corrections", {})),
            "observer": dict(self.latest_feedback.get("observer_corrections", {})),
            "orientation": dict(self.latest_feedback.get("orientation_corrections", {})),
        }

    def apply_corrections(self, agent: Any) -> dict[str, Any]:
        corrections = self.suggest_corrections()
        orientation_feedback = corrections.get("orientation", {})

        planner_patch = corrections.get("planner", {})
        if hasattr(agent, "planner") and planner_patch:
            current_meta_weight = float(getattr(agent.planner, "meta_alignment_weight", 0.15))
            agent.planner.meta_alignment_weight = float(planner_patch.get("metaalignmentweight", current_meta_weight))

        if hasattr(agent, "meta_observer"):
            observer_patch = corrections.get("observer", {})
            if observer_patch.get("raise_thresholds"):
                current = float(getattr(agent.meta_observer, "self_consistency_threshold", 0.45))
                agent.meta_observer.self_consistency_threshold = max(0.35, min(0.7, current + self.correction_strength))

        if hasattr(agent, "orientation") and orientation_feedback:
            agent.orientation.update_from_metacognition(orientation_feedback)

        return corrections

    # Compatibility aliases requested by specification.
    def analyzecognition(self, state: Any, selfmodel: Any, meta_report: Any) -> dict[str, Any]:
        return self.analyze_cognition(state, selfmodel, meta_report)

    def detectcognitivebiases(self, history: Any) -> list[str]:
        return self.detect_cognitive_biases(history)

    def suggest_corrections_alias(self) -> dict[str, Any]:
        return self.suggest_corrections()

    def applycorrections(self, agent: Any) -> dict[str, Any]:
        return self.apply_corrections(agent)
