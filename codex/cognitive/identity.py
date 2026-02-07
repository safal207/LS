from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from codex.causal_memory.store import MemoryRecord

from .decision import DecisionRecord
from .thread import LiminalThread


@dataclass
class LivingIdentity:
    preferences: Dict[str, float] = field(default_factory=dict)
    aversions: Dict[str, float] = field(default_factory=dict)
    state_profile: Dict[str, int] = field(default_factory=dict)
    semantic_links: Dict[str, List[str]] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "preferences": dict(self.preferences),
            "aversions": dict(self.aversions),
            "state_profile": dict(self.state_profile),
            "semantic_links": {key: list(values) for key, values in self.semantic_links.items()},
            "history": list(self.history),
        }

    def update_from_state(self, state: str) -> None:
        self.state_profile[state] = self.state_profile.get(state, 0) + 1

    def update_from_capu(self, capu_features: Dict[str, float]) -> None:
        rtf = capu_features.get("rtf_estimate")
        if rtf is not None and rtf > 1.2:
            self.aversions["slow_runtime"] = self.aversions.get("slow_runtime", 0.0) + 0.1
        elif capu_features:
            self.preferences["smooth_runtime"] = self.preferences.get("smooth_runtime", 0.0) + 0.05

    def update_from_decision(self, decision_record: DecisionRecord) -> None:
        if decision_record.success:
            self.preferences[decision_record.choice] = self.preferences.get(decision_record.choice, 0.0) + 0.2
        else:
            self.aversions[decision_record.choice] = self.aversions.get(decision_record.choice, 0.0) + 0.2

    def update_from_causal(self, memory_record: MemoryRecord) -> None:
        target = self.preferences if memory_record.success else self.aversions
        target[memory_record.model] = target.get(memory_record.model, 0.0) + 0.1

    def update_from_thread(self, thread: LiminalThread) -> None:
        self.history.append(thread.thread_id)
        transitions = [event.transition_label for event in thread.events]
        if transitions:
            self.semantic_links.setdefault("transitions", []).extend(transitions)
