from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.contracts import (
    DecisionCode,
    ExecutionAuthorization,
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

    # JSON Schema validates shape; Python contracts validate cross-record links.
    assert _errors(validator, payload) == []

    with pytest.raises(ValueError, match="unknown role"):
        WorkflowPlan.from_mapping(payload)


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
