from __future__ import annotations

import pytest

from trusted_runtime.contracts import (
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
from trusted_runtime.execution import (
    CaPUDecisionCode,
    ExecutionRecord,
    ExecutionState,
    ExecutionTransition,
)
from trusted_runtime.orientation import (
    OrientationConsistencyError,
    OrientationStage,
    project_orientation_context,
)


CREATED_AT = "2026-06-23T14:00:00Z"


def _plan() -> WorkflowPlan:
    task = TaskEnvelope(
        task_id="task-1",
        trail_id="trail-1",
        intent="Publish one trusted review result.",
        actor="human:owner",
        created_at=CREATED_AT,
        evidence_refs=("evidence:diff",),
        metadata={"product": "trusted-pr-review"},
    )
    roles = (
        RoleAssignment(
            role_id="reviewer",
            capability="code_review",
            actor="local:reviewer",
            parent_cause=task.task_id,
        ),
        RoleAssignment(
            role_id="verifier",
            capability="evidence_verification",
            actor="local:verifier",
            parent_cause=task.task_id,
        ),
    )
    steps = (
        WorkflowStep(
            step_id="step-review",
            role_id="reviewer",
            action="Review the change.",
            parent_cause=task.task_id,
            evidence_refs=("evidence:diff",),
        ),
        WorkflowStep(
            step_id="step-verify",
            role_id="verifier",
            action="Verify linked evidence.",
            parent_cause="step-review",
            depends_on=("step-review",),
            evidence_refs=("evidence:tests",),
        ),
    )
    return WorkflowPlan(task=task, roles=roles, steps=steps)


def _route(task_id: str = "task-1", trail_id: str = "trail-1") -> RouteDecision:
    return RouteDecision(
        route_id="route-reviewer",
        task_id=task_id,
        trail_id=trail_id,
        role_id="reviewer",
        capability="code_review",
        adapter="dao-lim-local",
        actor="runtime:router",
        selected_backend="backend:reviewer",
        considered_backends=("backend:reviewer", "backend:fallback"),
        reason="Local reviewer is eligible.",
        created_at=CREATED_AT,
        parent_cause="event-plan",
    )


def _trail() -> CognitiveTrail:
    received = TrailEvent(
        event_id="event-received",
        task_id="task-1",
        trail_id="trail-1",
        event_type=TrailEventType.TASK_RECEIVED,
        actor="human:owner",
        created_at=CREATED_AT,
        parent_cause="task-1",
        evidence_refs=("evidence:diff",),
    )
    planned = TrailEvent(
        event_id="event-plan",
        task_id="task-1",
        trail_id="trail-1",
        event_type=TrailEventType.PLAN_CREATED,
        actor="runtime:planner",
        created_at=CREATED_AT,
        parent_cause=received.event_id,
    )
    audited = TrailEvent(
        event_id="event-audit",
        task_id="task-1",
        trail_id="trail-1",
        event_type=TrailEventType.CAUSAL_AUDIT,
        actor="adapter:cml",
        created_at=CREATED_AT,
        parent_cause=planned.event_id,
        evidence_refs=("evidence:causal-audit",),
    )
    return CognitiveTrail(
        task_id="task-1",
        trail_id="trail-1",
        actor="runtime:ls",
        created_at=CREATED_AT,
        events=(received, planned, audited),
    )


def _decision(code: DecisionCode) -> EvidenceDecision:
    return EvidenceDecision(
        task_id="task-1",
        trail_id="trail-1",
        decision=code,
        reason=f"Deterministic {code.value} fixture.",
        policy_version="policy.test.v0.1",
        actor="adapter:pythia",
        created_at=CREATED_AT,
        evidence_refs=("evidence:diff", "evidence:tests") if code is DecisionCode.ALLOW else (),
        parent_cause="event-audit",
    )


def _authorization() -> ExecutionAuthorization:
    return ExecutionAuthorization(
        authorization_id="authorization-1",
        task_id="task-1",
        trail_id="trail-1",
        decision=DecisionCode.ALLOW,
        actor="adapter:proofpath",
        scope=("artifact:write",),
        issued_at="2026-06-23T14:01:00Z",
        expires_at="2026-06-23T15:01:00Z",
        nonce="nonce-1",
        evidence_refs=("evidence:diff", "evidence:tests"),
        policy_version="policy.test.v0.1",
        parent_cause="decision:allow",
    )


def _execution() -> ExecutionRecord:
    transitions = (
        ExecutionTransition(
            sequence=0,
            state=ExecutionState.RECEIVED,
            event_type="EXECUTION_RECEIVED",
            decision_code=CaPUDecisionCode.PERMIT_OK,
            created_at="2026-06-23T14:02:00Z",
            actor="runtime:capu",
            detail="Execution request received.",
        ),
        ExecutionTransition(
            sequence=1,
            state=ExecutionState.COMMITTED,
            event_type="EXECUTION_COMMITTED",
            decision_code=CaPUDecisionCode.PERMIT_OK,
            created_at="2026-06-23T14:03:00Z",
            actor="runtime:capu",
            detail="Durable commit completed.",
        ),
        ExecutionTransition(
            sequence=2,
            state=ExecutionState.EXECUTED,
            event_type="EXECUTION_COMPLETED",
            decision_code=CaPUDecisionCode.COMMIT_EXECUTED,
            created_at="2026-06-23T14:04:00Z",
            actor="runtime:capu",
            detail="Protected effect completed.",
            effect_attempted=True,
        ),
    )
    return ExecutionRecord(
        execution_id="execution-1",
        task_id="task-1",
        trail_id="trail-1",
        action_id="action-1",
        action_ref="action:publish-review",
        action_digest="sha256:action",
        authorization_ref="authorization-1",
        authorization_nonce="nonce-1",
        state=ExecutionState.EXECUTED,
        decision_code=CaPUDecisionCode.COMMIT_EXECUTED,
        actor="runtime:capu",
        created_at="2026-06-23T14:02:00Z",
        updated_at="2026-06-23T14:04:00Z",
        committed_at="2026-06-23T14:03:00Z",
        executed_at="2026-06-23T14:04:00Z",
        effect_ref="effect:review-result-1",
        effect_attempted=True,
        effect_succeeded=True,
        transitions=transitions,
    )


def _replay() -> ReplayRecord:
    return ReplayRecord(
        replay_id="replay-1",
        task_id="task-1",
        trail_id="trail-1",
        actor="adapter:ltp",
        created_at="2026-06-23T14:05:00Z",
        source_event_refs=("event-received", "event-plan", "event-audit"),
        decision=ReplayDecision.ADMISSIBLE,
        reason="The durable path is internally consistent.",
        drift_refs=(),
        parent_cause="execution-1",
    )


def _artifact() -> ReusableArtifact:
    return ReusableArtifact(
        artifact_id="artifact-1",
        task_id="task-1",
        trail_id="trail-1",
        created_at="2026-06-23T14:06:00Z",
        route_refs=("route-reviewer",),
        evidence_refs=("evidence:diff", "evidence:tests"),
        contribution_refs=("contribution:reviewer",),
        decision_ref="decision:allow",
        execution_ref="execution-1",
        replay_ref="replay-1",
    )


def test_projects_allow_path_into_replayable_orientation() -> None:
    context = project_orientation_context(
        _plan(),
        routes=(_route(),),
        trail=_trail(),
        evidence_decision=_decision(DecisionCode.ALLOW),
        authorization=_authorization(),
        execution=_execution(),
        replay=_replay(),
        artifact=_artifact(),
        actual_state={"review_status": "not_published", "effect_count": 0},
        expected_state={"review_status": "published", "effect_count": 1},
        forbidden_deltas=("merge_pull_request", "modify_source_files"),
        constraints=("effect_count <= 1",),
        metadata={"risk": "high", "reversibility": "compensatable"},
    )

    assert context.stage is OrientationStage.REPLAYABLE
    assert context.decision == "ALLOW"
    assert context.authorization_ref == "authorization-1"
    assert context.execution_ref == "execution-1"
    assert context.effect_ref == "effect:review-result-1"
    assert context.replay_ref == "replay-1"
    assert context.artifact_ref == "artifact-1"
    assert context.role_ids == ("reviewer", "verifier")
    assert context.dimensions == {
        "intent": "declared",
        "authority": "authorized",
        "evidence": "sufficient",
        "risk": "high",
        "reversibility": "compensatable",
        "accountability": "assigned",
    }
    assert "evidence:causal-audit" in context.evidence_refs
    assert context.to_dict()["stage"] == "REPLAYABLE"


def test_hold_path_is_terminal_without_authorization_or_effect() -> None:
    context = project_orientation_context(
        _plan(),
        routes=(_route(),),
        trail=_trail(),
        evidence_decision=_decision(DecisionCode.HOLD),
        actual_state={"changed_tests_linked": False},
        expected_state={"changed_tests_linked": True},
    )

    assert context.stage is OrientationStage.HELD
    assert context.authorization_ref is None
    assert context.execution_ref is None
    assert context.effect_ref is None
    assert context.dimensions["authority"] == "not_authorized"
    assert context.dimensions["evidence"] == "incomplete"


def test_rejects_route_from_another_task() -> None:
    with pytest.raises(OrientationConsistencyError, match="route belongs to task/trail"):
        project_orientation_context(
            _plan(),
            routes=(_route(task_id="task-other"),),
        )


def test_rejects_authorization_over_non_allow_decision() -> None:
    with pytest.raises(
        OrientationConsistencyError,
        match="without an ALLOW decision",
    ):
        project_orientation_context(
            _plan(),
            trail=_trail(),
            evidence_decision=_decision(DecisionCode.HOLD),
            authorization=_authorization(),
        )


def test_rejects_duplicate_forbidden_deltas() -> None:
    with pytest.raises(ValueError, match="forbidden_deltas must be unique"):
        project_orientation_context(
            _plan(),
            forbidden_deltas=("merge_pull_request", "merge_pull_request"),
        )
