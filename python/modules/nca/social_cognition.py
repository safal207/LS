from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import normalize_traditions, MAX_TRACE_LENGTH


@dataclass
class SocialCognitionEngine:
    """Models other agents and computes cooperative social alignment signals."""

    social_models: dict[str, dict[str, Any]] = field(default_factory=dict)
    collectivevaluealignment: float = 1.0
    collectiveintentalignment: float = 1.0
    socialconflictscore: float = 0.0
    cooperation_score: float = 0.6
    group_norms: dict[str, float] = field(default_factory=dict)
    tradition_patterns: dict[str, Any] = field(default_factory=dict)
    culturalsimilarityscore: float = 0.6
    collaboration_index: float = 0.6
    conflict_index: float = 0.0
    social_trace: list[dict[str, Any]] = field(default_factory=list)

    def update_from_collective_state(self, collective: dict[str, Any] | None) -> dict[str, Any]:
        collective = collective or {}
        self.collectivevaluealignment = float(collective.get("collectivevaluealignment", self.collectivevaluealignment))
        self.collectiveintentalignment = float(collective.get("collectiveintentalignment", self.collectiveintentalignment))

        # Determine social conflict score first as it's used in cooperation inference
        self.socialconflictscore = max(
            0.0,
            min(
                1.0,
                max(
                    float(collective.get("collectivesocialconflict", 0.0)),
                    float(collective.get("collectiveintentconflict", 0.0)),
                    float(collective.get("collectiveethicalconflict", 0.0)),
                ),
            ),
        )

        # Use normalized key collectivecooperationscore, fallback only to self
        collective_cooperation = float(
            collective.get(
                "collectivecooperationscore",
                self.cooperation_score
            )
        )

        inferred_cooperation = max(
            0.0,
            min(
                1.0,
                (0.4 * self.collectivevaluealignment)
                + (0.35 * self.collectiveintentalignment)
                + (0.25 * (1.0 - self.socialconflictscore)),
            ),
        )

        # Update cooperation score based on pre-calculated inputs
        self.cooperation_score = max(0.0, min(1.0, 0.6 * collective_cooperation + 0.4 * inferred_cooperation))

        self.group_norms = {
            "cooperation": self.cooperation_score,
            "stability": 1.0 - self.socialconflictscore,
            "coordination": self.collectiveintentalignment,
        }

        # Normalize incoming traditions
        self.tradition_patterns = normalize_traditions(collective.get("collectivetraditionpatterns", {}))

        self.culturalsimilarityscore = max(
            0.0,
            min(1.0, (0.45 * self.collectivevaluealignment) + (0.35 * self.collectiveintentalignment) + (0.2 * (1.0 - self.socialconflictscore))),
        )
        self.collaboration_index = self.cooperation_score
        self.conflict_index = self.socialconflictscore
        snapshot = {
            "t": len(self.social_trace),
            "collectivevaluealignment": self.collectivevaluealignment,
            "collectiveintentalignment": self.collectiveintentalignment,
            "socialconflictscore": self.socialconflictscore,
            "cooperation_score": self.cooperation_score,
            "group_norms": dict(self.group_norms),
            "tradition_patterns": dict(self.tradition_patterns),
            "culturalsimilarityscore": self.culturalsimilarityscore,
            "model_count": len(self.social_models),
        }
        self.social_trace.append(snapshot)
        if len(self.social_trace) > MAX_TRACE_LENGTH:
            self.social_trace = self.social_trace[-MAX_TRACE_LENGTH:]
        return snapshot

    def infer_other_agents_intents(self, events: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
        for event in events or []:
            agent_id = str(event.get("agent_id", event.get("sourceagentid", event.get("agent", "unknown"))))
            model = self.social_models.setdefault(agent_id, {})
            primary_intent = event.get("primary_intent", event.get("primaryintent", {})) if isinstance(event, dict) else {}
            if primary_intent:
                model["intent"] = dict(primary_intent)
                model["intent_alignment"] = float(primary_intent.get("alignment", model.get("intent_alignment", 0.6)))
                model["intent_strength"] = float(primary_intent.get("strength", model.get("intent_strength", 0.5)))
        return self.social_models

    def infer_other_agents_values(self, events: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
        for event in events or []:
            agent_id = str(event.get("agent_id", event.get("sourceagentid", event.get("agent", "unknown"))))
            model = self.social_models.setdefault(agent_id, {})
            value_block = event.get("values", {}) if isinstance(event, dict) else {}
            if value_block:
                core_values = value_block.get("core_values", value_block.get("corevalues", {}))
                model["values"] = dict(core_values) if isinstance(core_values, dict) else {}
                model["valuealignmentscore"] = float(value_block.get("valuealignmentscore", value_block.get("value_alignment", model.get("valuealignmentscore", 0.6))))
        return self.social_models

    def evaluate_social_alignment(self, self_agent: Any, others: dict[str, Any] | None) -> float:
        others = others or {}
        self_values = dict(getattr(getattr(self_agent, "values", None), "core_values", {}))
        self_intent = getattr(getattr(self_agent, "intentengine", None), "select_primary_intent", lambda: {})() or {}
        self_intent_mode = str(self_intent.get("desired_mode", "balanced"))

        value_fit_scores: list[float] = []
        intent_fit_scores: list[float] = []

        for model in self.social_models.values():
            other_values = dict(model.get("values", {}))
            if self_values and other_values:
                overlap = [1.0 - abs(float(self_values.get(k, 0.5)) - float(v)) for k, v in other_values.items() if k in self_values]
                if overlap:
                    value_fit_scores.append(sum(overlap) / len(overlap))
            other_mode = str(model.get("intent", {}).get("desired_mode", "balanced"))
            if other_mode == self_intent_mode:
                intent_fit_scores.append(1.0)
            elif {self_intent_mode, other_mode} == {"stabilize", "explore"}:
                intent_fit_scores.append(0.35)
            else:
                intent_fit_scores.append(0.65)

        value_fit = sum(value_fit_scores) / max(1, len(value_fit_scores)) if value_fit_scores else self.collectivevaluealignment
        intent_fit = sum(intent_fit_scores) / max(1, len(intent_fit_scores)) if intent_fit_scores else self.collectiveintentalignment
        collective_penalty = float(others.get("collectivesocialconflict", self.socialconflictscore))

        alignment = max(0.0, min(1.0, (0.4 * value_fit) + (0.35 * intent_fit) + (0.25 * (1.0 - collective_penalty))))
        self.cooperation_score = max(0.0, min(1.0, (0.65 * self.cooperation_score) + (0.35 * alignment)))
        return alignment

    def generate_cooperative_adjustments(self) -> dict[str, Any]:
        conflict_pressure = max(0.0, min(1.0, 1.0 - self.cooperation_score))
        adjustment = {
            "prefer_balanced_modes": conflict_pressure > 0.35,
            "deescalate_competitive_actions": conflict_pressure > 0.45,
            "cooperation_boost": max(0.0, min(0.25, 0.3 * self.cooperation_score)),
            "social_conflict_penalty": max(0.0, min(0.3, 0.35 * self.socialconflictscore)),
            "shared_action_preference": ["forward", "idle"] if self.cooperation_score >= 0.55 else ["idle", "forward"],
        }
        return adjustment

    def predict_group_behavior(self) -> dict[str, Any]:
        dominant_mode = "balanced"
        mode_scores = {"stabilize": 0, "explore": 0, "balanced": 0}
        for model in self.social_models.values():
            mode = str(model.get("intent", {}).get("desired_mode", "balanced"))
            if mode in mode_scores:
                mode_scores[mode] += 1
        if sum(mode_scores.values()) > 0:
            dominant_mode = max(mode_scores, key=mode_scores.get)

        return {
            "dominant_mode": dominant_mode,
            "cooperation_score": self.cooperation_score,
            "socialconflictscore": self.socialconflictscore,
            "collectivevaluealignment": self.collectivevaluealignment,
            "collectiveintentalignment": self.collectiveintentalignment,
            "group_norms": dict(self.group_norms),
            "tradition_patterns": dict(self.tradition_patterns),
        }

    # Compatibility aliases requested by specification.
    def updatefromcollective_state(self, collective: dict[str, Any] | None) -> dict[str, Any]:
        return self.update_from_collective_state(collective)

    def updatefromcollectivestate(self, collective: dict[str, Any] | None) -> dict[str, Any]:
        return self.update_from_collective_state(collective)

    def inferotheragents_intents(self, events: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
        return self.infer_other_agents_intents(events)

    def inferotheragents_values(self, events: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
        return self.infer_other_agents_values(events)

    def evaluatesocialalignment(self, self_agent: Any, others: dict[str, Any] | None) -> float:
        return self.evaluate_social_alignment(self_agent, others)

    def generatecooperativeadjustments(self) -> dict[str, Any]:
        return self.generate_cooperative_adjustments()

    def generatecooperative_adjustments(self) -> dict[str, Any]:
        return self.generate_cooperative_adjustments()

    def predictgroupbehavior(self) -> dict[str, Any]:
        return self.predict_group_behavior()
