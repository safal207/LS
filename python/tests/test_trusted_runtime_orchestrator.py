from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime import (
    DeterministicWorkflowOrchestrator,
    OrchestrationDepthError,
    OrchestratorConfig,
    TrailEventType,
)
from modules.trusted_runtime.protocols import WorkflowOrchestrator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas" / "trusted_runtime" / "workflow_plan.schema.json"
FIXTURE_ROOT = (
    ROOT
    / "python"
    / "tests"
    / "fixtures"
    / "trusted-runtime"
    / "orchestrator"
)


def _load(name: str) -> dict:
    return json.loads((FIXTURE_ROOT / name).read_text(encoding="utf-8"))


def _schema_errors(payload: dict) -> list:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return sorted(validator.iter_errors(payload), key=lambda error: list(error.path))


def _causal_root(plan, step_id: str) -> str:
    steps = {step.step_id: step for step in plan.steps}
    current = steps[step_id]
    while current.parent_cause in steps:
        current = steps[current.parent_cause]
    return current.parent_cause


def test_simple_fixture_is_deterministic_and_schema_valid() -> None:
    fixture = _load("simple_workflow.json")
    first = DeterministicWorkflowOrchestrator()
    second = DeterministicWorkflowOrchestrator()

    first_plan = first.create_plan(fixture["task"], fixture["context"])
    second_plan = second.create_plan(fixture["task"], fixture["context"])

    assert isinstance(first, WorkflowOrchestrator)
    assert first_plan.to_dict() == second_plan.to_dict()
    assert [role.role_id for role in first_plan.roles] == fixture["expected"]["role_ids"]
    assert [role.actor for role in first_plan.roles] == fixture["expected"]["actors"]
    assert [step.step_id for step in first_plan.steps] == fixture["expected"]["step_ids"]
    assert first_plan.task.metadata["orchestration_depth"] == fixture["expected"]["depth"]
    assert _schema_errors(first_plan.to_dict()) == []


def test_multi_role_fixture_assigns_capabilities_and_preserves_causal_root() -> None:
    fixture = _load("multi_role_workflow.json")
    orchestrator = DeterministicWorkflowOrchestrator()
    plan = orchestrator.create_plan(fixture["task"], fixture["context"])

    assert [role.role_id for role in plan.roles] == fixture["expected"]["role_ids"]
    assert [role.actor for role in plan.roles] == fixture["expected"]["actors"]
    assert [step.step_id for step in plan.steps] == fixture["expected"]["step_ids"]

    for role in plan.roles:
        assert role.parent_cause == plan.task.task_id
    for step in plan.steps:
        assert _causal_root(plan, step.step_id) == plan.task.task_id

    reassigned = orchestrator.assign_roles(
        plan,
        {
            "researcher": "agent:research-replacement",
            "summarization": "agent:summary-replacement",
        },
    )
    assert reassigned.roles[0].actor == "agent:research-replacement"
    assert reassigned.roles[-1].actor == "agent:summary-replacement"
    assert reassigned.steps == plan.steps
    assert _schema_errors(reassigned.to_dict()) == []


def test_explicit_subtasks_are_bounded() -> None:
    fixture = _load("simple_workflow.json")
    context = {
        "roles": ["researcher", "summarizer"],
        "subtasks": [
            {"role": "researcher", "action": "Collect evidence."},
            {"role": "summarizer", "action": "Summarize the evidence."},
        ],
    }

    orchestrator = DeterministicWorkflowOrchestrator(
        OrchestratorConfig(max_steps=1)
    )
    with pytest.raises(ValueError, match="configured limit is 1"):
        orchestrator.create_plan(fixture["task"], context)


def test_recursive_fixture_records_revisions_and_enforces_depth_limit() -> None:
    fixture = _load("recursive_workflow.json")
    config = OrchestratorConfig(**fixture["config"])
    orchestrator = DeterministicWorkflowOrchestrator(config)
    plan = orchestrator.create_plan(fixture["task"], fixture["context"])

    for revision in fixture["revisions"]:
        plan = orchestrator.revise_plan(
            plan,
            revision["results"],
            revision["reason"],
        )

    expected = fixture["expected"]
    assert plan.task.metadata["orchestration_depth"] == expected["final_depth"]
    assert [step.step_id for step in plan.steps[-2:]] == expected["revision_step_ids"]
    assert _schema_errors(plan.to_dict()) == []

    trail = orchestrator.revision_trail(plan)
    assert [event.event_id for event in trail.events] == expected["trail_event_ids"]
    assert [event.event_type for event in trail.events[-2:]] == [
        TrailEventType.PLAN_REVISED,
        TrailEventType.PLAN_REVISED,
    ]
    assert trail.events[-1].parent_cause == trail.events[-2].event_id
    assert trail.events[-1].evidence_refs == (
        "result:verifier-001",
        "evidence:verification-001",
    )

    with pytest.raises(OrchestrationDepthError, match="configured limit 2"):
        orchestrator.revise_plan(
            plan,
            (),
            "A third revision must be rejected.",
        )


def test_revision_requires_an_explicit_reason() -> None:
    fixture = _load("simple_workflow.json")
    orchestrator = DeterministicWorkflowOrchestrator()
    plan = orchestrator.create_plan(fixture["task"], fixture["context"])

    with pytest.raises(ValueError, match="reason must not be empty"):
        orchestrator.revise_plan(plan, (), "   ")
