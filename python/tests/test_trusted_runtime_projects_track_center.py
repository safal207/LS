from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import (
    ContinuityDecision,
    ContinuityReason,
    KnowledgeClass,
)
from trusted_runtime.projects_track_center import (
    PROJECTS_TRACK,
    ProjectEvent,
    ProjectEventType,
    ProjectStatus,
    build_project_observation,
    process_project_event,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/project_track_result.schema.json"


def _event(
    *,
    event_type: ProjectEventType,
    project_status: ProjectStatus,
    previous_status: Optional[ProjectStatus] = None,
    knowledge_class: KnowledgeClass = KnowledgeClass.FACT,
    evidence_refs: tuple[str, ...] = ("evidence:project:1",),
    with_identity_candidate: bool = False,
) -> ProjectEvent:
    return ProjectEvent(
        event_id="project-event:1",
        project_id="project:ls",
        event_type=event_type,
        project_status=project_status,
        previous_status=previous_status,
        knowledge_class=knowledge_class,
        statement="A bounded project lifecycle observation.",
        occurred_at="2026-06-25T06:00:00Z",
        confidence=0.9,
        evidence_refs=evidence_refs,
        identity_candidate_statement=(
            "Preserve evidence-first delivery discipline."
            if with_identity_candidate
            else None
        ),
        identity_scope="projects" if with_identity_candidate else None,
        identity_repeat_key=(
            "project:ls:evidence-first-delivery"
            if with_identity_candidate
            else None
        ),
    )


def _process(event: ProjectEvent):
    return process_project_event(
        event,
        processed_at="2026-06-25T06:01:00Z",
    )


def test_completed_project_lesson_emits_only_bounded_candidate() -> None:
    result = _process(
        _event(
            event_type=ProjectEventType.PROJECT_LESSON_RETAINED,
            project_status=ProjectStatus.COMPLETED,
            knowledge_class=KnowledgeClass.MEMORY,
            with_identity_candidate=True,
        )
    )

    assert result.observation.track == PROJECTS_TRACK
    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is not None
    assert ContinuityReason.BOUNDED_LESSON_ONLY in result.assessment.reason_codes
    assert (
        ContinuityReason.HISTORICAL_INFLUENCE_PRESERVED
        in result.assessment.reason_codes
    )
    assert result.to_dict()["project_registry_mutation_allowed"] is False
    assert result.to_dict()["task_scheduling_allowed"] is False
    assert result.to_dict()["stable_identity_update_allowed"] is False
    assert result.to_dict()["execution_authorized"] is False


def test_current_task_for_completed_project_is_blocked() -> None:
    result = _process(
        _event(
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.COMPLETED,
            knowledge_class=KnowledgeClass.INFERENCE,
        )
    )

    assert result.assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert ContinuityReason.FALSE_CURRENT_INTENTION in result.assessment.reason_codes
    assert result.assessment.lesson_candidate is None


def test_current_priority_for_cancelled_project_is_blocked() -> None:
    result = _process(
        _event(
            event_type=ProjectEventType.CURRENT_PRIORITY_CLAIM,
            project_status=ProjectStatus.CANCELLED,
            knowledge_class=KnowledgeClass.MEMORY,
        )
    )

    assert result.assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert ContinuityReason.FALSE_CURRENT_INTENTION in result.assessment.reason_codes


def test_current_task_for_paused_project_is_held() -> None:
    result = _process(
        _event(
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.PAUSED,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert (
        ContinuityReason.ENTITY_TEMPORARILY_INACTIVE
        in result.assessment.reason_codes
    )
    assert result.assessment.lesson_candidate is None


def test_active_source_backed_task_claim_is_bounded_not_executable() -> None:
    result = _process(
        _event(
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert ContinuityReason.VERIFIED_CURRENT_CLAIM in result.assessment.reason_codes
    assert result.assessment.lesson_candidate is None
    assert result.to_dict()["task_scheduling_allowed"] is False
    assert result.to_dict()["execution_authorized"] is False


def test_active_unverified_task_claim_is_held() -> None:
    result = _process(
        _event(
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.ACTIVE,
            knowledge_class=KnowledgeClass.INFERENCE,
            evidence_refs=(),
        )
    )

    assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert ContinuityReason.UNVERIFIED_CURRENT_CLAIM in result.assessment.reason_codes


def test_valid_pause_and_resume_transitions() -> None:
    paused = _event(
        event_type=ProjectEventType.PROJECT_PAUSED,
        project_status=ProjectStatus.PAUSED,
        previous_status=ProjectStatus.ACTIVE,
    )
    resumed = _event(
        event_type=ProjectEventType.PROJECT_RESUMED,
        project_status=ProjectStatus.ACTIVE,
        previous_status=ProjectStatus.PAUSED,
    )

    assert (
        _process(paused).assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert (
        _process(resumed).assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )


def test_invalid_lifecycle_transition_fails_closed() -> None:
    with pytest.raises(ValueError, match="invalid project lifecycle transition"):
        _event(
            event_type=ProjectEventType.PROJECT_RESUMED,
            project_status=ProjectStatus.ACTIVE,
            previous_status=ProjectStatus.COMPLETED,
        )


def test_lifecycle_event_requires_fact_and_evidence() -> None:
    with pytest.raises(ValueError, match="require FACT"):
        _event(
            event_type=ProjectEventType.PROJECT_COMPLETED,
            project_status=ProjectStatus.COMPLETED,
            previous_status=ProjectStatus.ACTIVE,
            knowledge_class=KnowledgeClass.MEMORY,
        )

    with pytest.raises(ValueError, match="require evidence"):
        _event(
            event_type=ProjectEventType.PROJECT_CANCELLED,
            project_status=ProjectStatus.CANCELLED,
            previous_status=ProjectStatus.PAUSED,
            evidence_refs=(),
        )


def test_current_task_cannot_propose_identity_lesson() -> None:
    with pytest.raises(ValueError, match="cannot propose"):
        _event(
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.ACTIVE,
            with_identity_candidate=True,
        )


def test_project_observation_contains_no_state_or_execution_authority() -> None:
    observation = build_project_observation(
        _event(
            event_type=ProjectEventType.PROJECT_LESSON_RETAINED,
            project_status=ProjectStatus.ARCHIVED,
            knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
        )
    )

    assert observation.metadata["project_registry_mutation_allowed"] is False
    assert observation.metadata["task_scheduling_allowed"] is False


def test_project_result_is_deterministic_and_matches_schema() -> None:
    event = _event(
        event_type=ProjectEventType.PROJECT_LESSON_RETAINED,
        project_status=ProjectStatus.COMPLETED,
        knowledge_class=KnowledgeClass.MEMORY,
        with_identity_candidate=True,
    )
    first = _process(event)
    second = _process(event)

    assert first.result_id == second.result_id
    assert first.event.event_digest == second.event.event_digest
    assert first.observation.observation_id == second.observation.observation_id
    assert first.assessment.assessment_id == second.assessment.assessment_id

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(first.to_dict()))
    assert errors == []
