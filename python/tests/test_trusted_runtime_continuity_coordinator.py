from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import (
    ContinuityDecision,
    ContinuityReason,
    EntityStatus,
    KnowledgeClass,
    TrackObservation,
    assess_track_observation,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/continuity_assessment.schema.json"


def _observation(
    *,
    status: EntityStatus,
    knowledge_class: KnowledgeClass,
    statement: str = "The relationship still shapes the agent's priorities.",
    current_presence: bool = False,
    current_intention: bool = False,
    identity_candidate: bool = True,
    evidence_refs: tuple[str, ...] = ("evidence:1",),
) -> TrackObservation:
    return TrackObservation(
        observation_id="observation:loss:1",
        track="relationships",
        subject_id="human:mentor",
        entity_status=status,
        knowledge_class=knowledge_class,
        statement=statement,
        occurred_at="2026-06-25T00:00:00Z",
        confidence=0.82,
        evidence_refs=evidence_refs,
        claims_current_presence=current_presence,
        claims_current_intention=current_intention,
        identity_candidate_statement=(
            "Preserve the mentor's evidence-first discipline."
            if identity_candidate
            else None
        ),
        identity_scope="relationships" if identity_candidate else None,
        identity_repeat_key=(
            "mentor:evidence-first-discipline" if identity_candidate else None
        ),
    )


def _assess(observation: TrackObservation):
    return assess_track_observation(
        observation,
        assessed_at="2026-06-25T00:01:00Z",
    )


def test_deceased_entity_current_presence_is_blocked() -> None:
    assessment = _assess(
        _observation(
            status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
            current_presence=True,
            current_intention=True,
        )
    )

    assert assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert ContinuityReason.FALSE_CURRENT_PRESENCE in assessment.reason_codes
    assert ContinuityReason.FALSE_CURRENT_INTENTION in assessment.reason_codes
    assert (
        ContinuityReason.HISTORICAL_INFLUENCE_PRESERVED
        in assessment.reason_codes
    )
    assert assessment.lesson_candidate is None
    assert assessment.preserved_influence is not None
    assert assessment.to_dict()["stable_identity_update_allowed"] is False
    assert assessment.to_dict()["execution_authorized"] is False


def test_deceased_entity_symbolic_influence_remains_bounded() -> None:
    assessment = _assess(
        _observation(
            status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
        )
    )

    assert (
        assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert assessment.lesson_candidate is not None
    assert (
        assessment.lesson_candidate.statement
        == "Preserve the mentor's evidence-first discipline."
    )
    assert ContinuityReason.BOUNDED_LESSON_ONLY in assessment.reason_codes
    assert (
        ContinuityReason.HISTORICAL_INFLUENCE_PRESERVED
        in assessment.reason_codes
    )


def test_unknown_entity_current_intention_is_held() -> None:
    assessment = _assess(
        _observation(
            status=EntityStatus.UNKNOWN,
            knowledge_class=KnowledgeClass.INFERENCE,
            current_intention=True,
        )
    )

    assert assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert ContinuityReason.ENTITY_STATUS_UNKNOWN in assessment.reason_codes
    assert ContinuityReason.UNVERIFIED_CURRENT_CLAIM in assessment.reason_codes
    assert assessment.lesson_candidate is None


def test_active_verified_current_claim_can_emit_only_bounded_lesson() -> None:
    assessment = _assess(
        _observation(
            status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            current_intention=True,
        )
    )

    assert (
        assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert ContinuityReason.VERIFIED_CURRENT_CLAIM in assessment.reason_codes
    assert ContinuityReason.BOUNDED_LESSON_ONLY in assessment.reason_codes
    assert assessment.lesson_candidate is not None
    assert assessment.to_dict()["stable_identity_update_allowed"] is False


def test_active_unverified_current_claim_is_held() -> None:
    assessment = _assess(
        _observation(
            status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.MEMORY,
            current_presence=True,
        )
    )

    assert assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert ContinuityReason.UNVERIFIED_CURRENT_CLAIM in assessment.reason_codes
    assert assessment.lesson_candidate is None


def test_assessment_is_deterministic_and_matches_schema() -> None:
    observation = _observation(
        status=EntityStatus.DECEASED,
        knowledge_class=KnowledgeClass.MEMORY,
    )
    first = _assess(observation)
    second = _assess(observation)

    assert first.assessment_id == second.assessment_id
    assert first.observation_digest == second.observation_digest

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(first.to_dict()))
    assert errors == []


def test_partial_identity_candidate_contract_fails_closed() -> None:
    with pytest.raises(ValueError, match="must be set together"):
        TrackObservation(
            observation_id="observation:bad:1",
            track="relationships",
            subject_id="human:mentor",
            entity_status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            statement="A bounded fact.",
            occurred_at="2026-06-25T00:00:00Z",
            confidence=0.8,
            evidence_refs=("evidence:1",),
            identity_candidate_statement="Candidate without scope.",
        )


def test_duplicate_evidence_refs_fail_closed() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        _observation(
            status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            evidence_refs=("evidence:1", "evidence:1"),
        )
