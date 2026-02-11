import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any

from .models import Convict, ConvictStatus, ReinforcementEvent, Contradiction, BeliefCluster
from .events import BeliefEvent, BeliefDeprecatedEvent, BeliefConflictedEvent
from .promotion import BeliefPromotionSystem
from .temporal_index import TemporalIndex

logger = logging.getLogger("BeliefLifecycle")

# --- Components (Ported from belief_system.py) ---

class DecayEngine:
    def __init__(self, base_half_life_hours: float = 24.0, resilience_factor: float = 0.1):
        self.base_half_life = base_half_life_hours
        self.resilience = resilience_factor
        self.min_strength_active = 0.1
        self.deprecation_threshold = 0.05

    def calculate_decay_factor(self, convict: Convict, now: datetime) -> float:
        if not convict.last_reinforced_at:
            last_event = convict.created_at
        else:
            last_event = convict.last_reinforced_at

        # Ensure aware/naive compatibility if mixed
        if now.tzinfo is not None and last_event.tzinfo is None:
             last_event = last_event.replace(tzinfo=timezone.utc)
        elif now.tzinfo is None and last_event.tzinfo is not None:
             now = now.replace(tzinfo=timezone.utc)

        delta_hours = (now - last_event).total_seconds() / 3600.0
        if delta_hours < 0:
            return 1.0

        effective_half_life = self.base_half_life * (1 + self.resilience * convict.reinforcement_count)
        if effective_half_life <= 0:
             return 0.0

        factor = 0.5 ** (delta_hours / effective_half_life)
        return factor

    def apply_decay(self, convict: Convict, now: datetime) -> ConvictStatus:
        factor = self.calculate_decay_factor(convict, now)
        old_status = convict.status

        convict.confidence *= factor
        convict.strength *= factor

        if convict.strength < self.deprecation_threshold:
            convict.status = ConvictStatus.DEPRECATED
        elif convict.strength < self.min_strength_active:
            convict.status = ConvictStatus.DECAYING

        if old_status in [ConvictStatus.ACTIVE, ConvictStatus.MATURE] and convict.status == ConvictStatus.DECAYING:
             convict.decay_cycles_survived += 1

        return convict.status

class ReinforcementTracker:
    def __init__(self, cooldown_seconds: float = 60.0, base_boost: float = 0.1):
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.base_boost = base_boost

    def can_reinforce(self, convict: Convict, now: datetime) -> bool:
        if not convict.last_reinforced_at:
            return True
        return (now - convict.last_reinforced_at) > self.cooldown

    def calculate_boost(self, convict: Convict) -> float:
        return self.base_boost * (1.0 - convict.confidence)

    def reinforce(self, convict: Convict, source: str, context: Dict[str, Any], strength_signal: float, now: datetime) -> bool:
        if not self.can_reinforce(convict, now):
            return False

        boost = self.calculate_boost(convict)
        strength_multiplier = max(0.3, convict.strength)
        actual_boost = boost * strength_signal * strength_multiplier

        convict.confidence = min(1.0, convict.confidence + actual_boost)
        convict.strength = min(1.0, convict.strength + (0.05 * strength_signal))

        convict.last_reinforced_at = now
        convict.reinforcement_count += 1

        event = ReinforcementEvent(
            timestamp=now,
            source=source,
            context=context,
            strength=strength_signal
        )
        convict.reinforcement_history.append(event)

        if len(convict.reinforcement_history) > 50:
            convict.reinforcement_history.pop(0)

        # Restore status
        if convict.status in [ConvictStatus.DECAYING, ConvictStatus.DEPRECATED]:
             convict.status = ConvictStatus.ACTIVE

        return True

class ContradictionDetector:
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
        now = datetime.now(timezone.utc)

        for i in range(len(active_convicts)):
            for j in range(i + 1, len(active_convicts)):
                c1 = active_convicts[i]
                c2 = active_convicts[j]

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

                ctx1 = c1.metadata.get("context_id")
                ctx2 = c2.metadata.get("context_id")

                is_outcome_conflict = False
                if ctx1 and ctx2 and ctx1 == ctx2:
                    if c1.confidence > 0.7 and c2.confidence > 0.7:
                        if similarity < 0.5:
                            is_outcome_conflict = True

                if is_explicit_negation or is_outcome_conflict:
                    severity = 0.5
                    if is_explicit_negation:
                        severity = 0.8
                    if is_outcome_conflict:
                        severity = 0.6

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
        diff = abs(c1.confidence - c2.confidence)
        if diff > 0.3:
            loser = c1 if c1.confidence < c2.confidence else c2
            loser.confidence *= 0.5
            loser.strength *= 0.5
            loser.status = ConvictStatus.CONFLICTED
            contradiction.resolution_strategy = "weaken_lower"
        elif c1.confidence > 0.8 and c2.confidence > 0.8:
            c1.status = ConvictStatus.CONFLICTED
            c2.status = ConvictStatus.CONFLICTED
            contradiction.resolution_strategy = "mark_conflicted_high_stakes"
        else:
            c1.confidence *= 0.7
            c2.confidence *= 0.7
            c1.status = ConvictStatus.CONFLICTED
            c2.status = ConvictStatus.CONFLICTED
            contradiction.resolution_strategy = "weaken_both"

class SemanticClusterManager:
    def _jaccard_distance(self, s1: str, s2: str) -> float:
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
        if not set1 or not set2:
            return 1.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        if union == 0:
            return 1.0
        return 1.0 - (intersection / union)

    def cluster(self, convicts: List[Convict]) -> List[BeliefCluster]:
        threshold = 0.7
        clusters: List[BeliefCluster] = []
        for c in convicts:
            best_cluster = None
            best_dist = threshold
            for cluster in clusters:
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

# --- Main Coordinator ---

class BeliefLifecycleManager:
    """
    Coordinator for belief lifecycle.
    Manages Decay, Reinforcement, Contradiction, Promotion, and Event Notification.
    """
    def __init__(self):
        self._convicts: Dict[str, Convict] = {}
        self.decay_engine = DecayEngine()
        self.tracker = ReinforcementTracker()
        self.contradiction_detector = ContradictionDetector()
        self.cluster_manager = SemanticClusterManager()
        self.promotion_system = BeliefPromotionSystem()
        self.temporal_index = TemporalIndex()

        self.contradictions: List[Contradiction] = []
        self._observers = [] # List of objects with handle_event(event) method
        self._ingest_existing_beliefs()

    def _ingest_existing_beliefs(self) -> None:
        """Load any pre-existing beliefs into the temporal index."""
        for convict in self._convicts.values():
            self.temporal_index.add(self._belief_timestamp(convict), convict.id)

    def add_observer(self, observer):
        self._observers.append(observer)

    def _notify(self, event: BeliefEvent):
        for obs in self._observers:
            if hasattr(obs, 'handle_event'):
                try:
                    obs.handle_event(event)
                except Exception as e:
                    logger.error(f"Observer error: {e}")

    def belief_exists(self, convict_id: str) -> bool:
        """Return True if a belief with this ID exists."""
        return convict_id in self._convicts

    def register_belief(self, text: str, metadata: Dict[str, Any] | None = None) -> Convict:
        for c in self._convicts.values():
            if c.belief == text:
                if metadata:
                    c.metadata.update(metadata)
                return c

        new_id = f"convict_{uuid.uuid4()}"
        if metadata is None:
            metadata = {}

        now = datetime.now(timezone.utc)
        convict = Convict(
            id=new_id,
            belief=text,
            confidence=0.5,
            strength=0.1,
            created_at=now,
            last_updated_at=now,
            metadata=metadata
        )
        self._convicts[new_id] = convict
        self.temporal_index.add(now, new_id)
        logger.info(f"✨ Registered new belief: {text}")
        return convict

    def reinforce(self, convict_id: str, source: str, context: Dict[str, Any], strength: float) -> bool:
        convict = self._convicts.get(convict_id)
        if not convict:
            return False

        now = datetime.now(timezone.utc)
        previous_ts = self._belief_timestamp(convict)
        success = self.tracker.reinforce(convict, source, context, strength, now)
        if success:
            convict.last_updated_at = now
            self._refresh_temporal_index(convict_id, previous_ts, now)
            logger.info(f"💪 Reinforced: {convict.belief}")
        return success

    def decay_all(self, now: Optional[datetime] = None) -> List[str]:
        if now is None:
            now = datetime.now(timezone.utc)
        decayed_ids = []

        for c in self._convicts.values():
            if c.status == ConvictStatus.DEPRECATED:
                continue

            old_status = c.status
            old_strength = c.strength
            new_status = self.decay_engine.apply_decay(c, now)
            status_changed = new_status != old_status
            strength_changed = abs(c.strength - old_strength) > 0.001
            if status_changed or strength_changed:
                previous_ts = self._belief_timestamp(c)
                c.last_updated_at = now
                self._refresh_temporal_index(c.id, previous_ts, now)

            if new_status == ConvictStatus.DECAYING and old_status in [ConvictStatus.ACTIVE, ConvictStatus.MATURE]:
                decayed_ids.append(c.id)
                logger.info(f"🥀 Belief decaying: {c.belief}")

            if new_status == ConvictStatus.DEPRECATED and old_status != ConvictStatus.DEPRECATED:
                logger.info(f"💀 Belief deprecated: {c.belief}")
                self._notify(BeliefDeprecatedEvent(
                    timestamp=now,
                    convict_id=c.id,
                    belief_text=c.belief,
                    reason="Strength dropped below threshold"
                ))

        return decayed_ids

    def detect_contradictions(self) -> List[Contradiction]:
        active = [c for c in self._convicts.values() if c.status in [ConvictStatus.ACTIVE, ConvictStatus.MATURE, ConvictStatus.DECAYING]]
        new_conflicts = self.contradiction_detector.detect(active)

        for conflict in new_conflicts:
            c1 = self._convicts[conflict.belief_a_id]
            c2 = self._convicts[conflict.belief_b_id]
            self.contradiction_detector.resolve(conflict, c1, c2)
            now = datetime.now(timezone.utc)
            previous_ts_c1 = self._belief_timestamp(c1)
            previous_ts_c2 = self._belief_timestamp(c2)
            c1.last_updated_at = now
            c2.last_updated_at = now
            self._refresh_temporal_index(c1.id, previous_ts_c1, now)
            self._refresh_temporal_index(c2.id, previous_ts_c2, now)
            self.contradictions.append(conflict)
            logger.warning(f"⚔️ Conflict: {c1.belief} vs {c2.belief}")

            self._notify(BeliefConflictedEvent(
                timestamp=now,
                convict_id=c1.id,
                belief_text=c1.belief,
                conflict_id=conflict.id,
                opponent_id=c2.id,
                context=conflict.context
            ))
            self._notify(BeliefConflictedEvent(
                timestamp=now,
                convict_id=c2.id,
                belief_text=c2.belief,
                conflict_id=conflict.id,
                opponent_id=c1.id,
                context=conflict.context
            ))

        return new_conflicts

    def promote_mature_beliefs(self) -> List[Convict]:
        promoted = []
        now = datetime.now(timezone.utc)
        for c in self.get_active_beliefs():
            can_promote, reason = self.promotion_system.can_be_promoted(c, now)
            if can_promote:
                previous_ts = self._belief_timestamp(c)
                c.status = ConvictStatus.MATURE
                c.last_updated_at = now
                self._refresh_temporal_index(c.id, previous_ts, now)
                promoted.append(c)
                logger.info(f"🎓 Belief Promoted to MATURE: {c.belief}")
        return promoted

    def _normalize_timestamp(self, timestamp: datetime) -> datetime:
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=timezone.utc)
        return timestamp

    def _belief_timestamp(self, convict: Convict) -> datetime:
        """
        Return the most recent meaningful timestamp for a belief.
        Guaranteed to be timezone-aware.
        """
        timestamp = (
            convict.last_updated_at
            or convict.last_reinforced_at
            or convict.created_at
            or datetime.now(timezone.utc)
        )
        return self._normalize_timestamp(timestamp)

    def _refresh_temporal_index(self, convict_id: str, previous_ts: datetime, new_ts: datetime) -> None:
        self.temporal_index.remove(self._normalize_timestamp(previous_ts), convict_id)
        self.temporal_index.add(self._normalize_timestamp(new_ts), convict_id)

    def get_beliefs_since(self, timestamp: datetime, *, include_deprecated: bool = False) -> List[Convict]:
        """Return beliefs updated at or after the provided timestamp."""
        now = datetime.now(timezone.utc)
        ids = self.temporal_index.query_range(self._normalize_timestamp(timestamp), now)
        beliefs = [self._convicts[c_id] for c_id in ids if c_id in self._convicts]
        if include_deprecated:
            return beliefs
        return [belief for belief in beliefs if belief.status != ConvictStatus.DEPRECATED]

    def get_beliefs_in_range(self, start: datetime, end: datetime, *, include_deprecated: bool = False) -> List[Convict]:
        """Return beliefs updated within the [start, end] range."""
        if start > end:
            return []
        ids = self.temporal_index.query_range(self._normalize_timestamp(start), self._normalize_timestamp(end))
        beliefs = [self._convicts[c_id] for c_id in ids if c_id in self._convicts]
        if include_deprecated:
            return beliefs
        return [belief for belief in beliefs if belief.status != ConvictStatus.DEPRECATED]

    def get_recent_by_hours(self, hours: int) -> List[Convict]:
        """Return beliefs updated within the last N hours."""
        if hours <= 0:
            return []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return self.get_beliefs_since(cutoff)

    def get_recent_changes(self, hours: int) -> List[Convict]:
        """Deprecated: use get_recent_by_hours."""
        return self.get_recent_by_hours(hours)

    def update_clusters(self) -> List[BeliefCluster]:
        """Recompute clusters and update timestamps for affected beliefs."""
        active = self.get_active_beliefs()
        previous_clusters = {convict.id: convict.cluster_id for convict in active}
        clusters = self.cluster_manager.cluster(active)
        now = datetime.now(timezone.utc)
        for convict in active:
            if convict.cluster_id != previous_clusters.get(convict.id):
                previous_ts = self._belief_timestamp(convict)
                convict.last_updated_at = now
                self._refresh_temporal_index(convict.id, previous_ts, now)
        return clusters

    def get_mature_beliefs(self) -> List[Convict]:
        return [c for c in self._convicts.values() if c.status == ConvictStatus.MATURE]

    def get_active_beliefs(self) -> List[Convict]:
        return [c for c in self._convicts.values() if c.status in [ConvictStatus.ACTIVE, ConvictStatus.MATURE]]

    def get_belief_count(self) -> int:
        return len(self._convicts)

    def get_summary(self) -> Dict[str, Any]:
        active_count = sum(1 for c in self._convicts.values() if c.status == ConvictStatus.ACTIVE)
        mature_count = sum(1 for c in self._convicts.values() if c.status == ConvictStatus.MATURE)
        decaying_count = sum(1 for c in self._convicts.values() if c.status == ConvictStatus.DECAYING)
        return {
            "total_beliefs": len(self._convicts),
            "active": active_count,
            "mature": mature_count,
            "decaying": decaying_count,
            "conflicts_detected": len(self.contradictions)
        }
