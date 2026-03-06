import os
from dataclasses import dataclass

@dataclass(frozen=True)
class COTConfig:
    min_age_hours: float = float(os.getenv("CAPU_PROMOTION_MIN_AGE", "6.0"))
    enable_auto_promotion: bool = os.getenv("CAPU_AUTO_PROMOTION", "False").lower() == "true"
    cot_frequency_minutes: int = int(os.getenv("CAPU_COT_FREQUENCY", "5"))

    # Defaults for other promotion criteria if needed
    min_decay_cycles: int = 3
    min_reinforcement_count: int = 2
    min_confidence: float = 0.75
    min_unique_sources: int = 2
