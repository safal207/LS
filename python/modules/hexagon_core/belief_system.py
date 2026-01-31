import logging
import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any, Tuple, Protocol

logger = logging.getLogger("BeliefSystem")

# --- Data Models ---

class ConvictStatus(Enum):
    ACTIVE = "active"
    DECAYING = "decaying"
    DEPRECATED = "deprecated"
    CONFLICTED = "conflicted"

@dataclass
class ReinforcementEvent:
    timestamp: datetime
    source: str
    context: Dict[str, Any]
    strength: float

@dataclass
class Convict:
    id: str
    belief: str
    confidence: float  # 0.0 - 1.0
    strength: float    # 0.0 - 1.0 (Inertia/Resilience)
    created_at: datetime
    last_reinforced_at: Optional[datetime] = None
    reinforcement_count: int = 0
    reinforcement_history: List[ReinforcementEvent] = field(default_factory=list)
    status: ConvictStatus = ConvictStatus.ACTIVE
    decay_cycles_survived: int = 0
    validation_gaps: int = 0
    semantic_domain: Optional[str] = None
    cluster_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Contradiction:
    id: str
    belief_a_id: str
    belief_b_id: str
    belief_a_text: str
    belief_b_text: str
    severity: float
    detected_at: datetime
    context: str
    resolution_strategy: Optional[str] = None

@dataclass
class BeliefCluster:
    id: str
    center_text: str
    member_ids: List[str]
    domain: Optional[str] = None

# --- Components ---

class DecayEngine:
    """
    Implements exponential decay for beliefs.
    Formula:
      effective_half_life = base_half_life * (1 + resilience * reinforcement_count)
      factor = 0.5 ** (Δt_hours / effective_half_life)
    """
    def __init__(self, base_half_life_hours: float = 24.0, resilience_factor: float = 0.1):
        self.base_half_life = base_half_life_hours
        self.resilience = resilience_factor
        self.min_strength_active = 0.1
        self.deprecation_threshold = 0.05

    def calculate_decay_factor(self, convict: Convict, now: datetime) -> float:
        if not convict.last_reinforced_at:
            # If never reinforced (only created), decay from creation
            last_event = convict.created_at
        else:
            last_event = convict.last_reinforced_at

        delta_hours = (now - last_event).total_seconds() / 3600.0
        if delta_hours < 0:
            return 1.0

        effective_half_life = self.base_half_life * (1 + self.resilience * convict.reinforcement_count)
        # Avoid division by zero
        if effective_half_life <= 0:
             return 0.0 # Instant decay

        factor = 0.5 ** (delta_hours / effective_half_life)
        return factor

    def apply_decay(self, convict: Convict, now: datetime) -> ConvictStatus:
        factor = self.calculate_decay_factor(convict, now)

        old_status = convict.status

        # Apply factor
        convict.confidence *= factor
        convict.strength *= factor

        # Update status based on thresholds
        if convict.strength < self.deprecation_threshold:
            convict.status = ConvictStatus.DEPRECATED
        elif convict.strength < self.min_strength_active:
            convict.status = ConvictStatus.DECAYING
        # Note: We don't automatically restore to ACTIVE here, that happens on reinforcement

        # Increment only when crossing ACTIVE -> DECAYING
        # Or if it's surviving in DECAYING state?
        # Requirement: "Increment only when crossing ACTIVE -> DECAYING" as per diff provided in user prompt?
        # Actually user prompt diff says:
        # if oldstatus == ConvictStatus.ACTIVE and convict.strength < self.minstrength_active:
        #    convict.decaycyclessurvived += 1

        if old_status == ConvictStatus.ACTIVE and convict.strength < self.min_strength_active:
             convict.decay_cycles_survived += 1

        return convict.status

class ReinforcementTracker:
    """
    Manages belief strengthening with anti-spam and diminishing returns.
    """
    def __init__(self, cooldown_seconds: float = 60.0, base_boost: float = 0.1):
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.base_boost = base_boost

    def can_reinforce(self, convict: Convict, now: datetime) -> bool:
        if not convict.last_reinforced_at:
            return True
        return (now - convict.last_reinforced_at) > self.cooldown

    def calculate_boost(self, convict: Convict) -> float:
        """
        boost = base_boost * (1 - current_confidence)
        """
        return self.base_boost * (1.0 - convict.confidence)

    def reinforce(self, convict: Convict, source: str, context: Dict[str, Any], strength_signal: float, now: datetime) -> bool:
        if not self.can_reinforce(convict, now):
            return False

        # Calculate boost
        boost = self.calculate_boost(convict)

        # Apply boost (scaled by the incoming signal strength 0.0-1.0 and strength multiplier)
        strength_multiplier = max(0.3, convict.strength)
        actual_boost = boost * strength_signal * strength_multiplier

        convict.confidence = min(1.0, convict.confidence + actual_boost)
        convict.strength = min(1.0, convict.strength + (0.05 * strength_signal)) # Strength grows slower

        convict.last_reinforced_at = now
        convict.reinforcement_count += 1

        event = ReinforcementEvent(
            timestamp=now,
            source=source,
            context=context,
            strength=strength_signal
        )
        convict.reinforcement_history.append(event)

        # Pruning
        if len(convict.reinforcement_history) > 50:
            convict.reinforcement_history.pop(0)

        # Restore status if needed
        if convict.status in [ConvictStatus.DECAYING, ConvictStatus.DEPRECATED]:
             convict.status = ConvictStatus.ACTIVE

        return True

class ContradictionDetector:
    """
    Detects contradictions using Jaccard similarity and explicit rules.
    """
    def __init__(self):
        pass

    def _jaccard_similarity(self, s1: str, s2: str) -> float:
        set1 = set(s1.lower().split())
        set2 = set(s2.lower().split())
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union

    def detect(self, active_convicts: List[Convict]) -> List[Contradiction]:
        contradictions = []
        now = datetime.now()

        # Pairwise check (O(N^2)) - keep N small or optimize later
        for i in range(len(active_convicts)):
            for j in range(i + 1, len(active_convicts)):
                c1 = active_convicts[i]
                c2 = active_convicts[j]

                # 1. Explicit Negation (Heuristic)
                # High similarity + 'not'/'no' difference?
                # Spec: Jaccard > 0.6 + negation token
                similarity = self._jaccard_similarity(c1.belief, c2.belief)

                negation_tokens = {"not", "no", "never", "false", "fake", "wrong"}
                tokens1 = set(c1.belief.lower().split())
                tokens2 = set(c2.belief.lower().split())

                has_neg_a = not tokens1.isdisjoint(negation_tokens)
                has_neg_b = not tokens2.isdisjoint(negation_tokens)

                is_explicit_negation = False
                if similarity > 0.6:
                    if has_neg_a != has_neg_b:
                        is_explicit_negation = True

                # 2. Outcome Conflicts
                # same context_id (if available), both confident, low similarity?
                # Spec: same context_id, both conf > 0.7, similarity < 0.5
                # We need context_id in metadata
                ctx1 = c1.metadata.get("context_id")
                ctx2 = c2.metadata.get("context_id")

                is_outcome_conflict = False
                if ctx1 and ctx2 and ctx1 == ctx2:
                    if c1.confidence > 0.7 and c2.confidence > 0.7:
                        if similarity < 0.5:
                            is_outcome_conflict = True

                if is_explicit_negation or is_outcome_conflict:
                    # Determine severity
                    severity = 0.5
                    if is_explicit_negation: severity = 0.8
                    if is_outcome_conflict: severity = 0.6

                    contradictions.append(Contradiction(
                        id=f"conflict_{uuid.uuid4()}",
                        belief_a_id=c1.id,
                        belief_b_id=c2.id,
                        belief_a_text=c1.belief,
                        belief_b_text=c2.belief,
                        severity=severity,
                        detected_at=now,
                        context="explicit_negation" if is_explicit_negation else "outcome_conflict"
                    ))

        return contradictions

    def resolve(self, contradiction: Contradiction, c1: Convict, c2: Convict):
        """
        Decision Tree v3:
        if |confA - confB| > 0.3: weaken lower (x0.5), mark CONFLICTED
        elif confA > 0.8 and confB > 0.8: mark both CONFLICTED (needs review)
        else: weaken both (x0.7), mark CONFLICTED
        """
        diff = abs(c1.confidence - c2.confidence)

        if diff > 0.3:
            # Weaken lower
            loser = c1 if c1.confidence < c2.confidence else c2
            loser.confidence *= 0.5
            loser.strength *= 0.5
            loser.status = ConvictStatus.CONFLICTED
            contradiction.resolution_strategy = "weaken_lower"

        elif c1.confidence > 0.8 and c2.confidence > 0.8:
            # High stakes conflict
            c1.status = ConvictStatus.CONFLICTED
            c2.status = ConvictStatus.CONFLICTED
            contradiction.resolution_strategy = "mark_conflicted_high_stakes"

        else:
            # Ambiguous
            c1.confidence *= 0.7
            c2.confidence *= 0.7
            c1.status = ConvictStatus.CONFLICTED
            c2.status = ConvictStatus.CONFLICTED
            contradiction.resolution_strategy = "weaken_both"

class SemanticClusterManager:
    """
    Groups beliefs by meaning.
    Phase 2: Jaccard (default) or Cosine (if embeddings enabled).
    """
    def __init__(self, use_embeddings: bool = False):
        self.use_embeddings = use_embeddings
        # Placeholder for embedding provider

    def _jaccard_distance(self, s1: str, s2: str) -> float:
        # English + Russian Stopwords
        stopwords = {
            # English
            "is", "a", "the", "an", "of", "and", "or", "to", "in", "on", "at", "are", "it", "this", "that",
            # Russian (common)
            "и", "в", "во", "не", "что", "он", "на", "я", "с", "со", "как", "а", "то", "все", "она", "так", "его", "но", "да", "ты", "к", "у", "же", "вы", "за", "бы", "по", "только", "ее", "мне", "было", "вот", "от", "меня", "еще", "нет", "о", "из", "ему", "теперь", "когда", "даже", "ну", "вдруг", "ли", "если", "уже", "или", "ни", "быть", "был", "него", "до", "вас", "нибудь", "опять", "уж", "вам", "ведь", "там", "потом", "себя", "ничего", "ей", "может", "они", "тут", "где", "есть", "надо", "ней", "для", "мы", "тебя", "их", "чем", "была", "сам", "чтоб", "без", "будто", "чего", "раз", "тоже", "себе", "под", "будет", "ж", "тогда", "кто", "этот", "того", "потому", "этого", "какой", "совсем", "ним", "здесь", "этом", "один", "почти", "мой", "тем", "чтобы", "нее", "сейчас", "были", "куда", "зачем", "всех", "никогда", "можно", "при", "наконец", "два", "об", "другой", "хоть", "после", "над", "больше", "тот", "через", "эти", "нас", "про", "всего", "них", "какая", "много", "разве", "три", "эту", "моя", "впрочем", "хорошо", "свою", "этой", "перед", "иногда", "лучше", "чуть", "том", "нельзя", "такой", "им", "более", "всегда", "конечно", "всю", "между"
        }

        def tokenize(text):
            words = text.lower().split()
            return {w for w in words if w not in stopwords}

        set1 = tokenize(s1)
        set2 = tokenize(s2)

        if not set1 or not set2: return 1.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        if union == 0: return 1.0
        return 1.0 - (intersection / union)

    def cluster(self, convicts: List[Convict]) -> List[BeliefCluster]:
        # Simple clustering: Iterate and assign to BEST matching cluster or create new
        # Threshold for Jaccard: distance < 0.7 (similarity > 0.3)
        threshold = 0.7

        clusters: List[BeliefCluster] = []

        for c in convicts:
            best_cluster = None
            best_dist = threshold

            for cluster in clusters:
                # Compare with center (simplification)
                dist = self._jaccard_distance(c.belief, cluster.center_text)
                if dist < best_dist:
                    best_dist = dist
                    best_cluster = cluster

            if best_cluster:
                best_cluster.member_ids.append(c.id)
                c.cluster_id = best_cluster.id
            else:
                new_cluster = BeliefCluster(
                    id=f"cluster_{uuid.uuid4()}",
                    center_text=c.belief,
                    member_ids=[c.id]
                )
                c.cluster_id = new_cluster.id
                clusters.append(new_cluster)

        return clusters

class BeliefLifecycleManager:
    """
    Central manager for the lifecycle of beliefs (Convicts).
    """
    def __init__(self):
        self._convicts: Dict[str, Convict] = {}
        self.decay_engine = DecayEngine()
        self.tracker = ReinforcementTracker()
        self.contradiction_detector = ContradictionDetector()
        self.cluster_manager = SemanticClusterManager()
        self.contradictions: List[Contradiction] = []

    def register_belief(self, text: str, metadata: Dict[str, Any] = None) -> Convict:
        # Check if already exists (by exact text match for now)
        # Ideally we search by ID if provided, or hash text
        for c in self._convicts.values():
            if c.belief == text:
                if metadata:
                    c.metadata.update(metadata)
                return c

        # Create new
        new_id = f"convict_{uuid.uuid4()}"
        if metadata is None: metadata = {}

        # Initial confidence/strength?
        # Spec says:
        # belief with 20 early reinforcements NOT mature
        # So start low?
        # CTE.form_convict used 0.7 confidence, 1 strength.
        # We should align with caller or set defaults.
        # Let's set defaults here, can be reinforced immediately after.

        convict = Convict(
            id=new_id,
            belief=text,
            confidence=0.5, # moderate start
            strength=0.1,   # low inertia
            created_at=datetime.now(),
            metadata=metadata
        )
        self._convicts[new_id] = convict
        logger.info(f"✨ Registered new belief: {text}")
        return convict

    def reinforce(self, convict_id: str, source: str, context: Dict[str, Any], strength: float) -> bool:
        convict = self._convicts.get(convict_id)
        if not convict:
            logger.warning(f"⚠️ Attempted to reinforce unknown convict: {convict_id}")
            return False

        success = self.tracker.reinforce(convict, source, context, strength, datetime.now())
        if success:
            logger.info(f"💪 Reinforced belief: {convict.belief} (conf={convict.confidence:.2f}, str={convict.strength:.2f})")
        return success

    def decay_all(self, now: Optional[datetime] = None) -> List[str]:
        if now is None: now = datetime.now()
        decayed_ids = []
        for c in self._convicts.values():
            if c.status == ConvictStatus.DEPRECATED:
                continue # Already dead

            old_status = c.status
            new_status = self.decay_engine.apply_decay(c, now)

            if new_status == ConvictStatus.DECAYING and old_status == ConvictStatus.ACTIVE:
                decayed_ids.append(c.id)
                logger.info(f"🥀 Belief decaying: {c.belief}")

        return decayed_ids

    def detect_contradictions(self) -> List[Contradiction]:
        active = [c for c in self._convicts.values() if c.status in [ConvictStatus.ACTIVE, ConvictStatus.DECAYING]]
        new_conflicts = self.contradiction_detector.detect(active)

        # Resolve them immediately
        for conflict in new_conflicts:
            c1 = self._convicts[conflict.belief_a_id]
            c2 = self._convicts[conflict.belief_b_id]
            self.contradiction_detector.resolve(conflict, c1, c2)
            self.contradictions.append(conflict)
            logger.warning(f"⚔️ Contradiction detected & resolved: '{c1.belief}' vs '{c2.belief}' -> {conflict.resolution_strategy}")

        return new_conflicts

    def get_summary(self) -> Dict[str, Any]:
        active_count = sum(1 for c in self._convicts.values() if c.status == ConvictStatus.ACTIVE)
        decaying_count = sum(1 for c in self._convicts.values() if c.status == ConvictStatus.DECAYING)
        return {
            "total_beliefs": len(self._convicts),
            "active": active_count,
            "decaying": decaying_count,
            "conflicts_detected": len(self.contradictions)
        }

    def get_active_beliefs(self) -> List[Convict]:
        return [c for c in self._convicts.values() if c.status == ConvictStatus.ACTIVE]
