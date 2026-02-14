from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
    civilizationalignmentscore: float = 0.5
    normcompliancefactor: float = 0.5
    culturalstrategyadjustment: str = "balance"

    def generate_strategies(self, identitycore: Any, intentengine: Any, metacognition: Any, values: Any | None = None, civilization_adjustments: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        integrity = float(getattr(identitycore, "identity_integrity", 1.0))
        agency = float(getattr(identitycore, "agency_level", 0.0))
        drift_resistance = float(getattr(identitycore, "drift_resistance", 1.0))
        intent_alignment = float(getattr(intentengine, "intent_alignment", 1.0))
        intent_strength = float(getattr(intentengine, "intent_strength", 0.0))
        meta_drift = float(getattr(metacognition, "latest_feedback", {}).get("meta_drift", 0.0))
        value_alignment = float(getattr(values, "valuealignmentscore", 1.0)) if values is not None else 1.0
        value_map = dict(getattr(values, "core_values", {})) if values is not None else {}
        civ = civilization_adjustments or {}
        self.civilizationalignmentscore = float(civ.get("civilizationalignmentscore", self.civilizationalignmentscore))
        self.normcompliancefactor = float(civ.get("normcompliancefactor", self.normcompliancefactor))
        self.culturalstrategyadjustment = str(civ.get("culturalstrategyadjustment", self.culturalstrategyadjustment))

        self.autonomy_level = max(
            0.0,
            min(
                1.0,
                (0.23 * integrity) + (0.2 * agency) + (0.12 * drift_resistance) + (0.14 * intent_alignment) + (0.1 * (1.0 - meta_drift)) + (0.1 * value_alignment) + (0.11 * self.civilizationalignmentscore),
            ),
        )

        self.ethicalalignmentscore = max(0.0, min(1.0, value_alignment))
        self.selfregulationstrength = max(0.0, min(1.0, (0.5 * drift_resistance) + (0.5 * self.ethicalalignmentscore)))

        strategies = [
            {
                "name": "identity_guard",
                "mode": "stabilize",
                "preferred_actions": ["idle", "forward"],
                "strength": max(0.2, 0.5 + (0.35 * (1.0 - integrity)) + (0.2 * meta_drift) + (0.1 * value_map.get("ethical_stability", 0.6)) + (0.08 * self.normcompliancefactor if self.culturalstrategyadjustment == "stabilize" else 0.0)),
                "alignment": max(0.0, min(1.0, 0.6 * drift_resistance + 0.4 * integrity)),
                "selfdirected": True,
            },
            {
                "name": "adaptive_exploration",
                "mode": "explore",
                "preferred_actions": ["forward", "left", "right"],
                "strength": max(0.2, 0.35 + (0.35 * agency) + (0.2 * intent_strength) + (0.12 * value_map.get("adaptive_learning", 0.5)) + (0.08 * self.normcompliancefactor if self.culturalstrategyadjustment == "expand" else -0.04)),
                "alignment": max(0.0, min(1.0, 0.5 * integrity + 0.5 * intent_alignment)),
                "selfdirected": True,
            },
            {
                "name": "collective_stability",
                "mode": "balanced",
                "preferred_actions": ["forward", "idle"],
                "strength": max(0.2, 0.35 + (0.4 * intent_alignment) + (0.2 * drift_resistance) + (0.1 * value_map.get("collective_good", 0.5)) + (0.06 * self.civilizationalignmentscore)),
                "alignment": max(0.0, min(1.0, 0.45 * integrity + 0.3 * intent_alignment + 0.25 * drift_resistance)),
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
            "culturalstrategyadjustment": self.culturalstrategyadjustment,
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
            "culturalstrategyadjustment": self.culturalstrategyadjustment,
            "conflicts": [dict(c) for c in self.autonomy_conflicts],
        }
        self.autonomy_trace.append(entry)
        if len(self.autonomy_trace) > 200:
            self.autonomy_trace = self.autonomy_trace[-200:]
        return entry

    # Compatibility aliases requested by specification.
    def generatestrategies(self, identitycore: Any, intentengine: Any, metacognition: Any, values: Any | None = None, civilization_adjustments: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.generate_strategies(identitycore, intentengine, metacognition, values=values, civilization_adjustments=civilization_adjustments)

    def selectstrategy(self) -> dict[str, Any] | None:
        return self.select_strategy()

    def evaluateautonomyalignment(self) -> float:
        return 1.0 - min(1.0, sum(float(c.get("severity", 0.0)) for c in self.autonomy_conflicts))

    def updateautonomymetrics(self) -> dict[str, Any]:
        return self.update_autonomy_metrics()

