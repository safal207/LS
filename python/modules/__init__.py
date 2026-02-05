# Phase 5?9: Existing modules
from .agent import AgentLoop
from .cognitive_flow import (
    PresenceState,
    TransitionEngine,
    CognitiveFlow,
    AttentionState,
    AttentionEngine,
)

# Phase 10: Coordinator (NEW)
from .coordinator import (
    Coordinator,
    ModeDetector,
    ContextSync,
    CognitiveHygiene,
)

__all__ = [
    # Existing
    "AgentLoop",
    "PresenceState",
    "TransitionEngine",
    "CognitiveFlow",
    "AttentionState",
    "AttentionEngine",

    # New (Phase 10)
    "Coordinator",
    "ModeDetector",
    "ContextSync",
    "CognitiveHygiene",
]
