from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from .authorization import AuthorizationBundle
from .causal import CausalAuditReport
from .contracts import CognitiveTrail, EvidenceDecision, RouteDecision, WorkflowPlan
from .execution import ExecutionRecord, ProtectedAction
from .replay_models import ReplayOutcome


JsonObject = Mapping[str, Any]


@runtime_checkable
class WorkflowOrchestrator(Protocol):
    """Create, assign, revise, and trace provider-neutral workflow plans."""

    @property
    def adapter_name(self) -> str:
        ...

    def create_plan(self, task: JsonObject, context: JsonObject) -> WorkflowPlan:
        ...

    def assign_roles(
        self,
        plan: WorkflowPlan,
        available_capabilities: Mapping[str, str],
    ) -> WorkflowPlan:
        ...

    def revise_plan(
        self,
        plan: WorkflowPlan,
        results: Sequence[JsonObject],
        reason: str,
    ) -> WorkflowPlan:
        ...

    def revision_trail(self, plan: WorkflowPlan) -> CognitiveTrail:
        ...


@runtime_checkable
class RoutingAdapter(Protocol):
    """Select a backend for a declared capability."""

    @property
    def adapter_name(self) -> str:
        ...

    def route(self, request: JsonObject) -> RouteDecision:
        ...


@runtime_checkable
class CausalAuditAdapter(Protocol):
    """Validate causal ancestry without owning workflow planning."""

    @property
    def adapter_name(self) -> str:
        ...

    def audit(self, trail: CognitiveTrail) -> CausalAuditReport:
        ...


@runtime_checkable
class EvidenceGateAdapter(Protocol):
    """Return ALLOW, HOLD, BLOCK, or ESCALATE from inspectable evidence."""

    @property
    def adapter_name(self) -> str:
        ...

    def decide(self, request: JsonObject) -> EvidenceDecision:
        ...


@runtime_checkable
class AuthorizationBundleAdapter(Protocol):
    """Build a portable authorization bundle from accepted intent and evidence."""

    @property
    def adapter_name(self) -> str:
        ...

    def build(
        self,
        decision: EvidenceDecision,
        request: JsonObject,
    ) -> AuthorizationBundle:
        ...


@runtime_checkable
class ExecutionControlAdapter(Protocol):
    """Enforce Gate -> Incubate -> Commit -> Execute for protected effects."""

    @property
    def adapter_name(self) -> str:
        ...

    def run(
        self,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        *,
        now: str,
        preconditions_met: bool = True,
    ) -> ExecutionRecord:
        ...

    def recover(
        self,
        bundle: AuthorizationBundle,
        action: ProtectedAction,
        *,
        now: str,
        preconditions_met: bool = True,
    ) -> ExecutionRecord:
        ...


@runtime_checkable
class ReplayAdapter(Protocol):
    """Inspect a durable path without rerunning models, tools, or effects."""

    @property
    def adapter_name(self) -> str:
        ...

    def replay(
        self,
        events: Sequence[JsonObject],
        *,
        now: str,
        baseline_payload_digests: Optional[Mapping[str, str]] = None,
        corrupted_tail: bool = False,
    ) -> ReplayOutcome:
        ...


@runtime_checkable
class EventStoreAdapter(Protocol):
    """Append and read durable workflow events."""

    @property
    def adapter_name(self) -> str:
        ...

    def append(self, event: JsonObject) -> str:
        ...

    def read(self, trail_id: str) -> Sequence[JsonObject]:
        ...
