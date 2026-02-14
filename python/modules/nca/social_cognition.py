from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SocialCognitionEngine:
    """Tracks emergent social modeling and group-level cultural cues."""

    social_memory: list[dict[str, Any]] = field(default_factory=list)
    role_affinities: dict[str, float] = field(default_factory=dict)
    collaboration_index: float = 0.5
    conflict_index: float = 0.0
    group_norms: dict[str, float] = field(default_factory=dict)
    tradition_patterns: list[dict[str, Any]] = field(default_factory=list)
    culturalsimilarityscore: float = 0.5

    def update_from_collective(self, collective_state: dict[str, Any] | None) -> dict[str, Any]:
        payload = collective_state or {}
        intent_alignment = float(payload.get("collectiveintentalignment", 0.5))
        value_alignment = float(payload.get("collectivevaluealignment", 0.5))
        ethical_conflict = float(payload.get("collectiveethicalconflict", 0.0))

        self.collaboration_index = max(0.0, min(1.0, (0.55 * intent_alignment) + (0.45 * value_alignment)))
        self.conflict_index = max(0.0, min(1.0, ethical_conflict))
        self.culturalsimilarityscore = max(0.0, min(1.0, self.collaboration_index - (0.35 * self.conflict_index)))
        self.group_norms = {
            "mutual_progress": max(0.0, min(1.0, intent_alignment)),
            "ethical_balance": max(0.0, min(1.0, 1.0 - ethical_conflict)),
            "collective_consistency": max(0.0, min(1.0, value_alignment)),
        }
        marker = {
            "t": len(self.social_memory),
            "collaboration_index": self.collaboration_index,
            "conflict_index": self.conflict_index,
            "group_norms": dict(self.group_norms),
            "culturalsimilarityscore": self.culturalsimilarityscore,
        }
        self.social_memory.append(marker)
        if len(self.social_memory) > 200:
            self.social_memory = self.social_memory[-200:]
        return marker

    def update_from_identity(self, identity_core: Any) -> None:
        cooperation = float(getattr(identity_core, "core_traits", {}).get("cooperation", 0.6))
        consistency = float(getattr(identity_core, "core_traits", {}).get("consistency", 0.6))
        self.role_affinities = {
            "coordinator": max(0.0, min(1.0, 0.6 * cooperation + 0.4 * consistency)),
            "explorer": max(0.0, min(1.0, 1.0 - consistency + 0.4 * cooperation)),
        }

    def update_from_values(self, value_system: Any) -> None:
        collective_good = float(getattr(value_system, "core_values", {}).get("collective_good", 0.6))
        ethical_stability = float(getattr(value_system, "core_values", {}).get("ethical_stability", 0.7))
        self.group_norms["collective_good"] = collective_good
        self.group_norms["ethical_stability"] = ethical_stability

        if collective_good > 0.68 or ethical_stability > 0.72:
            self.tradition_patterns.append(
                {
                    "t": len(self.tradition_patterns),
                    "pattern": "cohesive_coordination",
                    "strength": max(collective_good, ethical_stability),
                }
            )
        if len(self.tradition_patterns) > 200:
            self.tradition_patterns = self.tradition_patterns[-200:]

    def updatefromcollective(self, collective_state: dict[str, Any] | None) -> dict[str, Any]:
        return self.update_from_collective(collective_state)

    def updatefromidentity(self, identity_core: Any) -> None:
        self.update_from_identity(identity_core)

    def updatefromvalues(self, value_system: Any) -> None:
        self.update_from_values(value_system)

