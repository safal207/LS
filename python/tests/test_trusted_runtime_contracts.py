from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.contracts import (
    CognitiveTrail,
    DecisionCode,
    ExecutionAuthorization,
    ReplayDecision,
    ReplayRecord,
    RouteDecision,
    WorkflowPlan,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_ROOT = ROOT / "schemas" / "trusted_runtime"
FIXTURE_ROOT = ROOT / "python" / "tests" / "fixtures" / "trusted-runtime"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_name: str) -> Draft202012Validator:
    schema = _load(SCHEMA_ROOT / schema_name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _errors(validator: Draft202012Validator, payload: dict) -> list:
    return sorted(validator.iter_errors(payload), key=lambda error: list(error.path))


def test_all_trusted_runtime_schemas_are_valid_draft_2020_12() -> None:
    schema_names = {
        "workflow_plan.schema.json",
        "route_decision.schema.json",
        "cognitive_trail.schema.json",
        "causal_audit_report.schema.json",
        "evidence_decision.schema.json",
        "execution_authorization.schema.json",
        "authorization_bundle.schema.json",
        "replay_record.schema.json",
        "reusable_artifact.schema.json",
    }

    assert {path.name for path in SCHEMA_ROOT.glob("*.schema.json")} == schema_names

    for schema_name in sorted(schema_names):
        Draft202012Validator.check_schema(_load(SCHEMA_ROOT / schema_name))


def test_valid_workflow_matches_schema_and_semantic_contract() -> None:
    payload = _load(FIXTURE_ROOT / "valid_workflow_plan.json")
    validator = _validator("workflow_plan.schema.json")

    assert _errors(validator, payload) == []

    plan = WorkflowPlan.from_mapping(payload)
    assert plan.task.task_id == "task-pr-001"
    assert [step.step_id for step in plan.steps] == ["draft-review", "verify-review"]
    assert plan.to_dict() == payload


def test_schema_rejects_workflow_step_without_parent_cause() -> None:
    payload = _load(FIXTURE_ROOT / "invalid_missing_parent_cause.json")
    validator = _validator("workflow_plan.schema.json")
    errors = _errors(validator, payload)

    assert any(
        list(error.path) == ["steps", 0]
        and error.message == "'parent_cause' is a required property"
        for error in errors
    )


def test_semantic_contract_rejects_unknown_role_reference() -> None:
    payload = _load(FIXTURE_ROOT / "invalid_unknown_role.json")
    validator = _validator("workflow_plan.schema.json")

    assert _errors(validator, payload) == []

    with pytest.raises(ValueError, match="unknown role"):
        WorkflowPlan.from_mapping(payload)


def test_valid_route_decision_matches_schema_and_contract() -> None:
    payload = _load(FIXTURE_ROOT / "valid_route_decision.json")
    validator = _validator("route_decision.schema.json")

    assert _errors(validator, payload) == []

    route = RouteDecision.from_mapping(payload)
    assert route.selected_backend == "backend:local-reviewer"
    assert route.to_dict() == payload


def test_route_contract_rejects_backend_not_in_considered_set() -> None:
    payload = _load(FIXTURE_ROOT / "invalid_route_selected_not_considered.json")
    validator = _validator("route_decision.schema.json")

    assert _errors(validator, payload) == []

    with pytest.raises(ValueError, match="selected backend must appear"):
        RouteDecision.from_mapping(payload)


def test_valid_cognitive_trail_matches_schema_and_contract() -> None:
    payload = _load(FIXTURE_ROOT / "valid_cognitive_trail.json")
    validator = _validator("cognitive_trail.schema.json")

    assert _errors(validator, payload) == []

    trail = CognitiveTrail.from_mapping(payload)
    assert [event.event_id for event in trail.events] == [
        "event-task-received",
        "event-plan-created",
        "event-route-selected",
        "event-work-completed",
    ]
    assert trail.to_dict() == payload


def test_cognitive_trail_rejects_parent_from_the_future() -> None:
    payload = _load(FIXTURE_ROOT / "invalid_cognitive_trail_forward_parent.json")
    validator = _validator("cognitive_trail.schema.json")

    assert _errors(validator, payload) == []

    with pytest.raises(ValueError, match="unavailable parent cause"):
        CognitiveTrail.from_mapping(payload)


def test_authorization_schema_rejects_allow_without_evidence() -> None:
    payload = _load(FIXTURE_ROOT / "invalid_authorization_without_evidence.json")
    validator = _validator("execution_authorization.schema.json")
    errors = _errors(validator, payload)

    assert any(
        list(error.path) == ["evidence_refs"]
        and "should be non-empty" in error.message
        for error in errors
    )


def test_python_authorization_contract_rejects_non_allow_decision() -> None:
    with pytest.raises(ValueError, match="requires an ALLOW decision"):
        ExecutionAuthorization(
            authorization_id="auth-pr-001",
            task_id="task-pr-001",
            trail_id="trail-pr-001",
            decision=DecisionCode.HOLD,
            actor="gate:mock",
            scope=("artifact:write",),
            issued_at="2026-06-22T17:00:00Z",
            expires_at="2026-06-22T18:00:00Z",
            nonce="nonce-pr-001",
            evidence_refs=("evidence:review-001",),
            policy_version="policy.v0.1",
            parent_cause="decision-pr-001",
        )


def test_valid_replay_record_matches_schema_and_contract() -> None:
    payload = _load(FIXTURE_ROOT / "valid_replay_record.json")
    validator = _validator("replay_record.schema.json")

    assert _errors(validator, payload) == []

    replay = ReplayRecord.from_mapping(payload)
    assert replay.decision is ReplayDecision.ADMISSIBLE
    assert replay.to_dict() == payload


def test_replay_schema_rejects_record_without_source_events() -> None:
    payload = _load(FIXTURE_ROOT / "invalid_replay_without_source.json")
    validator = _validator("replay_record.schema.json")
    errors = _errors(validator, payload)

    assert any(
        list(error.path) == ["source_event_refs"]
        and "should be non-empty" in error.message
        for error in errors
    )


def test_replay_contract_requires_drift_references_for_drifted_path() -> None:
    with pytest.raises(ValueError, match="DRIFTED replay requires drift references"):
        ReplayRecord(
            replay_id="replay-pr-003",
            task_id="task-pr-001",
            trail_id="trail-pr-001",
            actor="replay:local",
            created_at="2026-06-22T17:03:00Z",
            source_event_refs=("event-task-received",),
            decision=ReplayDecision.DRIFTED,
            reason="A route changed during replay.",
            drift_refs=(),
            parent_cause="event-task-received",
        )
