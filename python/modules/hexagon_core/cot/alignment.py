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

    def calculate_alignment(self, belief_text: str) -> float:
        """
        Calculates alignment score (0.0 - 1.0).
        Uses simple keyword overlap with Mission core principles for now.
        """
        now = time.time()
        if belief_text in self._cache:
            entry = self._cache[belief_text]
            if now - entry["timestamp"] < self.cache_ttl:
                return entry["score"]

        # Calculate
        # This is a placeholder for more complex logic.
        # MissionState.check_alignment uses "intent", let's reuse it if possible
        # or implement Jaccard against principles.

        # Spec: "Jaccard po mission keywords"
        # Core principles are sentences.
        mission_keywords = set()
        for p in self.mission.core_principles:
            mission_keywords.update(p.lower().split())

        belief_words = set(belief_text.lower().split())
        if not mission_keywords or not belief_words:
            score = 0.5
        else:
            intersection = len(belief_words.intersection(mission_keywords))
            union = len(belief_words.union(mission_keywords))
            # Jaccard might be too strict if texts are very different lengths.
            # Spec says Jaccard.
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

        # Weighted average of upstream weights (which imply success/confidence)
        # Maybe upstream node confidence?
        # Spec: "score = weighted average with time decay"

        total_weight = 0.0
        weighted_sum = 0.0

        for edge in upstream_edges:
            # Assuming edge.weight is positive indicator
            # Time decay?
            # Not implementing complex time decay here without `now` reference in args
            # Using edge weight directly.
            weighted_sum += edge.weight
            total_weight += 1.0 # Or use some importance factor

        if total_weight == 0: return 0.5

        return weighted_sum / total_weight
