"""Provider-neutral contracts for the LS Trusted Cooperative Runtime.

The package intentionally contains no live provider integrations. It defines
small stable data structures, adapter protocols, and a deterministic local
orchestrator that ecosystem modules can replace independently.
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
from .orchestrator import (
    DeterministicWorkflowOrchestrator,
    OrchestrationDepthError,
    OrchestratorConfig,
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
    "DeterministicWorkflowOrchestrator",
    "EventStoreAdapter",
    "EvidenceDecision",
    "EvidenceGateAdapter",
    "ExecutionAuthorization",
    "ExecutionControlAdapter",
    "OrchestrationDepthError",
    "OrchestratorConfig",
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
