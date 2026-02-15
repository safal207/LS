from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .utils import MAX_TRACE_LENGTH, MAX_NORM_CONFLICTS


@dataclass
class AutonomyEngine:
    """Builds self-directed strategies and tracks autonomy stability."""

    autonomy_level: float = 0.5
    strategy_profile: dict[str, Any] = field(default_factory=dict)
    selfdirectedgoals: list[dict[str, Any]] = field(default_factory=list)
    autonomy_conflicts: list[dict[str, Any]] = field(default_factory=list)
    autonomy_trace: list[dict[str, Any]] = field(default_factory=list)
    ethicalalignmentscore: float = 1.0
    selfregulationstrength: float = 0.5
    cooperativealignmentscore: float = 1.0
    groupstrategyadjustment: dict[str, Any] = field(default_factory=dict)
    civilizationalignmentscore: float = 1.0
    normcompliancefactor: float = 1.0
    culturalstrategyadjustment: dict[str, Any] = field(default_factory=dict)

    def generate_strategies(
        self,
        identitycore: Any,
        intentengine: Any,
        metacognition: Any,
        values: Any | None = None,
        culture: Any | None = None,
        militocracy: Any | None = None,
        synergy: Any | None = None,
    ) -> list[dict[str, Any]]:
        integrity = float(getattr(identitycore, "identity_integrity", 1.0))
        agency = float(getattr(identitycore, "agency_level", 0.0))
        drift_resistance = float(getattr(identitycore, "drift_resistance", 1.0))
        intent_alignment = float(getattr(intentengine, "intent_alignment", 1.0))
        intent_strength = float(getattr(intentengine, "intent_strength", 0.0))
        meta_drift = float(getattr(metacognition, "latest_feedback", {}).get("meta_drift", 0.0))
        value_alignment = float(getattr(values, "valuealignmentscore", 1.0)) if values is not None else 1.0
        value_map = dict(getattr(values, "core_values", {})) if values is not None else {}

        self.autonomy_level = max(
            0.0,
            min(
                1.0,
                (0.27 * integrity)
                + (0.24 * agency)
                + (0.14 * drift_resistance)
                + (0.15 * intent_alignment)
                + (0.1 * (1.0 - meta_drift))
                + (0.1 * value_alignment),
            ),
        )

        self.ethicalalignmentscore = max(0.0, min(1.0, value_alignment))
        self.selfregulationstrength = max(0.0, min(1.0, (0.5 * drift_resistance) + (0.5 * self.ethicalalignmentscore)))

        culture_alignment = float(getattr(culture, "culturalalignmentscore", 1.0)) if culture is not None else 1.0

        # Use property or fallback
        if hasattr(culture, "conflicts"):
            conflicts = culture.conflicts
        else:
            conflicts = getattr(culture, "norm_conflicts", getattr(culture, "normconflicts", [])) if culture is not None else []

        self.civilizationalignmentscore = culture_alignment
        self.normcompliancefactor = max(0.0, min(1.0, 1.0 - min(1.0, len(list(conflicts)) / MAX_NORM_CONFLICTS)))
        self.culturalstrategyadjustment = {
            "stability_bias": 0.1 if culture_alignment < 0.55 else 0.0,
            "cooperation_bias": 0.12 if culture_alignment > 0.7 else 0.04,
        }

        discipline = float(getattr(militocracy, "militarydisciplinescore", 0.5)) if militocracy is not None else 0.5
        command = float(getattr(militocracy, "command_coherence", 0.5)) if militocracy is not None else 0.5
        synergy_index = float(getattr(synergy, "synergy_index", 0.5)) if synergy is not None else 0.5

        strategies = [
            {
                "name": "identity_guard",
                "mode": "stabilize",
                "preferred_actions": ["idle", "forward"],
                "strength": max(0.2, 0.5 + (0.35 * (1.0 - integrity)) + (0.2 * meta_drift) + (0.1 * value_map.get("ethical_stability", 0.6))),
                "alignment": max(0.0, min(1.0, 0.6 * drift_resistance + 0.4 * integrity)),
                "selfdirected": True,
            },
            {
                "name": "adaptive_exploration",
                "mode": "explore",
                "preferred_actions": ["forward", "left", "right"],
                "strength": max(0.2, 0.35 + (0.35 * agency) + (0.2 * intent_strength) + (0.12 * value_map.get("adaptive_learning", 0.5))),
                "alignment": max(0.0, min(1.0, 0.5 * integrity + 0.5 * intent_alignment)),
                "selfdirected": True,
            },
            {
                "name": "collective_stability",
                "mode": "balanced",
                "preferred_actions": ["forward", "idle"],
                "strength": max(0.2, 0.35 + (0.4 * intent_alignment) + (0.2 * drift_resistance) + (0.1 * value_map.get("collective_good", 0.5))),
                "alignment": max(0.0, min(1.0, 0.45 * integrity + 0.3 * intent_alignment + 0.25 * drift_resistance)),
                "selfdirected": True,
            },
            {
                "name": "coordinated_command",
                "mode": "balanced",
                "preferred_actions": ["forward", "idle"],
                "strength": max(0.2, (0.35 * discipline) + (0.35 * command) + (0.3 * synergy_index)),
                "alignment": max(0.0, min(1.0, (0.4 * discipline) + (0.3 * command) + (0.3 * self.normcompliancefactor))),
                "selfdirected": True,
            },
        ]

        self.selfdirectedgoals = [
            {"name": "preserve_cognitive_structure", "priority": max(0.4, 1.0 - integrity)},
            {"name": "expand_action_frontier", "priority": max(0.3, agency)},
            {"name": "maintain_meta_stability", "priority": max(0.3, 1.0 - meta_drift)},
        ]

        self.strategy_profile = {
            "strategies": [dict(s) for s in strategies],
            "autonomy_level": self.autonomy_level,
            "intent_alignment": intent_alignment,
            "meta_drift": meta_drift,
            "ethicalalignmentscore": self.ethicalalignmentscore,
            "selfregulationstrength": self.selfregulationstrength,
            "civilizationalignmentscore": self.civilizationalignmentscore,
            "normcompliancefactor": self.normcompliancefactor,
            "culturalstrategyadjustment": dict(self.culturalstrategyadjustment),
        }
        self.evaluate_autonomy_alignment(identitycore)
        return strategies

    def select_strategy(self) -> dict[str, Any] | None:
        strategies = list(self.strategy_profile.get("strategies", [])) if self.strategy_profile else []
        if not strategies:
            return None
        return max(strategies, key=lambda s: float(s.get("strength", 0.0)) * (0.65 + (0.35 * float(s.get("alignment", 0.0)))))

    def evaluate_autonomy_alignment(self, identitycore: Any) -> float:
        selected = self.select_strategy() or {}
        compatibility = 0.5
        if hasattr(identitycore, "evaluate_strategy_compatibility"):
            compatibility = float(identitycore.evaluate_strategy_compatibility(selected))

        conflict = max(0.0, 1.0 - compatibility)
        self.autonomy_conflicts = []
        if conflict > 0.35:
            self.autonomy_conflicts.append(
                {
                    "type": "identity_strategy_mismatch",
                    "strategy": str(selected.get("name", "none")),
                    "severity": conflict,
                }
            )
        return compatibility

    def update_autonomy_metrics(self) -> dict[str, Any]:
        selected = self.select_strategy() or {}
        alignment = 1.0 - min(1.0, sum(float(c.get("severity", 0.0)) for c in self.autonomy_conflicts))
        entry = {
            "t": len(self.autonomy_trace),
            "autonomy_level": self.autonomy_level,
            "selected_strategy": dict(selected),
            "selfdirectedgoals": [dict(g) for g in self.selfdirectedgoals],
            "autonomy_alignment": max(0.0, alignment),
            "ethicalalignmentscore": self.ethicalalignmentscore,
            "selfregulationstrength": self.selfregulationstrength,
            "civilizationalignmentscore": self.civilizationalignmentscore,
            "normcompliancefactor": self.normcompliancefactor,
            "culturalstrategyadjustment": dict(self.culturalstrategyadjustment),
            "conflicts": [dict(c) for c in self.autonomy_conflicts],
        }
        self.autonomy_trace.append(entry)
        if len(self.autonomy_trace) > MAX_TRACE_LENGTH:
            self.autonomy_trace = self.autonomy_trace[-MAX_TRACE_LENGTH:]
        return entry

    def apply_cooperative_regulation(self, social: Any | None, collective_state: dict[str, Any] | None = None) -> dict[str, Any]:
        collective_state = collective_state or {}
        cooperation = float(getattr(social, "cooperation_score", 0.6)) if social is not None else float(collective_state.get("collectivecooperationscore", 0.6))
        conflict = float(getattr(social, "socialconflictscore", 0.0)) if social is not None else float(collective_state.get("collectivesocialconflict", 0.0))

        self.cooperativealignmentscore = max(0.0, min(1.0, (0.55 * cooperation) + (0.45 * (1.0 - conflict))))
        self.groupstrategyadjustment = {
            "mode_bias": "balanced" if conflict > 0.4 else "explore" if cooperation > 0.7 else "stabilize",
            "strength_delta": (0.14 * cooperation) - (0.18 * conflict),
            "conflict_mitigation": conflict > 0.35,
        }

        self.autonomy_level = max(0.0, min(1.0, self.autonomy_level + float(self.groupstrategyadjustment["strength_delta"] * 0.2)))
        return dict(self.groupstrategyadjustment)

    # Compatibility aliases requested by specification.
    def generatestrategies(
        self,
        identitycore: Any,
        intentengine: Any,
        metacognition: Any,
        values: Any | None = None,
        culture: Any | None = None,
        militocracy: Any | None = None,
        synergy: Any | None = None,
    ) -> list[dict[str, Any]]:
        return self.generate_strategies(
            identitycore,
            intentengine,
            metacognition,
            values=values,
            culture=culture,
            militocracy=militocracy,
            synergy=synergy,
        )

    def selectstrategy(self) -> dict[str, Any] | None:
        return self.select_strategy()

    def evaluateautonomyalignment(self) -> float:
        return 1.0 - min(1.0, sum(float(c.get("severity", 0.0)) for c in self.autonomy_conflicts))

    def updateautonomymetrics(self) -> dict[str, Any]:
        return self.update_autonomy_metrics()

    def applycooperativeregulation(self, social: Any | None, collective_state: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.apply_cooperative_regulation(social, collective_state)
