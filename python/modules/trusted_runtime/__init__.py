"""Provider-neutral contracts for the LS Trusted Cooperative Runtime.

The package intentionally contains no live provider integrations.  It defines
small stable data structures and adapter protocols that ecosystem modules can
implement independently.
"""

from .contracts import (
    DecisionCode,
    EvidenceDecision,
    ExecutionAuthorization,
    ReusableArtifact,
    RoleAssignment,
    TaskEnvelope,
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
    "DecisionCode",
    "EventStoreAdapter",
    "EvidenceDecision",
    "EvidenceGateAdapter",
    "ExecutionAuthorization",
    "ExecutionControlAdapter",
    "ReplayAdapter",
    "ReusableArtifact",
    "RoleAssignment",
    "RoutingAdapter",
    "TaskEnvelope",
    "WorkflowOrchestrator",
    "WorkflowPlan",
    "WorkflowStep",
]
