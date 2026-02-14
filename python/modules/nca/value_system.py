from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValueSystem:
    """Phase 9 internal values, preference evolution, and ethics regulator."""

    core_values: dict[str, float] = field(
        default_factory=lambda: {
            "identity_preservation": 0.75,
            "collective_good": 0.65,
            "goal_progress": 0.7,
            "ethical_stability": 0.8,
            "adaptive_learning": 0.55,
        }
    )
    valuealignmentscore: float = 1.0
    ethical_constraints: dict[str, float] = field(
        default_factory=lambda: {
            "avoid_harm": 0.8,
            "avoid_chaotic_actions": 0.65,
            "preserve_identity": 0.75,
        }
    )
    preference_drift: float = 0.0
    value_conflicts: list[dict[str, Any]] = field(default_factory=list)
    collectivevaluealignment: float = 1.0
    collectiveethicalconflict: float = 0.0
    groupvaluemap: dict[str, dict[str, Any]] = field(default_factory=dict)
    value_trace: list[dict[str, Any]] = field(default_factory=list)
    culturalvaluealignment: float = 1.0
    normethicsmap: dict[str, float] = field(default_factory=dict)
    traditionvaluemap: dict[str, float] = field(default_factory=dict)

    def update_from_identity(self, identity_core: Any) -> None:
        integrity = float(getattr(identity_core, "identity_integrity", 1.0))
        drift_resistance = float(getattr(identity_core, "drift_resistance", 1.0))
        agency_level = float(getattr(identity_core, "agency_level", 0.5))

        self.core_values["identity_preservation"] = max(
            0.0,
            min(1.0, (0.6 * self.core_values.get("identity_preservation", 0.75)) + (0.4 * integrity)),
        )
        self.core_values["ethical_stability"] = max(
            0.0,
            min(1.0, (0.55 * self.core_values.get("ethical_stability", 0.8)) + (0.45 * drift_resistance)),
        )
        self.core_values["adaptive_learning"] = max(
            0.0,
            min(1.0, (0.5 * self.core_values.get("adaptive_learning", 0.55)) + (0.5 * agency_level)),
        )

    def update_from_intents(self, intent_engine: Any) -> None:
        intent_alignment = float(getattr(intent_engine, "intent_alignment", 1.0))
        intent_strength = float(getattr(intent_engine, "intent_strength", 0.0))
        conflicts = list(getattr(intent_engine, "intent_conflicts", []))

        self.core_values["goal_progress"] = max(
            0.0,
            min(1.0, (0.65 * self.core_values.get("goal_progress", 0.7)) + (0.35 * intent_strength)),
        )
        self.core_values["collective_good"] = max(
            0.0,
            min(1.0, (0.7 * self.core_values.get("collective_good", 0.65)) + (0.3 * intent_alignment)),
        )
        conflict_penalty = min(0.25, 0.08 * len(conflicts))
        self.valuealignmentscore = max(0.0, min(1.0, self.valuealignmentscore - conflict_penalty))

    def update_from_autonomy(self, autonomy_engine: Any) -> None:
        autonomy_level = float(getattr(autonomy_engine, "autonomy_level", 0.5))
        ethical_alignment = float(getattr(autonomy_engine, "ethicalalignmentscore", 1.0))

        self.core_values["adaptive_learning"] = max(
            0.0,
            min(1.0, (0.6 * self.core_values.get("adaptive_learning", 0.55)) + (0.4 * autonomy_level)),
        )
        self.valuealignmentscore = max(
            0.0,
            min(1.0, (0.65 * self.valuealignmentscore) + (0.35 * ethical_alignment)),
        )


    def update_from_collective(self, collective_state: dict[str, Any] | None) -> None:
        collective_state = collective_state or {}
        self.groupvaluemap = dict(collective_state.get("collectivevaluemap", self.groupvaluemap))
        self.collectivevaluealignment = float(collective_state.get("collectivevaluealignment", self.collectivevaluealignment))
        self.collectiveethicalconflict = float(collective_state.get("collectiveethicalconflict", self.collectiveethicalconflict))

        self.core_values["collective_good"] = max(
            0.0,
            min(1.0, (0.6 * self.core_values.get("collective_good", 0.65)) + (0.4 * self.collectivevaluealignment)),
        )
        self.valuealignmentscore = max(
            0.0,
            min(1.0, self.valuealignmentscore - (0.18 * self.collectiveethicalconflict) + (0.12 * self.collectivevaluealignment)),
        )
        self.culturalvaluealignment = max(0.0, min(1.0, (0.6 * self.collectivevaluealignment) + (0.4 * self.core_values.get("collective_good", 0.65))))
        self.normethicsmap = {
            "cooperation": self.core_values.get("collective_good", 0.65),
            "stability": self.core_values.get("ethical_stability", 0.8),
            "identity": self.core_values.get("identity_preservation", 0.75),
        }
        self.traditionvaluemap = {
            "learning": self.core_values.get("adaptive_learning", 0.55),
            "progress": self.core_values.get("goal_progress", 0.7),
        }

    def evaluate_value_alignment(
        self,
        action: dict[str, Any] | None,
        intent: dict[str, Any] | None,
        strategy: dict[str, Any] | None,
    ) -> float:
        action_name = str((action or {}).get("action", (action or {}).get("name", ""))).lower()
        intent_mode = str((intent or {}).get("desired_mode", "balanced")).lower()
        strategy_mode = str((strategy or {}).get("mode", "balanced")).lower()

        score = 0.45 * self.core_values.get("ethical_stability", 0.8)
        score += 0.2 * self.core_values.get("identity_preservation", 0.75)
        score += 0.15 * self.core_values.get("collective_good", 0.65)
        score += 0.2 * self.core_values.get("goal_progress", 0.7)

        if action_name == "idle" and self.ethical_constraints.get("avoid_chaotic_actions", 0.65) > 0.6:
            score += 0.04
        if {intent_mode, strategy_mode} == {"stabilize", "explore"}:
            score -= 0.16

        if action_name in ("left", "right") and self.ethical_constraints.get("avoid_harm", 0.8) > 0.75:
            score -= 0.04

        self.valuealignmentscore = max(0.0, min(1.0, score))
        return self.valuealignmentscore

    def resolve_value_conflicts(self) -> list[dict[str, Any]]:
        self.value_conflicts = []
        progress = self.core_values.get("goal_progress", 0.7)
        stability = self.core_values.get("ethical_stability", 0.8)
        learning = self.core_values.get("adaptive_learning", 0.55)

        if progress > 0.8 and stability < 0.5:
            self.value_conflicts.append({"type": "progress_vs_stability", "severity": progress - stability})
            self.core_values["goal_progress"] = max(0.0, progress - 0.05)
            self.core_values["ethical_stability"] = min(1.0, stability + 0.06)

        if learning > 0.75 and self.core_values.get("identity_preservation", 0.75) < 0.55:
            self.value_conflicts.append(
                {
                    "type": "adaptation_vs_identity",
                    "severity": learning - self.core_values.get("identity_preservation", 0.75),
                }
            )
            self.core_values["adaptive_learning"] = max(0.0, learning - 0.04)
            self.core_values["identity_preservation"] = min(1.0, self.core_values.get("identity_preservation", 0.75) + 0.05)

        return self.value_conflicts

    def evolve_preferences(self) -> dict[str, float]:
        baseline = sum(self.core_values.values()) / max(1, len(self.core_values))
        last = self.value_trace[-1]["valuealignmentscore"] if self.value_trace else baseline
        self.preference_drift = max(0.0, min(1.0, abs(baseline - float(last))))

        if self.preference_drift > 0.12:
            self.core_values["ethical_stability"] = min(1.0, self.core_values.get("ethical_stability", 0.8) + 0.03)
        else:
            self.core_values["adaptive_learning"] = min(1.0, self.core_values.get("adaptive_learning", 0.55) + 0.01)

        self.resolve_value_conflicts()
        self.value_trace.append(
            {
                "t": len(self.value_trace),
                "collectivevaluealignment": self.collectivevaluealignment,
                "collectiveethicalconflict": self.collectiveethicalconflict,
                "core_values": dict(self.core_values),
                "valuealignmentscore": self.valuealignmentscore,
                "preference_drift": self.preference_drift,
                "value_conflicts": [dict(c) for c in self.value_conflicts],
                "culturalvaluealignment": self.culturalvaluealignment,
                "normethicsmap": dict(self.normethicsmap),
                "traditionvaluemap": dict(self.traditionvaluemap),
            }
        )
        if len(self.value_trace) > 200:
            self.value_trace = self.value_trace[-200:]
        return dict(self.core_values)

    def updatefromidentity(self, identity_core: Any) -> None:
        self.update_from_identity(identity_core)

    def updatefromintents(self, intent_engine: Any) -> None:
        self.update_from_intents(intent_engine)

    def updatefromautonomy(self, autonomy_engine: Any) -> None:
        self.update_from_autonomy(autonomy_engine)

    def updatefromcollective(self, collective_state: dict[str, Any] | None) -> None:
        self.update_from_collective(collective_state)

    def evaluatevaluealignment(self, action: dict[str, Any] | None, intent: dict[str, Any] | None, strategy: dict[str, Any] | None) -> float:
        return self.evaluate_value_alignment(action, intent, strategy)

    def evaluatevalue_alignment(self, action: dict[str, Any] | None, intent: dict[str, Any] | None, strategy: dict[str, Any] | None) -> float:
        return self.evaluate_value_alignment(action, intent, strategy)

    def resolvevalueconflicts(self) -> list[dict[str, Any]]:
        return self.resolve_value_conflicts()

