import time
from typing import Dict, Any
from ..mission.state import MissionState
from ..causal.graph import CausalGraph

STOPWORDS = {
    "is","a","the","an","of","and","or","to","in","on","at",
    "are","it","this","that","we","must","can","should","will",
    "be","as","for","with","by","from","not","but","have","has"
}

class AlignmentSystem:
    """
    Calculates alignment of beliefs with Mission State and determines trajectory.
    """
    def __init__(self, mission_state: MissionState):
        self.mission = mission_state
        self._cache: Dict[str, Dict[str, Any]] = {} # text -> {score, timestamp}
        self.cache_ttl = 60.0

        # Cleanup params
        self.cleanup_threshold = 100
        self.cleanup_frequency = 10
        self.cleanup_counter = 0

        # Metrics
        self.cache_hits = 0
        self.cache_misses = 0

    def cleanup_cache(self):
        """Removes expired cache entries."""
        now = time.time()
        expired = [k for k,v in self._cache.items() if now - v["timestamp"] > self.cache_ttl]
        for k in expired:
            del self._cache[k]

    def get_cache_stats(self) -> Dict[str, Any]:
        total = self.cache_hits + self.cache_misses
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": self.cache_hits / total if total > 0 else 0.0,
        }

    def calculate_alignment(self, belief_text: str) -> float:
        """
        Calculates alignment score (0.0 - 1.0).
        Uses Jaccard similarity with Mission core principles.
        """
        self.cleanup_counter += 1
        if len(self._cache) > self.cleanup_threshold or \
           self.cleanup_counter >= self.cleanup_frequency:
            self.cleanup_cache()
            self.cleanup_counter = 0

        now = time.time()

        if belief_text in self._cache:
            entry = self._cache[belief_text]
            if now - entry["timestamp"] < self.cache_ttl:
                self.cache_hits += 1
                return entry["score"]

        self.cache_misses += 1

        # Spec: "Jaccard po mission keywords"
        mission_keywords = set()
        for p in self.mission.core_principles:
            mission_keywords.update(p.lower().split())

        # Apply stopwords
        mission_keywords = {w for w in mission_keywords if w not in STOPWORDS}

        belief_words = set(belief_text.lower().split())
        belief_words = {w for w in belief_words if w not in STOPWORDS}

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

        if total_weight == 0:
            return 0.5

        return weighted_sum / total_weight
