"""Read-only Agent Orientation projection for Trusted Runtime artifacts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence

from .contracts import DecisionCode, TrailEventType, WorkflowPlan


ORIENTATION_CONTEXT_VERSION = "trusted_runtime.orientation_context.v0.1"
_DIMENSIONS = (
    "intent",
    "authority",
    "evidence",
    "risk",
    "reversibility",
    "accountability",
)


class OrientationStage(str, Enum):
    PROPOSED = "PROPOSED"
    PLANNED = "PLANNED"
    ROUTED = "ROUTED"
    CAUSALLY_AUDITED = "CAUSALLY_AUDITED"
    EVIDENCE_DECIDED = "EVIDENCE_DECIDED"
    AUTHORIZED = "AUTHORIZED"
    COMMITTED = "COMMITTED"
    EXECUTED = "EXECUTED"
    HELD = "HELD"
    BLOCKED = "BLOCKED"
    ESCALATED = "ESCALATED"
    REPLAYABLE = "REPLAYABLE"


class OrientationConsistencyError(ValueError):
    """Projected artifacts do not belong to one transition."""


@dataclass(frozen=True)
class OrientationContext:
    orientation_id: str
    transition_id: str
    task_id: str
    trail_id: str
    actor: str
    intent: str
    created_at: str
    stage: OrientationStage
    role_ids: tuple[str, ...]
    route_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    causal_parent_refs: tuple[str, ...]
    dimensions: Mapping[str, str]
    actual_state: Mapping[str, Any] = field(default_factory=dict)
    expected_state: Mapping[str, Any] = field(default_factory=dict)
    forbidden_deltas: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    decision: Optional[str] = None
    decision_reason: Optional[str] = None
    authorization_ref: Optional[str] = None
    execution_ref: Optional[str] = None
    effect_ref: Optional[str] = None
    replay_ref: Optional[str] = None
    artifact_ref: Optional[str] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = ORIENTATION_CONTEXT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != ORIENTATION_CONTEXT_VERSION:
            raise ValueError(
                f"unsupported orientation context version: {self.schema_version}"
            )
        required = (
            self.orientation_id,
            self.transition_id,
            self.task_id,
            self.trail_id,
            self.actor,
            self.intent,
            self.created_at,
        )
        if not all(required):
            raise ValueError("orientation context identifiers must not be empty")
        for name, values in (
            ("role_ids", self.role_ids),
            ("route_refs", self.route_refs),
            ("evidence_refs", self.evidence_refs),
            ("causal_parent_refs", self.causal_parent_refs),
            ("forbidden_deltas", self.forbidden_deltas),
            ("constraints", self.constraints),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"orientation context {name} must be unique")
        if tuple(self.dimensions) != _DIMENSIONS:
            raise ValueError(f"orientation dimensions must be ordered as {_DIMENSIONS!r}")
        if self.authorization_ref and self.decision != DecisionCode.ALLOW.value:
            raise ValueError("authorization requires an ALLOW evidence decision")
        if self.execution_ref and not self.authorization_ref:
            raise ValueError("execution requires an authorization reference")
        if self.effect_ref and not self.execution_ref:
            raise ValueError("an effect reference requires an execution reference")
        if self.artifact_ref and not self.replay_ref:
            raise ValueError("a reusable artifact requires a replay reference")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "orientation_id": self.orientation_id,
            "transition_id": self.transition_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "actor": self.actor,
            "intent": self.intent,
            "created_at": self.created_at,
            "stage": self.stage.value,
            "role_ids": list(self.role_ids),
            "route_refs": list(self.route_refs),
            "evidence_refs": list(self.evidence_refs),
            "causal_parent_refs": list(self.causal_parent_refs),
            "dimensions": dict(self.dimensions),
            "actual_state": dict(self.actual_state),
            "expected_state": dict(self.expected_state),
            "forbidden_deltas": list(self.forbidden_deltas),
            "constraints": list(self.constraints),
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "authorization_ref": self.authorization_ref,
            "execution_ref": self.execution_ref,
            "effect_ref": self.effect_ref,
            "replay_ref": self.replay_ref,
            "artifact_ref": self.artifact_ref,
            "metadata": dict(self.metadata),
        }


def project_orientation_context(
    plan: WorkflowPlan,
    *,
    routes: Sequence[Any] = (),
    trail: Optional[Any] = None,
    evidence_decision: Optional[Any] = None,
    authorization: Optional[Any] = None,
    execution: Optional[Any] = None,
    replay: Optional[Any] = None,
    artifact: Optional[Any] = None,
    actual_state: Optional[Mapping[str, Any]] = None,
    expected_state: Optional[Mapping[str, Any]] = None,
    forbidden_deltas: Sequence[str] = (),
    constraints: Sequence[str] = (),
    orientation_id: Optional[str] = None,
    transition_id: Optional[str] = None,
    metadata: Optional[Mapping[str, Any]] = None,
) -> OrientationContext:
    """Compose existing contracts into one validated, read-only view."""

    task = plan.task
    task_id = task.task_id
    trail_id = task.trail_id
    role_ids = tuple(role.role_id for role in plan.roles)
    known_roles = set(role_ids)
    route_items = tuple(routes)
    route_refs = tuple(route.route_id for route in route_items)

    evidence_refs: list[str] = []
    causal_refs: list[str] = []
    _extend_unique(evidence_refs, task.evidence_refs)

    for step in plan.steps:
        _extend_unique(evidence_refs, step.evidence_refs)
        _append_unique(causal_refs, step.parent_cause)

    for route in route_items:
        _require_identity("route", route, task_id, trail_id)
        if route.role_id not in known_roles:
            raise OrientationConsistencyError(
                f"route {route.route_id!r} references unknown role {route.role_id!r}"
            )
        _append_unique(causal_refs, route.parent_cause)

    audited = False
    if trail is not None:
        _require_identity("cognitive trail", trail, task_id, trail_id)
        for event in trail.events:
            _extend_unique(evidence_refs, event.evidence_refs)
            _append_unique(causal_refs, event.parent_cause)
            audited = audited or (
                _enum_value(event.event_type) == TrailEventType.CAUSAL_AUDIT.value
            )

    decision_value: Optional[str] = None
    decision_reason: Optional[str] = None
    if evidence_decision is not None:
        _require_identity("evidence decision", evidence_decision, task_id, trail_id)
        decision_value = _enum_value(evidence_decision.decision)
        if decision_value not in {item.value for item in DecisionCode}:
            raise OrientationConsistencyError(
                f"unsupported evidence decision {decision_value!r}"
            )
        decision_reason = str(evidence_decision.reason)
        _extend_unique(evidence_refs, evidence_decision.evidence_refs)
        _append_unique(causal_refs, evidence_decision.parent_cause)

    authorization_ref: Optional[str] = None
    if authorization is not None:
        _require_identity("authorization", authorization, task_id, trail_id)
        if decision_value != DecisionCode.ALLOW.value:
            raise OrientationConsistencyError(
                "authorization cannot be projected without an ALLOW decision"
            )
        authorization_ref = _first_reference(
            authorization,
            ("authorization_ref", "authorization_id", "bundle_id"),
        )
        _extend_unique(evidence_refs, getattr(authorization, "evidence_refs", ()))
        _extend_unique(causal_refs, getattr(authorization, "causal_audit_refs", ()))
        parent = getattr(authorization, "parent_cause", None)
        if parent:
            _append_unique(causal_refs, parent)

    execution_ref: Optional[str] = None
    effect_ref: Optional[str] = None
    execution_state: Optional[str] = None
    if execution is not None:
        _require_identity("execution", execution, task_id, trail_id)
        if authorization_ref is None:
            raise OrientationConsistencyError(
                "execution cannot be projected without authorization"
            )
        linked_authorization = _optional_text(
            getattr(execution, "authorization_ref", None)
        )
        if linked_authorization != authorization_ref:
            raise OrientationConsistencyError(
                "execution authorization reference does not match projected authorization"
            )
        execution_ref = _first_reference(execution, ("execution_id", "execution_ref"))
        effect_ref = _optional_text(getattr(execution, "effect_ref", None))
        execution_state = _enum_value(getattr(execution, "state", None))

    replay_record = getattr(replay, "record", replay)
    replay_ref: Optional[str] = None
    if replay_record is not None:
        _require_identity("replay", replay_record, task_id, trail_id)
        replay_ref = _optional_text(getattr(replay, "report_ref", None))
        replay_ref = replay_ref or _first_reference(
            replay_record,
            ("replay_id", "replay_ref"),
        )
        _extend_unique(causal_refs, getattr(replay_record, "source_event_refs", ()))
        parent = getattr(replay_record, "parent_cause", None)
        if parent:
            _append_unique(causal_refs, parent)

    artifact_ref: Optional[str] = None
    if artifact is not None:
        _require_identity("artifact", artifact, task_id, trail_id)
        artifact_ref = _first_reference(artifact, ("artifact_id", "artifact_ref"))
        _extend_unique(evidence_refs, getattr(artifact, "evidence_refs", ()))
        _validate_artifact_links(
            artifact,
            route_refs=route_refs,
            authorization=authorization,
            execution_ref=execution_ref,
            replay_ref=replay_ref,
        )

    projection_metadata = dict(metadata or {})
    projection_metadata.setdefault("projection", "read_only")
    projection_metadata.setdefault("source_contract", plan.schema_version)

    return OrientationContext(
        orientation_id=orientation_id or f"orientation:{task_id}",
        transition_id=transition_id or f"transition:{task_id}",
        task_id=task_id,
        trail_id=trail_id,
        actor=task.actor,
        intent=task.intent,
        created_at=task.created_at,
        stage=_derive_stage(
            has_routes=bool(route_items),
            audited=audited,
            decision=decision_value,
            has_authorization=authorization_ref is not None,
            execution_state=execution_state,
            has_replay=replay_ref is not None,
        ),
        role_ids=role_ids,
        route_refs=route_refs,
        evidence_refs=tuple(evidence_refs),
        causal_parent_refs=tuple(causal_refs),
        dimensions=_dimensions(
            decision_value,
            authorization_ref,
            execution,
            projection_metadata,
        ),
        actual_state=dict(actual_state or {}),
        expected_state=dict(expected_state or {}),
        forbidden_deltas=tuple(str(value) for value in forbidden_deltas),
        constraints=tuple(str(value) for value in constraints),
        decision=decision_value,
        decision_reason=decision_reason,
        authorization_ref=authorization_ref,
        execution_ref=execution_ref,
        effect_ref=effect_ref,
        replay_ref=replay_ref,
        artifact_ref=artifact_ref,
        metadata=projection_metadata,
    )


def _validate_artifact_links(
    artifact: Any,
    *,
    route_refs: tuple[str, ...],
    authorization: Optional[Any],
    execution_ref: Optional[str],
    replay_ref: Optional[str],
) -> None:
    unknown_routes = set(getattr(artifact, "route_refs", ())) - set(route_refs)
    if unknown_routes:
        raise OrientationConsistencyError(
            f"artifact references unprojected routes: {sorted(unknown_routes)}"
        )
    artifact_execution = _optional_text(getattr(artifact, "execution_ref", None))
    if artifact_execution and artifact_execution != execution_ref:
        raise OrientationConsistencyError(
            "artifact execution reference does not match projected execution"
        )
    artifact_replay = _optional_text(getattr(artifact, "replay_ref", None))
    if artifact_replay and artifact_replay != replay_ref:
        raise OrientationConsistencyError(
            "artifact replay reference does not match projected replay"
        )
    expected_decision = _optional_text(getattr(authorization, "decision_ref", None))
    artifact_decision = _optional_text(getattr(artifact, "decision_ref", None))
    if expected_decision and artifact_decision != expected_decision:
        raise OrientationConsistencyError(
            "artifact decision reference does not match authorization bundle"
        )


def _derive_stage(
    *,
    has_routes: bool,
    audited: bool,
    decision: Optional[str],
    has_authorization: bool,
    execution_state: Optional[str],
    has_replay: bool,
) -> OrientationStage:
    if has_replay:
        return OrientationStage.REPLAYABLE
    if execution_state == "EXECUTED":
        return OrientationStage.EXECUTED
    if execution_state == "COMMITTED":
        return OrientationStage.COMMITTED
    if execution_state == "HELD":
        return OrientationStage.HELD
    if execution_state in {"REJECTED", "EXPIRED"}:
        return OrientationStage.BLOCKED
    if has_authorization:
        return OrientationStage.AUTHORIZED
    if decision == DecisionCode.HOLD.value:
        return OrientationStage.HELD
    if decision == DecisionCode.BLOCK.value:
        return OrientationStage.BLOCKED
    if decision == DecisionCode.ESCALATE.value:
        return OrientationStage.ESCALATED
    if decision == DecisionCode.ALLOW.value:
        return OrientationStage.EVIDENCE_DECIDED
    if audited:
        return OrientationStage.CAUSALLY_AUDITED
    if has_routes:
        return OrientationStage.ROUTED
    return OrientationStage.PLANNED


def _dimensions(
    decision: Optional[str],
    authorization_ref: Optional[str],
    execution: Optional[Any],
    metadata: Mapping[str, Any],
) -> Mapping[str, str]:
    evidence = {
        DecisionCode.ALLOW.value: "sufficient",
        DecisionCode.HOLD.value: "incomplete",
        DecisionCode.BLOCK.value: "policy_blocked",
        DecisionCode.ESCALATE.value: "requires_stronger_authority",
    }.get(decision, "pending")
    authority = "authorized" if authorization_ref else (
        "pending" if decision is None else "not_authorized"
    )
    return {
        "intent": "declared",
        "authority": authority,
        "evidence": evidence,
        "risk": str(metadata.get("risk", "unclassified")),
        "reversibility": str(metadata.get("reversibility", "unknown")),
        "accountability": (
            "assigned" if getattr(execution, "actor", None) else "task_actor_assigned"
        ),
    }


def _require_identity(
    label: str,
    item: Any,
    task_id: str,
    trail_id: str,
) -> None:
    actual = (getattr(item, "task_id", None), getattr(item, "trail_id", None))
    if actual != (task_id, trail_id):
        raise OrientationConsistencyError(
            f"{label} belongs to task/trail {actual[0]!r}/{actual[1]!r}; "
            f"expected {task_id!r}/{trail_id!r}"
        )


def _enum_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value.value) if isinstance(value, Enum) else str(value)


def _first_reference(item: Any, names: Iterable[str]) -> str:
    candidates = tuple(names)
    for name in candidates:
        value = getattr(item, name, None)
        if value:
            return str(value)
    raise OrientationConsistencyError(
        f"{type(item).__name__} has no usable reference in {candidates!r}"
    )


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _append_unique(target: list[str], value: Any) -> None:
    text = str(value)
    if text and text not in target:
        target.append(text)


def _extend_unique(target: list[str], values: Iterable[Any]) -> None:
    for value in values:
        _append_unique(target, value)
