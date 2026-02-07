from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class MeritEngine:
    def score(self, aggregated: Dict[str, Any]) -> Dict[str, float]:
        self_model = aggregated.get("self_model", {})
        affective = aggregated.get("affective", {})
        identity = aggregated.get("identity", {})
        capu = aggregated.get("capu", {})

        fragmentation = float(self_model.get("fragmentation", 0.0))
        energy = float(affective.get("energy", 0.5))
        preferences = identity.get("preferences", {})
        smooth_runtime = float(preferences.get("smooth_runtime", 0.5))
        confidence_margin = float(capu.get("logits_confidence_margin", 0.5))

        scores: Dict[str, float] = {
            "self_model": 1.0 - fragmentation,
            "affective": energy,
            "identity": smooth_runtime,
            "capu": confidence_margin,
            "decision": 1.0,
            "causal": 0.8,
            "state": 1.0,
        }
        return scores
