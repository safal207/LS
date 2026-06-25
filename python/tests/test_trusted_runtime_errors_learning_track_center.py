from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import ContinuityDecision, KnowledgeClass
from trusted_runtime.errors_learning_track_center import (
    ERRORS_TRACK,
    ErrorEventType,
    ErrorLearningEvent,
    ErrorStatus,
    OutcomeClass,
    process_error_event,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/error_learning_result.schema.json"


def _event(
    event_type: ErrorEventType,
    status: ErrorStatus,
    outcome: OutcomeClass,
    *,
    count: int = 1,
    candidate: bool = False,
    evidence: tuple[str, ...] = ("evidence:1",),
    contexts: tuple[str, ...] = ("context:1",),
    observers: tuple[str, ...] = ("observer:1",),
    knowledge: KnowledgeClass = KnowledgeClass.FACT,
) -> ErrorLearningEvent:
    return ErrorLearningEvent(
        event_id="error-event:1",
        error_id="error:checkout-timeout",
        event_type=event_type,
        error_status=status,
        outcome_class=outcome,
        knowledge_class=knowledge,
        statement="A bounded error-learning observation.",
        occurred_at="2026-06-25T08:00:00Z",
        confidence=0.91,
        occurrence_count=count,
        evidence_refs=evidence,
        context_refs=contexts,
        observer_refs=observers,
        identity_candidate_statement=(
            "Verify timeout assumptions before release." if candidate else None
        ),
        identity_scope=ERRORS_TRACK if candidate else None,
        identity_repeat_key="error:timeout:verification" if candidate else None,
    )


def _process(event: ErrorLearningEvent):
    return process_error_event(event, processed_at="2026-06-25T08:01:00Z")


def test_single_failure_and_near_miss_emit_no_lesson() -> None:
    cases = (
        _event(
            ErrorEventType.FAILURE_VERIFIED,
            ErrorStatus.CONFIRMED,
            OutcomeClass.FAILED,
        ),
        _event(
            ErrorEventType.NEAR_MISS_RECORDED,
            ErrorStatus.CONFIRMED,
            OutcomeClass.NEAR_MISS,
        ),
    )
    for event in cases:
        result = _process(event)
        assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
        assert result.assessment.lesson_candidate is None
        assert result.observation.metadata["failed_outcome_is_not_success"] is True


def test_recurrence_and_verified_remediation_emit_only_bounded_lessons() -> None:
    shared = {
        "count": 2,
        "candidate": True,
        "evidence": ("evidence:1", "evidence:2"),
        "contexts": ("context:api", "context:ui"),
        "observers": ("observer:qa", "observer:sre"),
    }
    events = (
        _event(
            ErrorEventType.ERROR_RECURRENCE_CONFIRMED,
            ErrorStatus.RECURRING,
            OutcomeClass.FAILED,
            **shared,
        ),
        _event(
            ErrorEventType.REMEDIATION_VERIFIED,
            ErrorStatus.RESOLVED,
            OutcomeClass.SUCCESSFUL_REMEDIATION,
            **shared,
        ),
    )
    for event in events:
        result = _process(event)
        assert result.assessment.lesson_candidate is not None
        assert result.to_dict()["blame_assignment_allowed"] is False
        assert result.to_dict()["stable_identity_update_allowed"] is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ErrorStatus.DISPUTED, ContinuityDecision.HOLD_FOR_REVIEW),
        (ErrorStatus.OBSERVED, ContinuityDecision.HOLD_FOR_REVIEW),
        (ErrorStatus.RESOLVED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
        (ErrorStatus.RETIRED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
    ],
)
def test_current_blame_claim_is_fail_closed(
    status: ErrorStatus,
    expected: ContinuityDecision,
) -> None:
    result = _process(
        _event(
            ErrorEventType.CURRENT_BLAME_CLAIM,
            status,
            OutcomeClass.UNEXPECTED,
        )
    )
    assert result.assessment.decision is expected
    assert result.to_dict()["blame_assignment_allowed"] is False


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"count": 1}, "repeated evidence"),
        ({"contexts": ("context:1",)}, "cross-context"),
        ({"observers": ("observer:1",)}, "observer independence"),
    ],
)
def test_learning_candidate_requires_independent_repetition(
    overrides: dict[str, object],
    match: str,
) -> None:
    kwargs = {
        "count": 2,
        "candidate": True,
        "evidence": ("evidence:1", "evidence:2"),
        "contexts": ("context:1", "context:2"),
        "observers": ("observer:1", "observer:2"),
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError, match=match):
        _event(
            ErrorEventType.ERROR_RECURRENCE_CONFIRMED,
            ErrorStatus.RECURRING,
            OutcomeClass.FAILED,
            **kwargs,
        )


def test_wrong_outcome_and_status_fail_closed() -> None:
    with pytest.raises(ValueError, match="requires FAILED"):
        _event(
            ErrorEventType.FAILURE_VERIFIED,
            ErrorStatus.CONFIRMED,
            OutcomeClass.UNEXPECTED,
        )
    with pytest.raises(ValueError, match="requires DISPUTED"):
        _event(
            ErrorEventType.ATTRIBUTION_DISPUTED,
            ErrorStatus.CONFIRMED,
            OutcomeClass.UNEXPECTED,
        )


def test_result_is_deterministic_schema_valid_and_non_authoritative() -> None:
    event = _event(
        ErrorEventType.ERROR_RECURRENCE_CONFIRMED,
        ErrorStatus.RECURRING,
        OutcomeClass.FAILED,
        count=2,
        candidate=True,
        evidence=("evidence:1", "evidence:2"),
        contexts=("context:1", "context:2"),
        observers=("observer:1", "observer:2"),
    )
    first = _process(event)
    second = _process(event)
    assert first.result_id == second.result_id
    payload = first.to_dict()
    for field in (
        "incident_registry_mutation_allowed",
        "blame_assignment_allowed",
        "remediation_scheduling_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    ):
        assert payload[field] is False
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
