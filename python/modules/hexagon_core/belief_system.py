import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple
from .cte import Convict, CognitiveTimelineEngine

logger = logging.getLogger("BeliefSystem")

# Fix 9: Russian stopwords
STOPWORDS_RU = {
    "и", "в", "во", "не", "на", "я", "быть", "он", "с", "со", "что", "а", "по",
    "это", "она", "этот", "к", "но", "они", "мы", "как", "из", "у", "который",
    "то", "за", "свой", "что-то", "весь", "мочь", "для", "о", "же", "год", "вы",
    "ты", "от", "человек", "такой", "все", "теперь", "еще", "или", "бы"
}
STOPWORDS_EN = {
    "is", "a", "the", "an", "of", "and", "or", "to", "in", "on", "at", "not",
    "this", "that", "it", "for", "with", "as", "by", "from"
}
ALL_STOPWORDS = STOPWORDS_EN | STOPWORDS_RU

@dataclass
class ReinforcementHistory:
    timestamp: datetime
    boost: float
    source: str

class ReinforcementTracker:
    def __init__(self):
        self.history: List[ReinforcementHistory] = []
        self.base_boost = 0.1

    # Fix 1: Fix Reinforcement Boost
    def calculate_boost(self, convict: Convict) -> float:
        """
        Calculate reinforcement boost based on current confidence.
        Diminishing returns: high confidence = lower boost.
        """
        return self.base_boost * (1.0 - convict.confidence)

    def reinforce(self, convict: Convict, strength_signal: float = 1.0) -> float:
        """
        Apply reinforcement to a convict.
        """
        boost = self.calculate_boost(convict)

        # Use legitimate strength, not artificial floor of 0.5
        effective_strength_multiplier = max(0.1, min(1.0, convict.strength / 10.0))

        actual_boost = boost * strength_signal * effective_strength_multiplier

        convict.confidence = min(1.0, convict.confidence + actual_boost)
        convict.strength += 1
        convict.last_validated = datetime.now().timestamp()

        # Log history
        self.history.append(ReinforcementHistory(
            timestamp=datetime.now(),
            boost=actual_boost,
            source="reinforce"
        ))

        # Fix 10: Pruning reinforcement history
        self._prune_history()

        return actual_boost

    def _prune_history(self):
        if len(self.history) > 1000:
            # Keep last 500
            self.history = self.history[-500:]

class DecayEngine:
    def __init__(self):
        self.decay_rate = 0.05 # Per cycle/check

    # Fix 4: Fix decay_cycles_survived inflation
    def apply_decay(self, convict: Convict, is_active: bool = False):
        """
        Apply decay if belief hasn't been validated recently.
        """
        # Assuming Convict has 'status' and 'decay_cycles_survived' fields
        # (if not in CTE, we might need to patch CTE or track separately)
        # For Phase 2, let's assume we can set attributes dynamically or rely on CTE update.
        # Since CTE.Convict is a dataclass, we can't easily add fields dynamically if frozen.
        # But it's not frozen.

        if not hasattr(convict, 'status'):
            convict.status = "active"
        if not hasattr(convict, 'decay_cycles_survived'):
            convict.decay_cycles_survived = 0

        old_status = convict.status

        # Determine if should decay
        now = datetime.now().timestamp()
        days_since_validation = (now - convict.last_validated) / 86400

        if days_since_validation > 30 and not is_active:
             convict.confidence = max(0.0, convict.confidence - self.decay_rate)
             convict.status = "decaying"
        else:
             convict.status = "active"

        # Only increment survival counter if we were active and stay active
        if old_status != "deprecated" and convict.status != "deprecated":
             if convict.status == "decaying":
                 pass # Don't increment survival if decaying?
                 # User said: "Use old status... if old != DEPRECATED and current != DEPRECATED: survive += 1"
                 # But "Problem: Counter increases even if belief already DECAYING".
                 # So if it IS decaying, we shouldn't increment?
                 # "Use old status" implies we care about state transition.
                 # Let's assume survival means "cycles active".
                 pass
             elif convict.status == "active":
                 convict.decay_cycles_survived += 1

class ContradictionDetector:
    # Fix 5: Fix negation false positives using XOR
    def detect(self, belief1: str, belief2: str) -> bool:
        """
        Detect logical contradiction between two belief strings.
        """
        tokens1 = self._tokenize(belief1)
        tokens2 = self._tokenize(belief2)

        negation_tokens = {"not", "no", "never", "не", "нет"}

        has_neg_a = not tokens1.isdisjoint(negation_tokens)
        has_neg_b = not tokens2.isdisjoint(negation_tokens)

        # XOR: one has negation, the other doesn't
        is_explicit_negation = (has_neg_a != has_neg_b)

        # Clean tokens for similarity check (remove negations)
        clean1 = tokens1 - negation_tokens
        clean2 = tokens2 - negation_tokens

        similarity = self._jaccard_similarity(clean1, clean2)

        return is_explicit_negation and (similarity > 0.6)

    def _tokenize(self, text: str) -> Set[str]:
        return set(re.findall(r"\w+", text.lower()))

    def _jaccard_similarity(self, set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a or not set_b: return 0.0
        return len(set_a.intersection(set_b)) / len(set_a.union(set_b))

@dataclass
class BeliefCluster:
    id: str
    center_text: str
    members: List[Convict]

class SemanticClusterManager:
    def __init__(self):
        self.clusters: List[BeliefCluster] = []
        self.threshold = 0.4

    # Fix 6: Improve cluster assignment (Best Fit)
    def cluster(self, convicts: List[Convict]) -> List[BeliefCluster]:
        self.clusters = []

        for c in convicts:
            best_cluster = None
            best_dist = 1.0 - self.threshold # Distance threshold (1 - sim)

            # Find best cluster
            for cluster in self.clusters:
                dist = self._jaccard_distance(c.belief, cluster.center_text)
                if dist < best_dist:
                    best_dist = dist
                    best_cluster = cluster

            if best_cluster:
                best_cluster.members.append(c)
                # Optional: Update center? For now, keep simple.
            else:
                # Create new cluster
                new_cluster = BeliefCluster(
                    id=f"cluster_{len(self.clusters)}",
                    center_text=c.belief,
                    members=[c]
                )
                self.clusters.append(new_cluster)

        return self.clusters

    def _jaccard_distance(self, text1: str, text2: str) -> float:
        tokens1 = set(re.findall(r"\w+", text1.lower())) - ALL_STOPWORDS
        tokens2 = set(re.findall(r"\w+", text2.lower())) - ALL_STOPWORDS

        if not tokens1 or not tokens2:
            return 1.0 # Max distance

        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        similarity = intersection / union
        return 1.0 - similarity

class BeliefLifecycleManager:
    """
    Manages the complete lifecycle of cognitive beliefs (Phase 2).
    """
    def __init__(self, cte: CognitiveTimelineEngine):
        self.cte = cte
        self.reinforcement = ReinforcementTracker()
        self.decay = DecayEngine()
        self.contradiction = ContradictionDetector()
        self.clustering = SemanticClusterManager()

    def process_lifecycle(self):
        """
        Main maintenance cycle:
        1. Apply decay
        2. Detect contradictions
        3. Reinforce/Cluster
        """
        now = datetime.now()

        # 1. Decay
        for convict in self.cte._convicts.values():
            self.decay.apply_decay(convict)

        # 2. Contradictions (Naive O(N^2) for now, acceptable for small N)
        beliefs = list(self.cte._convicts.values())
        for i in range(len(beliefs)):
            for j in range(i + 1, len(beliefs)):
                if self.contradiction.detect(beliefs[i].belief, beliefs[j].belief):
                    # Handle contradiction (e.g. weaken both or flag)
                    logger.warning(f"⚔️ Contradiction detected: '{beliefs[i].belief}' vs '{beliefs[j].belief}'")

    def register_belief(self, belief_text: str, metadata: Dict[str, Any] = None):
        """
        Register or update a belief.
        """
        if metadata is None: metadata = {}

        # Check existence
        if belief_text in self.cte._convicts:
            # Fix 7: Fix metadata loss
            existing = self.cte._convicts[belief_text]
            # Since Convict is a dataclass without a flexible metadata dict (unless we monkeypatch),
            # we check if it has one.
            if not hasattr(existing, 'metadata'):
                existing.metadata = {}
            existing.metadata.update(metadata)

            self.reinforcement.reinforce(existing)
        else:
            # Create new (via CTE mechanism usually, but here manual helper)
            pass
