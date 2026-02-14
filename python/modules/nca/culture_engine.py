from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CultureEngine:
    """Emergent culture layer for norms, traditions, and civilization signals."""

    cultural_memory: list[dict[str, Any]] = field(default_factory=list)
    norms: dict[str, float] = field(default_factory=dict)
    culturalalignmentscore: float = 0.5
    norm_conflicts: list[dict[str, Any]] = field(default_factory=list)
    traditions: list[dict[str, Any]] = field(default_factory=list)
    civilization_state: dict[str, Any] = field(default_factory=dict)
    culture_trace: list[dict[str, Any]] = field(default_factory=list)

    def update_from_social(self, social_engine: Any) -> dict[str, Any]:
        group_norms = dict(getattr(social_engine, "group_norms", {}))
        similarity = float(getattr(social_engine, "culturalsimilarityscore", 0.5))
        conflict = float(getattr(social_engine, "conflict_index", 0.0))
        self.norms.update(group_norms)
        self.culturalalignmentscore = max(0.0, min(1.0, (0.7 * similarity) + (0.3 * (1.0 - conflict))))

        marker = {
            "t": len(self.cultural_memory),
            "source": "social",
            "norms": dict(group_norms),
            "similarity": similarity,
            "conflict": conflict,
            "culturalalignmentscore": self.culturalalignmentscore,
        }
        self.cultural_memory.append(marker)
        if len(self.cultural_memory) > 300:
            self.cultural_memory = self.cultural_memory[-300:]
        return marker

    def update_from_values(self, value_system: Any) -> None:
        value_alignment = float(getattr(value_system, "culturalvaluealignment", getattr(value_system, "valuealignmentscore", 0.5)))
        ethics_map = dict(getattr(value_system, "normethicsmap", {}))
        self.norms.update({f"ethic_{k}": float(v) for k, v in ethics_map.items()})
        self.culturalalignmentscore = max(0.0, min(1.0, 0.65 * self.culturalalignmentscore + 0.35 * value_alignment))

    def update_from_collective(self, collective_state: dict[str, Any] | None) -> None:
        payload = collective_state or {}
        collective_alignment = float(payload.get("collectiveculturealignment", payload.get("collectivevaluealignment", 0.5)))
        collective_conflict = float(payload.get("collectiveculturalconflict", payload.get("collectiveethicalconflict", 0.0)))
        self.civilization_state = {
            "collective_alignment": collective_alignment,
            "collective_conflict": collective_conflict,
            "civilization_maturity": max(0.0, min(1.0, collective_alignment - (0.4 * collective_conflict))),
        }

    def infer_norms(self, events: list[dict[str, Any]] | None) -> dict[str, float]:
        event_list = events or []
        action_counts: dict[str, int] = {}
        for event in event_list:
            action = str(event.get("action", "idle"))
            action_counts[action] = action_counts.get(action, 0) + 1

        total = max(1, sum(action_counts.values()))
        for action, count in action_counts.items():
            self.norms[f"prefer_{action}"] = count / total

        if action_counts:
            dominant_action = max(action_counts, key=action_counts.get)
            self.traditions.append(
                {
                    "t": len(self.traditions),
                    "pattern": f"repeat_{dominant_action}",
                    "strength": action_counts[dominant_action] / total,
                }
            )
        if len(self.traditions) > 300:
            self.traditions = self.traditions[-300:]
        return dict(self.norms)

    def evolve_norms(self) -> dict[str, float]:
        self.norm_conflicts = []
        stabilize = float(self.norms.get("prefer_idle", 0.0))
        explore = sum(float(self.norms.get(k, 0.0)) for k in ("prefer_forward", "prefer_left", "prefer_right"))
        if stabilize > 0.65 and explore > 0.65:
            self.norm_conflicts.append(
                {
                    "type": "stability_vs_exploration",
                    "severity": min(1.0, abs(stabilize - explore) + 0.2),
                }
            )

        conflict_penalty = min(0.35, 0.12 * len(self.norm_conflicts))
        self.culturalalignmentscore = max(0.0, min(1.0, self.culturalalignmentscore - conflict_penalty))

        trace_item = {
            "t": len(self.culture_trace),
            "norms": dict(self.norms),
            "norm_conflicts": [dict(c) for c in self.norm_conflicts],
            "culturalalignmentscore": self.culturalalignmentscore,
            "civilization_state": dict(self.civilization_state),
        }
        self.culture_trace.append(trace_item)
        if len(self.culture_trace) > 300:
            self.culture_trace = self.culture_trace[-300:]
        return dict(self.norms)

    def evaluate_cultural_alignment(self, agent: Any) -> float:
        identity_score = float(getattr(getattr(agent, "identitycore", None), "culturalidentityscore", 0.5))
        value_score = float(getattr(getattr(agent, "values", None), "culturalvaluealignment", 0.5))
        self.culturalalignmentscore = max(
            0.0,
            min(1.0, (0.45 * self.culturalalignmentscore) + (0.3 * identity_score) + (0.25 * value_score)),
        )
        return self.culturalalignmentscore

    def generate_civilization_adjustments(self) -> dict[str, Any]:
        maturity = float(self.civilization_state.get("civilization_maturity", self.culturalalignmentscore))
        conflict_level = min(1.0, len(self.norm_conflicts) / 4.0)
        return {
            "civilizationalignmentscore": self.culturalalignmentscore,
            "normcompliancefactor": max(0.0, min(1.0, self.culturalalignmentscore - (0.4 * conflict_level))),
            "culturalstrategyadjustment": "stabilize" if maturity < 0.45 else "balance" if maturity < 0.7 else "expand",
            "civilizationmaturity": maturity,
            "culturalconflict": conflict_level,
        }

    def updatefromsocial(self, social_engine: Any) -> dict[str, Any]:
        return self.update_from_social(social_engine)

    def updatefromvalues(self, value_system: Any) -> None:
        self.update_from_values(value_system)

    def updatefromcollective(self, collective_state: dict[str, Any] | None) -> None:
        self.update_from_collective(collective_state)

    def infernorms(self, events: list[dict[str, Any]] | None) -> dict[str, float]:
        return self.infer_norms(events)

    def evolvenorms(self) -> dict[str, float]:
        return self.evolve_norms()

    def evaluateculturalalignment(self, agent: Any) -> float:
        return self.evaluate_cultural_alignment(agent)

    def generatecivilizationadjustments(self) -> dict[str, Any]:
        return self.generate_civilization_adjustments()
