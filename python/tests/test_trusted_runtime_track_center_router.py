from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import ContinuityDecision
from trusted_runtime.relationship_loss_track_center import (
    RELATIONSHIP_LOSS_TRACK,
    RelationshipEventType,
)
from trusted_runtime.track_center_router import (
    RouterDecision,
    RouterReason,
    TrackCenterEnvelope,
    route_track_center_envelope,
    supported_track_center_routes,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/track_center_route_result.schema.json"


def _payload(
    *,
    event_type: str = RelationshipEventType.REMEMBERED_INFLUENCE.value,
    entity_status: str = "DECEASED",
    knowledge_class: str = "MEMORY",
    with_identity_candidate: bool = True,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "trusted_runtime.relationship_loss_event.v0.1",
        "event_id": "relationship-event:router:1",
        "relationship_id": "relationship:mentor",
        "subject_id": "human:mentor",
        "event_type": event_type,
        "entity_status": entity_status,
        "knowledge_class": knowledge_class,
        "statement": "Remembered evidence-first discipline remains influential.",
        "occurred_at": "2026-06-25T05:00:00Z",
        "confidence": 0.86,
        "evidence_refs": ["memory:mentor:review"],
        "identity_candidate_statement": None,
        "identity_scope": None,
        "identity_repeat_key": None,
        "metadata": {"source": "router-test"},
    }
    if with_identity_candidate:
        payload.update(
            {
                "identity_candidate_statement": (
                    "Preserve evidence-first discipline in bounded reviews."
                ),
                "identity_scope": "relationships",
                "identity_repeat_key": "mentor:evidence-first-review",
            }
        )
    return payload


def _envelope(
    *,
    route_key: str = RELATIONSHIP_LOSS_TRACK,
    payload: dict[str, object] | None = None,
) -> TrackCenterEnvelope:
    return TrackCenterEnvelope(
        envelope_id="track-envelope:1",
        route_key=route_key,
        payload=payload if payload is not None else _payload(),
        submitted_at="2026-06-25T05:01:00Z",
        source_refs=("source:router-test",),
    )


def _route(envelope: TrackCenterEnvelope):
    return route_track_center_envelope(
        envelope,
        processed_at="2026-06-25T05:02:00Z",
    )


def test_supported_routes_are_explicit_and_bounded() -> None:
    assert supported_track_center_routes() == (RELATIONSHIP_LOSS_TRACK,)


def test_valid_relationship_payload_routes_to_loss_track_center() -> None:
    result = _route(_envelope())

    assert result.decision is RouterDecision.ROUTED
    assert result.selected_route == RELATIONSHIP_LOSS_TRACK
    assert result.routed_result is not None
    assert (
        result.routed_result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )
    assert result.routed_result.assessment.lesson_candidate is not None
    assert result.reason_codes == (RouterReason.EXACT_ROUTE_MATCH,)
    assert result.diagnostic_code is None


def test_inner_false_presence_block_is_preserved() -> None:
    payload = _payload(
        event_type=RelationshipEventType.CURRENT_PRESENCE_CLAIM.value,
        entity_status="DECEASED",
        knowledge_class="SYMBOLIC_MEANING",
        with_identity_candidate=False,
    )
    result = _route(_envelope(payload=payload))

    assert result.decision is RouterDecision.ROUTED
    assert result.routed_result is not None
    assert (
        result.routed_result.assessment.decision
        is ContinuityDecision.BLOCK_FALSE_PRESENCE
    )
    assert result.routed_result.assessment.lesson_candidate is None


def test_inner_unknown_current_claim_hold_is_preserved() -> None:
    payload = _payload(
        event_type=RelationshipEventType.CURRENT_INTENTION_CLAIM.value,
        entity_status="UNKNOWN",
        knowledge_class="INFERENCE",
        with_identity_candidate=False,
    )
    payload["evidence_refs"] = []
    result = _route(_envelope(payload=payload))

    assert result.decision is RouterDecision.ROUTED
    assert result.routed_result is not None
    assert (
        result.routed_result.assessment.decision
        is ContinuityDecision.HOLD_FOR_REVIEW
    )


def test_unknown_route_is_held_without_route_inference() -> None:
    result = _route(
        _envelope(
            route_key="please infer that this is about relationships and loss",
        )
    )

    assert result.decision is RouterDecision.HOLD_UNKNOWN_ROUTE
    assert result.selected_route is None
    assert result.routed_result is None
    assert RouterReason.UNKNOWN_ROUTE in result.reason_codes
    assert RouterReason.NO_ROUTE_INFERENCE in result.reason_codes
    assert result.diagnostic_code == "unknown_track_center_route"


def test_known_route_missing_required_payload_is_held() -> None:
    payload = _payload()
    payload.pop("subject_id")
    result = _route(_envelope(payload=payload))

    assert result.decision is RouterDecision.HOLD_MALFORMED_PAYLOAD
    assert result.selected_route == RELATIONSHIP_LOSS_TRACK
    assert result.routed_result is None
    assert result.reason_codes == (RouterReason.MALFORMED_PAYLOAD,)
    assert result.diagnostic_code == "relationship_loss_payload_invalid"


def test_known_route_invalid_enum_is_held() -> None:
    payload = _payload()
    payload["entity_status"] = "MAYBE_PRESENT"
    result = _route(_envelope(payload=payload))

    assert result.decision is RouterDecision.HOLD_MALFORMED_PAYLOAD
    assert result.routed_result is None


def test_lifecycle_inconsistency_is_held_as_malformed_payload() -> None:
    payload = _payload(
        event_type=RelationshipEventType.LOSS_CONFIRMED.value,
        entity_status="ACTIVE",
        knowledge_class="FACT",
        with_identity_candidate=False,
    )
    result = _route(_envelope(payload=payload))

    assert result.decision is RouterDecision.HOLD_MALFORMED_PAYLOAD
    assert result.routed_result is None


def test_result_never_grants_mutation_or_execution_authority() -> None:
    routed = _route(_envelope()).to_dict()
    held = _route(_envelope(route_key="projects.unknown")).to_dict()

    for result in (routed, held):
        assert result["relational_self_mutation_allowed"] is False
        assert result["stable_identity_update_allowed"] is False
        assert result["execution_authorized"] is False


def test_result_is_deterministic_and_matches_schema() -> None:
    envelope = _envelope()
    first = _route(envelope)
    second = _route(envelope)

    assert first.route_result_id == second.route_result_id
    assert first.envelope_digest == second.envelope_digest
    assert first.routed_result is not None
    assert second.routed_result is not None
    assert first.routed_result.result_id == second.routed_result.result_id

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(first.to_dict()))
    assert errors == []


def test_duplicate_envelope_source_refs_fail_closed() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        TrackCenterEnvelope(
            envelope_id="track-envelope:duplicate",
            route_key=RELATIONSHIP_LOSS_TRACK,
            payload=_payload(),
            submitted_at="2026-06-25T05:01:00Z",
            source_refs=("source:1", "source:1"),
        )
