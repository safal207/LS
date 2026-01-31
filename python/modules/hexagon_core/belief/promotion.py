from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple, Optional, Set

from .models import Convict, ConvictStatus

@dataclass(frozen=True)
class PromotionCriteria:
    min_age_hours: float = 6.0
    min_decay_cycles: int = 3
    min_reinforcement_count: int = 2
    min_confidence: float = 0.75
    min_unique_sources: int = 2

class BeliefPromotionSystem:
    def __init__(self, criteria: PromotionCriteria = None):
        if criteria is None:
            self.criteria = PromotionCriteria()
        else:
            self.criteria = criteria

    def can_be_promoted(self, convict: Convict, now: datetime) -> Tuple[bool, Optional[str]]:
        """
        Checks if a convict meets the criteria for promotion to MATURE status.
        Returns (True, None) if promotable, else (False, reason).
        """
        # 1. Check Status
        if convict.status not in [ConvictStatus.ACTIVE, ConvictStatus.DECAYING]:
             return False, f"Status is {convict.status.value}, not active/decaying"

        # 2. Check Age
        # Ensure timezone awareness handling if convict.created_at is tz-aware
        # The spec says "all datetime -> timezone-aware (UTC)"
        # Assuming inputs are compatible.

        age_hours = (now - convict.created_at).total_seconds() / 3600.0
        if age_hours < self.criteria.min_age_hours:
            return False, f"Age {age_hours:.2f}h < {self.criteria.min_age_hours}h"

        # 3. Check Decay Cycles
        if convict.decay_cycles_survived < self.criteria.min_decay_cycles:
             return False, f"Decay cycles {convict.decay_cycles_survived} < {self.criteria.min_decay_cycles}"

        # 4. Check Reinforcement Count
        if convict.reinforcement_count < self.criteria.min_reinforcement_count:
            return False, f"Reinforcements {convict.reinforcement_count} < {self.criteria.min_reinforcement_count}"

        # 5. Check Confidence
        if convict.confidence < self.criteria.min_confidence:
             return False, f"Confidence {convict.confidence:.2f} < {self.criteria.min_confidence}"

        # 6. Check Unique Sources
        sources: Set[str] = set()
        for event in convict.reinforcement_history:
            if event.source:
                sources.add(event.source)

        # Also consider origin if recorded in metadata, though history is better source of truth for reinforcements.
        # But wait, the first "reinforcement" might be creation?
        # Usually creation isn't in reinforcement history unless explicitly added.
        # Spec says "minuniquesources: int = 2".

        if len(sources) < self.criteria.min_unique_sources:
             return False, f"Unique sources {len(sources)} < {self.criteria.min_unique_sources}"

        return True, None
