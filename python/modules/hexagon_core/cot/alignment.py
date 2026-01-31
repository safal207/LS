import time
from typing import Dict, Any, List
from ..mission.state import MissionState
from ..causal.graph import CausalGraph

class AlignmentSystem:
    """
    Calculates alignment of beliefs with Mission State and determines trajectory.
    """
    def __init__(self, mission_state: MissionState):
        self.mission = mission_state
        self._cache: Dict[str, Dict[str, Any]] = {} # text -> {score, timestamp}
        self.cache_ttl = 60.0

    def cleanup_cache(self):
        """Removes expired cache entries."""
        now = time.time()
        expired = [k for k,v in self._cache.items() if now - v["timestamp"] > self.cache_ttl]
        for k in expired:
            del self._cache[k]

    def calculate_alignment(self, belief_text: str) -> float:
        """
        Calculates alignment score (0.0 - 1.0).
        Uses Jaccard similarity with Mission core principles.
        """
        now = time.time()

        # Periodic cleanup probability or call explicitly?
        # User requested the method, let's call it opportunistically or rely on caller.
        # Let's call it if cache is large? Or just leave it for maintenance.
        # I'll add the method as requested.

        if belief_text in self._cache:
            entry = self._cache[belief_text]
            if now - entry["timestamp"] < self.cache_ttl:
                return entry["score"]

        # Spec: "Jaccard po mission keywords"
        mission_keywords = set()
        for p in self.mission.core_principles:
            mission_keywords.update(p.lower().split())

        belief_words = set(belief_text.lower().split())
        if not mission_keywords or not belief_words:
            score = 0.5
        else:
            intersection = len(belief_words.intersection(mission_keywords))
            union = len(belief_words.union(mission_keywords))
            score = intersection / union if union > 0 else 0.0

        self._cache[belief_text] = {"score": score, "timestamp": now}
        return score

    def calculate_trajectory(self, belief_id: str, causal_graph: CausalGraph) -> float:
        """
        Calculates trajectory score based on upstream causal links.
        0.5 = neutral/no history.
        """
        upstream_edges = causal_graph.get_upstream(belief_id)
        if not upstream_edges:
            return 0.5

        # Spec: "score = weighted average with time decay" (Phase 3.1 placeholder)

        total_weight = 0.0
        weighted_sum = 0.0

        for edge in upstream_edges:
            weighted_sum += edge.weight
            total_weight += 1.0

        if total_weight == 0: return 0.5

        return weighted_sum / total_weight
