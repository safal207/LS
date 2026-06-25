from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import (
    ContinuityDecision,
    ContinuityReason,
    KnowledgeClass,
)
from trusted_runtime.values_track_center import (
    VALUES_TRACK,
    ValueEvent,
    ValueEventType,
    ValueStatus,
    build_value_observation,
    process_value_event,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/value_track_result.schema.json"


def _event(
    *,
    event_type: ValueEventType,
    value_status: ValueStatus,
    knowledge_class: KnowledgeClass,
    repeat_count: int = 1,
    evidence_refs: tuple[str, ...] = ("evidence:value:1",),
    context_refs: tuple[str, ...] = ("context:work",),
    with_identity_candidate: bool = False,
) -> ValueEvent:
    return ValueEvent(
        event_id="value-event:1",
        value_key="value:evidence-first",
        event_type=event_type,
        value_status=value_status,
        knowledge_class=knowledge_class,
        statement="Evidence should precede confident conclusions.",
        occurred_at="2026-06-25T07:00:00Z",
        confidence=0.91,
        repeat_count=repeat_count,
        evidence_refs=evidence_refs,
        context_refs=context_refs,
        identity_candidate_statement=(
            "Prefer evidence before confident conclusions."
            if with_identity_candidate
            else None
        ),
        identity_scope="values" if with_identity_candidate else None,
        identity_repeat_key=(
            "value:evidence-first:cross-context"
            if with_identity_candidate
            else None
        ),
    )


def _process(event: ValueEvent):
    return process_value_event(
        event,
        processed_at="2026-06-25T07:01:00Z",
    )


def test_single_value_signal_emits_no_lesson_candidate() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.VALUE_SIGNAL_OBSERVED,
            value_status=ValueStatus.CANDIDATE,
            knowledge_class=KnowledgeClass.INFERENCE,
        )
    )

    assert result.observation.track == VALUES_TRACK
    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is None
    assert ContinuityReason.NO_IDENTITY_CANDIDATE in result.assessment.reason_codes


def test_mood_signal_emits_no_lesson_candidate() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.MOOD_SIGNAL_OBSERVED,
            value_status=ValueStatus.CANDIDATE,
            knowledge_class=KnowledgeClass.INFERENCE,
        )
    )

    assert result.assessment.lesson_candidate is None
    assert result.to_dict()["stable_identity_update_allowed"] is False


def test_transient_preference_emits_no_lesson_candidate() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.TRANSIENT_PREFERENCE_OBSERVED,
            value_status=ValueStatus.CANDIDATE,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert result.assessment.lesson_candidate is None
    assert result.to_dict()["priority_mutation_allowed"] is False


def test_repeated_cross_context_active_value_emits_bounded_candidate() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.VALUE_PRACTICED,
            value_status=ValueStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            repeat_count=3,
            evidence_refs=("evidence:value:work", "evidence:value:family"),
            context_refs=("context:work", "context:family"),
            with_identity_candidate=True,
        )
    )

    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is not None
    assert ContinuityReason.BOUNDED_LESSON_ONLY in result.assessment.reason_codes
    assert ContinuityReason.VERIFIED_CURRENT_CLAIM in result.assessment.reason_codes
    assert result.to_dict()["value_registry_mutation_allowed"] is False
    assert result.to_dict()["priority_mutation_allowed"] is False
    assert result.to_dict()["stable_identity_update_allowed"] is False
    assert result.to_dict()["execution_authorized"] is False


def test_contested_current_value_claim_is_held() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.CURRENT_VALUE_CLAIM,
            value_status=ValueStatus.CONTESTED,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert (
        ContinuityReason.ENTITY_TEMPORARILY_INACTIVE
        in result.assessment.reason_codes
    )
    assert result.assessment.lesson_candidate is None


def test_candidate_current_value_claim_is_held() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.CURRENT_VALUE_CLAIM,
            value_status=ValueStatus.CANDIDATE,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert ContinuityReason.ENTITY_STATUS_UNKNOWN in result.assessment.reason_codes
    assert result.assessment.lesson_candidate is None


def test_retired_current_value_claim_is_blocked() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.CURRENT_VALUE_CLAIM,
            value_status=ValueStatus.RETIRED,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert result.assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert ContinuityReason.FALSE_CURRENT_INTENTION in result.assessment.reason_codes
    assert result.assessment.preserved_influence is not None


def test_retired_value_history_is_preserved_without_current_guidance() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.VALUE_RETIRED,
            value_status=ValueStatus.RETIRED,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is None
    assert (
        ContinuityReason.HISTORICAL_INFLUENCE_PRESERVED
        in result.assessment.reason_codes
    )


def test_active_current_value_claim_is_bounded_not_authoritative() -> None:
    result = _process(
        _event(
            event_type=ValueEventType.CURRENT_VALUE_CLAIM,
            value_status=ValueStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is None
    assert result.to_dict()["value_registry_mutation_allowed"] is False
    assert result.to_dict()["execution_authorized"] is False


def test_identity_candidate_requires_repeated_evidence() -> None:
    with pytest.raises(ValueError, match="requires repeated evidence"):
        _event(
            event_type=ValueEventType.VALUE_REAFFIRMED,
            value_status=ValueStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            repeat_count=1,
            evidence_refs=("evidence:value:1", "evidence:value:2"),
            context_refs=("context:work", "context:family"),
            with_identity_candidate=True,
        )


def test_identity_candidate_requires_cross_context_evidence() -> None:
    with pytest.raises(ValueError, match="cross-context"):
        _event(
            event_type=ValueEventType.VALUE_REAFFIRMED,
            value_status=ValueStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            repeat_count=2,
            evidence_refs=("evidence:value:1", "evidence:value:2"),
            context_refs=("context:work",),
            with_identity_candidate=True,
        )


def test_preference_cannot_propose_identity_lesson() -> None:
    with pytest.raises(ValueError, match="cannot propose"):
        _event(
            event_type=ValueEventType.TRANSIENT_PREFERENCE_OBSERVED,
            value_status=ValueStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            repeat_count=2,
            evidence_refs=("evidence:value:1", "evidence:value:2"),
            context_refs=("context:work", "context:family"),
            with_identity_candidate=True,
        )


def test_value_conflict_requires_contested_status() -> None:
    with pytest.raises(ValueError, match="requires CONTESTED"):
        _event(
            event_type=ValueEventType.VALUE_CONFLICT_RECORDED,
            value_status=ValueStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
        )


def test_value_observation_contains_no_registry_or_priority_authority() -> None:
    observation = build_value_observation(
        _event(
            event_type=ValueEventType.VALUE_SIGNAL_OBSERVED,
            value_status=ValueStatus.CANDIDATE,
            knowledge_class=KnowledgeClass.INFERENCE,
        )
    )

    assert observation.metadata["value_registry_mutation_allowed"] is False
    assert observation.metadata["priority_mutation_allowed"] is False


def test_value_result_is_deterministic_and_matches_schema() -> None:
    event = _event(
        event_type=ValueEventType.VALUE_REAFFIRMED,
        value_status=ValueStatus.ACTIVE,
        knowledge_class=KnowledgeClass.FACT,
        repeat_count=3,
        evidence_refs=("evidence:value:work", "evidence:value:family"),
        context_refs=("context:work", "context:family"),
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
