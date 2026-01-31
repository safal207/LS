from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

class ConvictStatus(Enum):
    ACTIVE = "active"
    DECAYING = "decaying"
    DEPRECATED = "deprecated"
    CONFLICTED = "conflicted"
    MATURE = "mature" # Added for promotion

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
