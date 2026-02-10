from dataclasses import dataclass
from datetime import datetime

@dataclass
class BeliefEvent:
    timestamp: datetime
    convict_id: str
    belief_text: str

@dataclass
class BeliefDeprecatedEvent(BeliefEvent):
    reason: str = "decay"

@dataclass
class BeliefConflictedEvent(BeliefEvent):
    conflict_id: str
    opponent_id: str
    context: str

@dataclass
class BeliefRemovedEvent(BeliefEvent):
    reason: str
