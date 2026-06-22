"""Provider-neutral contracts for the LS Trusted Cooperative Runtime.

The package intentionally contains no live provider integrations. It defines
small stable data structures and adapter protocols that ecosystem modules can
implement independently.
"""

from .contracts import (
    CognitiveTrail,
    DecisionCode,
    EvidenceDecision,
    ExecutionAuthorization,
    ReplayDecision,
    ReplayRecord,
    ReusableArtifact,
    RoleAssignment,
    RouteDecision,
    TaskEnvelope,
    TrailEvent,
    TrailEventType,
    WorkflowPlan,
    WorkflowStep,
)
from .protocols import (
    AuthorizationBundleAdapter,
    CausalAuditAdapter,
    EventStoreAdapter,
    EvidenceGateAdapter,
    ExecutionControlAdapter,
    ReplayAdapter,
    RoutingAdapter,
    WorkflowOrchestrator,
)

__all__ = [
    "AuthorizationBundleAdapter",
    "CausalAuditAdapter",
    "CognitiveTrail",
    "DecisionCode",
    "EventStoreAdapter",
    "EvidenceDecision",
    "EvidenceGateAdapter",
    "ExecutionAuthorization",
    "ExecutionControlAdapter",
    "ReplayAdapter",
    "ReplayDecision",
    "ReplayRecord",
    "ReusableArtifact",
    "RoleAssignment",
    "RouteDecision",
    "RoutingAdapter",
    "TaskEnvelope",
    "TrailEvent",
    "TrailEventType",
    "WorkflowOrchestrator",
    "WorkflowPlan",
    "WorkflowStep",
]
