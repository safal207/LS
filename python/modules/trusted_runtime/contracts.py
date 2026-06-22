from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any, Mapping


WORKFLOW_PLAN_VERSION = "trusted_runtime.workflow_plan.v0.1"
EVIDENCE_DECISION_VERSION = "trusted_runtime.evidence_decision.v0.1"
EXECUTION_AUTHORIZATION_VERSION = "trusted_runtime.execution_authorization.v0.1"
REUSABLE_ARTIFACT_VERSION = "trusted_runtime.reusable_artifact.v0.1"


class DecisionCode(str, Enum):
    """Stable decision vocabulary shared across adapters."""

    ALLOW = "ALLOW"
    HOLD = "HOLD"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


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
        for name in ("task_id", "trail_id", "intent", "actor", "created_at"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class RoleAssignment:
    role_id: str
    capability: str
    actor: str
    parent_cause: str

    def __post_init__(self) -> None:
        for name in ("role_id", "capability", "actor", "parent_cause"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True)
class WorkflowStep:
    step_id: str
    role_id: str
    action: str
    parent_cause: str
    depends_on: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("step_id", "role_id", "action", "parent_cause"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")
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
        known_causes = {self.task.task_id, *step_ids}
        known_dependencies = set(step_ids)

        for role in self.roles:
            if role.parent_cause not in known_causes:
                raise ValueError(
                    f"role {role.role_id!r} references unknown parent cause {role.parent_cause!r}"
                )

        for step in self.steps:
            if step.role_id not in known_roles:
                raise ValueError(
                    f"step {step.step_id!r} references unknown role {step.role_id!r}"
                )
            if step.parent_cause not in known_causes:
                raise ValueError(
                    f"step {step.step_id!r} references unknown parent cause {step.parent_cause!r}"
                )
            unknown_dependencies = set(step.depends_on) - known_dependencies
            if unknown_dependencies:
                raise ValueError(
                    f"step {step.step_id!r} has unknown dependencies: "
                    f"{sorted(unknown_dependencies)}"
                )
            if step.step_id in step.depends_on:
                raise ValueError(f"step {step.step_id!r} cannot depend on itself")

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
        if self.decision is not DecisionCode.ALLOW:
            raise ValueError("execution authorization requires an ALLOW decision")
        if not self.scope:
            raise ValueError("execution authorization requires a non-empty scope")
        if not self.evidence_refs:
            raise ValueError("execution authorization requires evidence references")
        if not self.nonce:
            raise ValueError("execution authorization requires a nonce")

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
    execution_ref: str | None
    replay_ref: str | None
    schema_version: str = REUSABLE_ARTIFACT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != REUSABLE_ARTIFACT_VERSION:
            raise ValueError(f"unsupported artifact version: {self.schema_version}")
        for name in ("artifact_id", "task_id", "trail_id", "created_at", "decision_ref"):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return _primitive(self)
