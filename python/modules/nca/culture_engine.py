from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CultureEngine:
    """Phase 11 culture engine for norms, traditions, and civilizational adaptation."""

    cultural_memory: list[dict[str, Any]] = field(default_factory=list)
    norms: dict[str, float] = field(default_factory=dict)
    traditions: dict[str, Any] = field(default_factory=dict)
    norm_conflicts: list[dict[str, Any]] = field(default_factory=list)
    civilization_state: dict[str, Any] = field(default_factory=dict)
    culturalalignmentscore: float = 1.0
    culture_trace: list[dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def _normalize_traditions(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, list):
            return {
                str(item.get("pattern", f"tradition_{idx}")): float(item.get("strength", 0.0))
                for idx, item in enumerate(raw)
                if isinstance(item, dict)
            }
        return {}

    def _ensure_traditions_mapping(self) -> None:
        if not isinstance(self.traditions, dict):
            self.traditions = self._normalize_traditions(self.traditions)

    def update_from_social(self, social_engine: Any) -> dict[str, Any]:
        if social_engine is None:
            return self.civilization_state

        group_norms = dict(getattr(social_engine, "group_norms", {}))
        tradition_patterns = self._normalize_traditions(getattr(social_engine, "tradition_patterns", {}))
        conflict_index = float(getattr(social_engine, "conflict_index", getattr(social_engine, "socialconflictscore", 0.0)))
        collaboration = float(getattr(social_engine, "collaboration_index", getattr(social_engine, "cooperation_score", 0.0)))
        similarity = float(getattr(social_engine, "culturalsimilarityscore", 0.5))

        self.norms.update({k: max(0.0, min(1.0, float(v))) for k, v in group_norms.items()})
        self._ensure_traditions_mapping()
        self.traditions.update(tradition_patterns)

        self.civilization_state.update(
            {
                "collaboration_index": collaboration,
                "conflict_index": conflict_index,
                "cultural_similarity": similarity,
            }
        )
        return dict(self.civilization_state)

    def update_from_values(self, value_system: Any) -> dict[str, Any]:
        if value_system is None:
            return self.civilization_state

        alignment = float(getattr(value_system, "culturalvaluealignment", 0.6))
        self.civilization_state["value_alignment"] = max(0.0, min(1.0, alignment))
        norm_map = dict(getattr(value_system, "normethicsmap", {}))
        for norm, score in norm_map.items():
            self.norms[norm] = max(0.0, min(1.0, 0.6 * self.norms.get(norm, 0.5) + 0.4 * float(score)))
        return dict(self.civilization_state)

    def update_from_collective(self, collective_state: dict[str, Any] | None) -> dict[str, Any]:
        collective_state = collective_state or {}
        self.civilization_state["collectiveculturealignment"] = float(
            collective_state.get("collectiveculturealignment", self.civilization_state.get("collectiveculturealignment", 0.6))
        )
        self.civilization_state["collectiveculturalconflict"] = float(
            collective_state.get("collectiveculturalconflict", self.civilization_state.get("collectiveculturalconflict", 0.0))
        )
        self.civilization_state["civilizationmaturityscore"] = float(
            collective_state.get("civilizationmaturityscore", self.civilization_state.get("civilizationmaturityscore", 0.5))
        )
        self._ensure_traditions_mapping()
        self.traditions.update(self._normalize_traditions(collective_state.get("collectivetraditionpatterns", {})))
        self.norms.update({k: float(v) for k, v in dict(collective_state.get("collectivenorms", {})).items()})
        return dict(self.civilization_state)

    def infer_norms(self, events: list[dict[str, Any]] | None) -> dict[str, float]:
        votes: dict[str, list[float]] = {}
        for event in events or []:
            social = dict(event.get("social", {})) if isinstance(event, dict) else {}
            group_norms = social.get("group_norms", {}) if isinstance(social, dict) else {}
            if isinstance(group_norms, dict):
                for norm, value in group_norms.items():
                    votes.setdefault(str(norm), []).append(float(value))

        for norm, samples in votes.items():
            avg = sum(samples) / max(1, len(samples))
            self.norms[norm] = max(0.0, min(1.0, 0.65 * self.norms.get(norm, avg) + 0.35 * avg))

        return dict(self.norms)

    def evolve_norms(self) -> dict[str, float]:
        self.norm_conflicts = []
        for norm, weight in list(self.norms.items()):
            target = 0.5
            if norm in ("cooperation", "stability"):
                target = 0.7
            drift = float(weight) - target
            if abs(drift) > 0.35:
                self.norm_conflicts.append({"norm": norm, "severity": abs(drift), "drift": drift})
            self.norms[norm] = max(0.0, min(1.0, float(weight) - (0.08 * drift)))

        return dict(self.norms)

    def evaluate_cultural_alignment(
        self,
        identity_score: float,
        value_score: float,
        social_score: float,
    ) -> float:
        conflict_penalty = float(self.civilization_state.get("collectiveculturalconflict", 0.0))

        self.culturalalignmentscore = max(
            0.0,
            min(
                1.0,
                (0.35 * float(identity_score))
                + (0.35 * float(value_score))
                + (0.3 * float(social_score))
                - (0.2 * conflict_penalty),
            ),
        )
        return self.culturalalignmentscore

    def generate_civilization_adjustments(self) -> dict[str, Any]:
        conflict = float(self.civilization_state.get("collectiveculturalconflict", 0.0))
        maturity = float(self.civilization_state.get("civilizationmaturityscore", 0.5))

        adjustment = {
            "norm_reinforcement": conflict < 0.35,
            "conflict_mitigation": conflict >= 0.35,
            "tradition_adaptation": maturity < 0.6,
            "alignment_boost": max(0.0, min(0.25, 0.3 * self.culturalalignmentscore)),
        }
        self.culture_trace.append(
            {
                "t": len(self.culture_trace),
                "culturalalignmentscore": self.culturalalignmentscore,
                "norms": dict(self.norms),
                "traditions": self._normalize_traditions(self.traditions),
                "norm_conflicts": [dict(c) for c in self.norm_conflicts],
                "civilization_state": dict(self.civilization_state),
                "adjustments": dict(adjustment),
            }
        )
        if len(self.culture_trace) > 200:
            self.culture_trace = self.culture_trace[-200:]
        return adjustment

    def updatefromsocial(self, social_engine: Any) -> dict[str, Any]:
        return self.update_from_social(social_engine)

    def updatefromvalues(self, value_system: Any) -> dict[str, Any]:
        return self.update_from_values(value_system)

    def updatefromcollective(self, collective_state: dict[str, Any] | None) -> dict[str, Any]:
        return self.update_from_collective(collective_state)

    def infer_norms_alias(self, events: list[dict[str, Any]] | None) -> dict[str, float]:
        return self.infer_norms(events)

    def evolve_norms_alias(self) -> dict[str, float]:
        return self.evolve_norms()

    def infernorms(self, events: list[dict[str, Any]] | None) -> dict[str, float]:
        return self.infer_norms(events)

    def evolvenorms(self) -> dict[str, float]:
        return self.evolve_norms()

    def evaluateculturalalignment(self, identity_score: float, value_score: float, social_score: float) -> float:
        return self.evaluate_cultural_alignment(identity_score, value_score, social_score)

    def generatecivilizationadjustments(self) -> dict[str, Any]:
        return self.generate_civilization_adjustments()
