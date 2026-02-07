from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class MeritEngine:
    def score(self, aggregated: Dict[str, Any]) -> Dict[str, float]:
        self_model = aggregated.get("self_model", {})
        affective = aggregated.get("affective", {})
        identity = aggregated.get("identity", {})
        capu = aggregated.get("capu", {})
        narrative = aggregated.get("narrative", {})

        fragmentation = float(self_model.get("fragmentation", 0.0))
        energy = float(affective.get("energy", 0.5))
        preferences = identity.get("preferences", {})
        smooth_runtime = float(preferences.get("smooth_runtime", 0.5))
        confidence_margin = float(capu.get("logits_confidence_margin", 0.5))
        narrative_alignment = self._narrative_alignment(narrative.get("timeline", []))

        scores: Dict[str, float] = {
            "self_model": 1.0 - fragmentation,
            "affective": energy,
            "identity": smooth_runtime,
            "capu": confidence_margin,
            "decision": 1.0,
            "causal": 0.8,
            "state": 1.0,
            "narrative_alignment": narrative_alignment,
        }
        return scores

    @staticmethod
    def _narrative_alignment(timeline: List[Dict[str, Any]]) -> float:
        if not timeline:
            return 0.5

        recent = timeline[-3:]
        states = [entry.get("system_state") for entry in recent]
        alignment = 0.5

        if len(recent) == 3 and all(state == "stable" for state in states):
            alignment += 0.1
        if "overload" in states:
            alignment -= 0.2
        if "fragmented" in states:
            alignment -= 0.3

        choices = [
            entry.get("decision_choice")
            for entry in recent
            if entry.get("system_state") == "stable" and entry.get("decision_choice")
        ]
        if choices:
            counts = {choice: choices.count(choice) for choice in set(choices)}
            if max(counts.values(), default=0) >= 2:
                alignment += 0.05

        return max(0.0, min(1.0, alignment))
