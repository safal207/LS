from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Mapping, Optional


WORKFLOW_PLAN_VERSION = "trusted_runtime.workflow_plan.v0.1"
ROUTE_DECISION_VERSION = "trusted_runtime.route_decision.v0.1"
COGNITIVE_TRAIL_VERSION = "trusted_runtime.cognitive_trail.v0.1"
EVIDENCE_DECISION_VERSION = "trusted_runtime.evidence_decision.v0.1"
EXECUTION_AUTHORIZATION_VERSION = "trusted_runtime.execution_authorization.v0.1"
REPLAY_RECORD_VERSION = "trusted_runtime.replay_record.v0.1"
REUSABLE_ARTIFACT_VERSION = "trusted_runtime.reusable_artifact.v0.1"


class DecisionCode(str, Enum):
    """Stable evidence decision vocabulary shared across adapters."""

    ALLOW = "ALLOW"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class ReplayDecision(str, Enum):
    """Stable replay result vocabulary."""

    ADMISSIBLE = "ADMISSIBLE"
    DRIFTED = "DRIFTED"
    REJECTED = "REJECTED"


class TrailEventType(str, Enum):
    """Initial event vocabulary for an inspectable Trusted Runtime trail."""

    TASK_RECEIVED = "TASK_RECEIVED"
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_REVISED = "PLAN_REVISED"
    ROUTE_SELECTED = "ROUTE_SELECTED"
    WORK_COMPLETED = "WORK_COMPLETED"
    CAUSAL_AUDIT = "CAUSAL_AUDIT"
    EVIDENCE_DECISION = "EVIDENCE_DECISION"
    AUTHORIZATION_ISSUED = "AUTHORIZATION_ISSUED"
    EXECUTION_COMMITTED = "EXECUTION_COMMITTED"
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"
    REPLAY_CHECKED = "REPLAY_CHECKED"
    ARTIFACT_CREATED = "ARTIFACT_CREATED"


def _primitive(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _primitive(item) for key, item in asdict(value).items()}
    if isinstance(value, tuple):
        return [_primitive(item) for item in value]
    if isinstance(value, list):
        return [_primitive(item) for item in value]
    if isinstance(value, dict):
        return {key: _primitive(item) for key, item in value.items()}
    return value


def _require_non_empty(instance: Any, names: tuple[str, ...]) -> None:
    for name in names:
        if not getattr(instance, name):
            raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    trail_id: str
    intent: str
    actor: str
    created_at: str
    evidence_refs: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(
            self,
            ("task_id", "trail_id", "intent", "actor", "created_at"),
        )


@dataclass(frozen=True)
class RoleAssignment:
    role_id: str
    capability: str
    actor: str
    parent_cause: str

    def __post_init__(self) -> None:
        _require_non_empty(
            self,
            ("role_id", "capability", "actor", "parent_cause"),
        )


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    role_id: str
    action: str
    parent_cause: str
    depends_on: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(
            self,
            ("step_id", "role_id", "action", "parent_cause"),
        )
        if self.step_id == self.parent_cause:
            raise ValueError("a workflow step cannot be its own parent cause")


@dataclass(frozen=True)
class WorkflowPlan:
    task: TaskEnvelope
    roles: tuple[RoleAssignment, ...]
    steps: tuple[WorkflowStep, ...]
    schema_version: str = WORKFLOW_PLAN_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != WORKFLOW_PLAN_VERSION:
            raise ValueError(f"unsupported workflow schema version: {self.schema_version}")
        if not self.roles:
            raise ValueError("workflow plan requires at least one role")
        if not self.steps:
            raise ValueError("workflow plan requires at least one step")

        role_ids = [role.role_id for role in self.roles]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("role_id values must be unique")

        step_ids = [step.step_id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("step_id values must be unique")

        known_roles = set(role_ids)
        prior_causes = {self.task.task_id}
        prior_steps: set[str] = set()

        for role in self.roles:
            if role.parent_cause != self.task.task_id:
                raise ValueError(
                    f"role {role.role_id!r} must descend from task {self.task.task_id!r}"
                )

        for step in self.steps:
            if step.role_id not in known_roles:
                raise ValueError(
                    f"step {step.step_id!r} references unknown role {step.role_id!r}"
                )
            if step.parent_cause not in prior_causes:
                raise ValueError(
                    f"step {step.step_id!r} references unavailable parent cause "
                    f"{step.parent_cause!r}"
                )
            unknown_dependencies = set(step.depends_on) - prior_steps
            if unknown_dependencies:
                raise ValueError(
                    f"step {step.step_id!r} has unavailable dependencies: "
                    f"{sorted(unknown_dependencies)}"
                )
            if step.step_id in step.depends_on:
                raise ValueError(f"step {step.step_id!r} cannot depend on itself")
            prior_steps.add(step.step_id)
            prior_causes.add(step.step_id)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "WorkflowPlan":
        task_payload = payload["task"]
        task = TaskEnvelope(
            task_id=task_payload["task_id"],
            trail_id=task_payload["trail_id"],
            intent=task_payload["intent"],
            actor=task_payload["actor"],
            created_at=task_payload["created_at"],
            evidence_refs=tuple(task_payload.get("evidence_refs", ())),
            metadata=dict(task_payload.get("metadata", {})),
        )
        roles = tuple(RoleAssignment(**item) for item in payload["roles"])
        steps = tuple(
            WorkflowStep(
                step_id=item["step_id"],
                role_id=item["role_id"],
                action=item["action"],
                parent_cause=item["parent_cause"],
                depends_on=tuple(item.get("depends_on", ())),
                evidence_refs=tuple(item.get("evidence_refs", ())),
            )
            for item in payload["steps"]
        )
        return cls(
            task=task,
            roles=roles,
            steps=steps,
            schema_version=payload.get("schema_version", WORKFLOW_PLAN_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


@dataclass(frozen=True)
class RouteDecision:
    route_id: str
    task_id: str
    trail_id: str
    role_id: str
    capability: str
    adapter: str
    actor: str
    selected_backend: str
    considered_backends: tuple[str, ...]
    reason: str
    created_at: str
    parent_cause: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ROUTE_DECISION_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ROUTE_DECISION_VERSION:
            raise ValueError(f"unsupported route decision version: {self.schema_version}")
        _require_non_empty(
            self,
            (
                "route_id",
                "task_id",
                "trail_id",
                "role_id",
                "capability",
                "adapter",
                "actor",
                "selected_backend",
                "reason",
                "created_at",
                "parent_cause",
            ),
        )
        if not self.considered_backends:
            raise ValueError("route decision requires considered backends")
        if self.selected_backend not in self.considered_backends:
            raise ValueError("selected backend must appear in considered backends")
        if len(self.considered_backends) != len(set(self.considered_backends)):
            raise ValueError("considered backends must be unique")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "RouteDecision":
        return cls(
            route_id=payload["route_id"],
            task_id=payload["task_id"],
            trail_id=payload["trail_id"],
            role_id=payload["role_id"],
            capability=payload["capability"],
            adapter=payload["adapter"],
            actor=payload["actor"],
            selected_backend=payload["selected_backend"],
            considered_backends=tuple(payload["considered_backends"]),
            reason=payload["reason"],
            created_at=payload["created_at"],
            parent_cause=payload["parent_cause"],
            metadata=dict(payload.get("metadata", {})),
            schema_version=payload.get("schema_version", ROUTE_DECISION_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


@dataclass(frozen=True)
class TrailEvent:
    event_id: str
    task_id: str
    trail_id: str
    event_type: TrailEventType
    actor: str
    created_at: str
    parent_cause: str
    evidence_refs: tuple[str, ...] = ()
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(
            self,
            (
                "event_id",
                "task_id",
                "trail_id",
                "actor",
                "created_at",
                "parent_cause",
            ),
        )
        if self.event_id == self.parent_cause:
            raise ValueError("a trail event cannot be its own parent cause")


@dataclass(frozen=True)
class CognitiveTrail:
    task_id: str
    trail_id: str
    actor: str
    created_at: str
    events: tuple[TrailEvent, ...]
    schema_version: str = COGNITIVE_TRAIL_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != COGNITIVE_TRAIL_VERSION:
            raise ValueError(f"unsupported cognitive trail version: {self.schema_version}")
        _require_non_empty(self, ("task_id", "trail_id", "actor", "created_at"))
        if not self.events:
            raise ValueError("cognitive trail requires at least one event")

        event_ids = [event.event_id for event in self.events]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("trail event identifiers must be unique")

        available_causes = {self.task_id}
        for event in self.events:
            if event.task_id != self.task_id:
                raise ValueError(
                    f"event {event.event_id!r} belongs to another task {event.task_id!r}"
                )
            if event.trail_id != self.trail_id:
                raise ValueError(
                    f"event {event.event_id!r} belongs to another trail {event.trail_id!r}"
                )
            if event.parent_cause not in available_causes:
                raise ValueError(
                    f"event {event.event_id!r} references unavailable parent cause "
                    f"{event.parent_cause!r}"
                )
            available_causes.add(event.event_id)

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CognitiveTrail":
        events = tuple(
            TrailEvent(
                event_id=item["event_id"],
                task_id=item["task_id"],
                trail_id=item["trail_id"],
                event_type=TrailEventType(item["event_type"]),
                actor=item["actor"],
                created_at=item["created_at"],
                parent_cause=item["parent_cause"],
                evidence_refs=tuple(item.get("evidence_refs", ())),
                payload=dict(item.get("payload", {})),
            )
            for item in payload["events"]
        )
        return cls(
            task_id=payload["task_id"],
            trail_id=payload["trail_id"],
            actor=payload["actor"],
            created_at=payload["created_at"],
            events=events,
            schema_version=payload.get("schema_version", COGNITIVE_TRAIL_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


@dataclass(frozen=True)
class EvidenceDecision:
    task_id: str
    trail_id: str
    decision: DecisionCode
    reason: str
    policy_version: str
    actor: str
    created_at: str
    evidence_refs: tuple[str, ...]
    parent_cause: str
    schema_version: str = EVIDENCE_DECISION_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EVIDENCE_DECISION_VERSION:
            raise ValueError(f"unsupported evidence decision version: {self.schema_version}")
        _require_non_empty(
            self,
            (
                "task_id",
                "trail_id",
                "reason",
                "policy_version",
                "actor",
                "created_at",
                "parent_cause",
            ),
        )
        if not self.evidence_refs and self.decision is DecisionCode.ALLOW:
            raise ValueError("ALLOW requires at least one evidence reference")

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


@dataclass(frozen=True)
class ExecutionAuthorization:
    authorization_id: str
    task_id: str
    trail_id: str
    decision: DecisionCode
    actor: str
    scope: tuple[str, ...]
    issued_at: str
    expires_at: str
    nonce: str
    evidence_refs: tuple[str, ...]
    policy_version: str
    parent_cause: str
    schema_version: str = EXECUTION_AUTHORIZATION_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != EXECUTION_AUTHORIZATION_VERSION:
            raise ValueError(
                f"unsupported execution authorization version: {self.schema_version}"
            )
        _require_non_empty(
            self,
            (
                "authorization_id",
                "task_id",
                "trail_id",
                "actor",
                "issued_at",
                "expires_at",
                "nonce",
                "policy_version",
                "parent_cause",
            ),
        )
        if self.decision is not DecisionCode.ALLOW:
            raise ValueError("execution authorization requires an ALLOW decision")
        if not self.scope:
            raise ValueError("execution authorization requires a non-empty scope")
        if not self.evidence_refs:
            raise ValueError("execution authorization requires evidence references")

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


@dataclass(frozen=True)
class ReplayRecord:
    replay_id: str
    task_id: str
    trail_id: str
    actor: str
    created_at: str
    source_event_refs: tuple[str, ...]
    decision: ReplayDecision
    reason: str
    drift_refs: tuple[str, ...]
    parent_cause: str
    schema_version: str = REPLAY_RECORD_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REPLAY_RECORD_VERSION:
            raise ValueError(f"unsupported replay record version: {self.schema_version}")
        _require_non_empty(
            self,
            (
                "replay_id",
                "task_id",
                "trail_id",
                "actor",
                "created_at",
                "reason",
                "parent_cause",
            ),
        )
        if not self.source_event_refs:
            raise ValueError("replay record requires source event references")
        if len(self.source_event_refs) != len(set(self.source_event_refs)):
            raise ValueError("source event references must be unique")
        if self.decision is ReplayDecision.ADMISSIBLE and self.drift_refs:
            raise ValueError("ADMISSIBLE replay cannot contain drift references")
        if self.decision is ReplayDecision.DRIFTED and not self.drift_refs:
            raise ValueError("DRIFTED replay requires drift references")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "ReplayRecord":
        return cls(
            replay_id=payload["replay_id"],
            task_id=payload["task_id"],
            trail_id=payload["trail_id"],
            actor=payload["actor"],
            created_at=payload["created_at"],
            source_event_refs=tuple(payload["source_event_refs"]),
            decision=ReplayDecision(payload["decision"]),
            reason=payload["reason"],
            drift_refs=tuple(payload.get("drift_refs", ())),
            parent_cause=payload["parent_cause"],
            schema_version=payload.get("schema_version", REPLAY_RECORD_VERSION),
        )

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)


@dataclass(frozen=True)
class ReusableArtifact:
    artifact_id: str
    task_id: str
    trail_id: str
    created_at: str
    route_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    contribution_refs: tuple[str, ...]
    decision_ref: str
    execution_ref: Optional[str]
    replay_ref: Optional[str]
    schema_version: str = REUSABLE_ARTIFACT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REUSABLE_ARTIFACT_VERSION:
            raise ValueError(f"unsupported artifact version: {self.schema_version}")
        _require_non_empty(
            self,
            ("artifact_id", "task_id", "trail_id", "created_at", "decision_ref"),
        )

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)
