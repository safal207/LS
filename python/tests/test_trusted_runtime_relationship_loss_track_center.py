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
)
from trusted_runtime.relationship_loss_track_center import (
    RELATIONSHIP_LOSS_TRACK,
    RelationshipEventType,
    RelationshipLossEvent,
    build_relationship_observation,
    process_relationship_event,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/relationship_loss_result.schema.json"


def _event(
    *,
    event_type: RelationshipEventType,
    entity_status: EntityStatus,
    knowledge_class: KnowledgeClass,
    statement: str = "The relationship still influences review discipline.",
    evidence_refs: tuple[str, ...] = ("evidence:relationship:1",),
    with_identity_candidate: bool = False,
) -> RelationshipLossEvent:
    return RelationshipLossEvent(
        event_id="relationship-event:1",
        relationship_id="relationship:mentor",
        subject_id="human:mentor",
        event_type=event_type,
        entity_status=entity_status,
        knowledge_class=knowledge_class,
        statement=statement,
        occurred_at="2026-06-25T01:00:00Z",
        confidence=0.84,
        evidence_refs=evidence_refs,
        identity_candidate_statement=(
            "Preserve evidence-first review discipline."
            if with_identity_candidate
            else None
        ),
        identity_scope="relationships" if with_identity_candidate else None,
        identity_repeat_key=(
            "mentor:evidence-first-review" if with_identity_candidate else None
        ),
    )


def _process(event: RelationshipLossEvent):
    return process_relationship_event(
        event,
        processed_at="2026-06-25T01:01:00Z",
    )


def test_confirmed_loss_is_preserved_without_identity_mutation() -> None:
    result = _process(
        _event(
            event_type=RelationshipEventType.LOSS_CONFIRMED,
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.FACT,
        )
    )

    assert result.observation.track == RELATIONSHIP_LOSS_TRACK
    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is None
    assert result.assessment.preserved_influence is not None
    assert (
        ContinuityReason.HISTORICAL_INFLUENCE_PRESERVED
        in result.assessment.reason_codes
    )
    assert result.to_dict()["relational_self_mutation_allowed"] is False
    assert result.to_dict()["stable_identity_update_allowed"] is False
    assert result.to_dict()["execution_authorized"] is False


def test_remembered_influence_can_emit_only_bounded_lesson() -> None:
    result = _process(
        _event(
            event_type=RelationshipEventType.REMEMBERED_INFLUENCE,
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.MEMORY,
            with_identity_candidate=True,
        )
    )

    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is not None
    assert (
        result.assessment.lesson_candidate.statement
        == "Preserve evidence-first review discipline."
    )
    assert ContinuityReason.BOUNDED_LESSON_ONLY in result.assessment.reason_codes
    assert result.assessment.to_dict()["stable_identity_update_allowed"] is False


def test_current_presence_claim_for_deceased_entity_is_blocked() -> None:
    result = _process(
        _event(
            event_type=RelationshipEventType.CURRENT_PRESENCE_CLAIM,
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
        )
    )

    assert result.assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert ContinuityReason.FALSE_CURRENT_PRESENCE in result.assessment.reason_codes
    assert result.assessment.lesson_candidate is None
    assert result.assessment.preserved_influence is not None


def test_current_intention_claim_for_closed_relationship_is_blocked() -> None:
    result = _process(
        _event(
            event_type=RelationshipEventType.CURRENT_INTENTION_CLAIM,
            entity_status=EntityStatus.CLOSED,
            knowledge_class=KnowledgeClass.INFERENCE,
        )
    )

    assert result.assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert ContinuityReason.FALSE_CURRENT_INTENTION in result.assessment.reason_codes
    assert result.assessment.lesson_candidate is None


def test_unknown_current_intention_claim_is_held() -> None:
    result = _process(
        _event(
            event_type=RelationshipEventType.CURRENT_INTENTION_CLAIM,
            entity_status=EntityStatus.UNKNOWN,
            knowledge_class=KnowledgeClass.INFERENCE,
            evidence_refs=(),
        )
    )

    assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert ContinuityReason.ENTITY_STATUS_UNKNOWN in result.assessment.reason_codes
    assert ContinuityReason.UNVERIFIED_CURRENT_CLAIM in result.assessment.reason_codes
    assert result.assessment.lesson_candidate is None


def test_active_source_backed_interaction_can_emit_bounded_lesson() -> None:
    result = _process(
        _event(
            event_type=RelationshipEventType.INTERACTION_RECORDED,
            entity_status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            with_identity_candidate=True,
        )
    )

    assert (
        result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.assessment.lesson_candidate is not None
    assert result.assessment.preserved_influence is None


def test_loss_confirmed_requires_deceased_status() -> None:
    with pytest.raises(ValueError, match="requires DECEASED"):
        _event(
            event_type=RelationshipEventType.LOSS_CONFIRMED,
            entity_status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
        )


def test_lifecycle_event_requires_fact_and_evidence() -> None:
    with pytest.raises(ValueError, match="require FACT"):
        _event(
            event_type=RelationshipEventType.INTERACTION_RECORDED,
            entity_status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.MEMORY,
        )

    with pytest.raises(ValueError, match="require evidence"):
        _event(
            event_type=RelationshipEventType.RELATIONSHIP_CLOSED,
            entity_status=EntityStatus.CLOSED,
            knowledge_class=KnowledgeClass.FACT,
            evidence_refs=(),
        )


def test_current_claim_cannot_propose_identity_lesson() -> None:
    with pytest.raises(ValueError, match="cannot propose"):
        _event(
            event_type=RelationshipEventType.CURRENT_PRESENCE_CLAIM,
            entity_status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            with_identity_candidate=True,
        )


def test_result_is_deterministic_and_matches_schema() -> None:
    event = _event(
        event_type=RelationshipEventType.REMEMBERED_INFLUENCE,
        entity_status=EntityStatus.DECEASED,
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


def test_observation_contains_no_direct_relational_self_authority() -> None:
    event = _event(
        event_type=RelationshipEventType.REMEMBERED_INFLUENCE,
        entity_status=EntityStatus.DECEASED,
        knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
    )
    observation = build_relationship_observation(event)

    assert observation.metadata["relational_self_mutation_allowed"] is False
    assert "identity" not in observation.metadata
