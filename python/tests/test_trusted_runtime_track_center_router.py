from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import ContinuityDecision
from trusted_runtime.errors_learning_track_center import ERRORS_TRACK
from trusted_runtime.goals_commitments_track_center import GOALS_TRACK
from trusted_runtime.projects_track_center import PROJECTS_TRACK
from trusted_runtime.relationship_loss_track_center import RELATIONSHIP_LOSS_TRACK
from trusted_runtime.track_center_router import (
    RouterDecision,
    TrackCenterEnvelope,
    route_track_center_envelope,
    supported_track_center_routes,
)
from trusted_runtime.values_track_center import VALUES_TRACK

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/track_center_route_result.schema.json"


def _payload(route: str) -> dict[str, object]:
    if route == RELATIONSHIP_LOSS_TRACK:
        return {
            "schema_version": "trusted_runtime.relationship_loss_event.v0.1",
            "event_id": "relationship-event:router",
            "relationship_id": "relationship:mentor",
            "subject_id": "human:mentor",
            "event_type": "REMEMBERED_INFLUENCE",
            "entity_status": "DECEASED",
            "knowledge_class": "MEMORY",
            "statement": "Remembered discipline remains influential.",
            "occurred_at": "2026-06-25T05:00:00Z",
            "confidence": 0.86,
            "evidence_refs": ["memory:mentor:review"],
            "identity_candidate_statement": "Preserve evidence-first reviews.",
            "identity_scope": "relationships",
            "identity_repeat_key": "mentor:evidence-first",
            "metadata": {},
        }
    if route == PROJECTS_TRACK:
        return {
            "schema_version": "trusted_runtime.project_event.v0.1",
            "event_id": "project-event:router",
            "project_id": "project:ls",
            "event_type": "PROJECT_LESSON_RETAINED",
            "project_status": "COMPLETED",
            "previous_status": None,
            "knowledge_class": "MEMORY",
            "statement": "A bounded project lesson.",
            "occurred_at": "2026-06-25T05:00:00Z",
            "confidence": 0.91,
            "evidence_refs": ["evidence:project"],
            "identity_candidate_statement": "Preserve evidence-first delivery.",
            "identity_scope": "projects",
            "identity_repeat_key": "project:ls:evidence-first",
            "metadata": {},
        }
    if route == VALUES_TRACK:
        return {
            "schema_version": "trusted_runtime.value_event.v0.1",
            "event_id": "value-event:router",
            "value_key": "value:evidence-first",
            "event_type": "VALUE_REAFFIRMED",
            "value_status": "ACTIVE",
            "knowledge_class": "FACT",
            "statement": "Evidence should precede confident conclusions.",
            "occurred_at": "2026-06-25T05:00:00Z",
            "confidence": 0.92,
            "repeat_count": 3,
            "evidence_refs": ["evidence:value:work", "evidence:value:family"],
            "context_refs": ["context:work", "context:family"],
            "identity_candidate_statement": "Prefer evidence before conclusions.",
            "identity_scope": "values",
            "identity_repeat_key": "value:evidence-first",
            "metadata": {},
        }
    if route == ERRORS_TRACK:
        return {
            "schema_version": "trusted_runtime.error_learning_event.v0.1",
            "event_id": "error-event:router",
            "error_id": "error:checkout-timeout",
            "event_type": "ERROR_RECURRENCE_CONFIRMED",
            "error_status": "RECURRING",
            "outcome_class": "FAILED",
            "knowledge_class": "FACT",
            "statement": "A repeated failure produced a bounded learning signal.",
            "occurred_at": "2026-06-25T05:00:00Z",
            "confidence": 0.93,
            "occurrence_count": 2,
            "evidence_refs": ["evidence:error:api", "evidence:error:ui"],
            "context_refs": ["context:api", "context:ui"],
            "observer_refs": ["observer:qa", "observer:sre"],
            "identity_candidate_statement": "Verify timeout assumptions before release.",
            "identity_scope": "errors.learning",
            "identity_repeat_key": "error:timeout:verification",
            "metadata": {},
        }
    return {
        "schema_version": "trusted_runtime.goal_commitment_event.v0.1",
        "event_id": "goal-event:router",
        "goal_id": "goal:release",
        "event_type": "FOLLOW_THROUGH_VERIFIED",
        "goal_status": "COMPLETED",
        "commitment_level": "COMMITMENT",
        "knowledge_class": "FACT",
        "statement": "Repeated follow-through produced a bounded lesson.",
        "occurred_at": "2026-06-25T05:00:00Z",
        "confidence": 0.94,
        "repeat_count": 2,
        "evidence_refs": ["evidence:goal:work", "evidence:goal:family"],
        "context_refs": ["context:work", "context:family"],
        "commitment_refs": ["commitment:1", "commitment:2"],
        "identity_candidate_statement": "Confirm scope before accepting deadlines.",
        "identity_scope": "goals.commitments",
        "identity_repeat_key": "goals:scope-before-deadline",
        "metadata": {},
    }


def _route(route: str, payload: Optional[dict[str, object]] = None):
    envelope = TrackCenterEnvelope(
        envelope_id="track-envelope:1",
        route_key=route,
        payload=payload if payload is not None else _payload(route),
        submitted_at="2026-06-25T05:01:00Z",
        source_refs=("source:router-test",),
    )
    return route_track_center_envelope(
        envelope,
        processed_at="2026-06-25T05:02:00Z",
    )


def test_supported_routes_are_explicit() -> None:
    assert supported_track_center_routes() == (
        RELATIONSHIP_LOSS_TRACK,
        PROJECTS_TRACK,
        VALUES_TRACK,
        ERRORS_TRACK,
        GOALS_TRACK,
    )


@pytest.mark.parametrize(
    "route",
    [
        RELATIONSHIP_LOSS_TRACK,
        PROJECTS_TRACK,
        VALUES_TRACK,
        ERRORS_TRACK,
        GOALS_TRACK,
    ],
)
def test_valid_payload_routes_exactly(route: str) -> None:
    result = _route(route)
    assert result.decision is RouterDecision.ROUTED
    assert result.selected_route == route
    assert result.routed_result is not None
    assert (
        result.routed_result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )


def test_goal_hold_and_block_are_preserved() -> None:
    paused = _payload(GOALS_TRACK)
    paused.update(
        {
            "event_type": "CURRENT_DUTY_CLAIM",
            "goal_status": "PAUSED",
            "repeat_count": 1,
            "evidence_refs": ["evidence:goal:claim"],
            "context_refs": ["context:work"],
            "commitment_refs": ["commitment:1"],
            "identity_candidate_statement": None,
            "identity_scope": None,
            "identity_repeat_key": None,
        }
    )
    cancelled = dict(paused)
    cancelled["goal_status"] = "CANCELLED"
    held = _route(GOALS_TRACK, paused)
    blocked = _route(GOALS_TRACK, cancelled)
    assert held.routed_result is not None
    assert blocked.routed_result is not None
    assert held.routed_result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert (
        blocked.routed_result.assessment.decision
        is ContinuityDecision.BLOCK_FALSE_PRESENCE
    )


def test_unknown_route_is_held() -> None:
    result = _route("unknown.route", {})
    assert result.decision is RouterDecision.HOLD_UNKNOWN_ROUTE
    assert result.selected_route is None
    assert result.diagnostic_code == "unknown_track_center_route"


@pytest.mark.parametrize(
    ("route", "field", "diagnostic"),
    [
        (RELATIONSHIP_LOSS_TRACK, "subject_id", "relationship_loss_payload_invalid"),
        (PROJECTS_TRACK, "project_id", "project_payload_invalid"),
        (VALUES_TRACK, "value_key", "value_payload_invalid"),
        (ERRORS_TRACK, "error_id", "error_learning_payload_invalid"),
        (GOALS_TRACK, "goal_id", "goal_commitment_payload_invalid"),
    ],
)
def test_malformed_payload_is_held(route: str, field: str, diagnostic: str) -> None:
    payload = _payload(route)
    payload.pop(field)
    result = _route(route, payload)
    assert result.decision is RouterDecision.HOLD_MALFORMED_PAYLOAD
    assert result.selected_route == route
    assert result.diagnostic_code == diagnostic


def test_router_never_grants_authority() -> None:
    denied = (
        "relational_self_mutation_allowed",
        "project_registry_mutation_allowed",
        "task_scheduling_allowed",
        "value_registry_mutation_allowed",
        "priority_mutation_allowed",
        "incident_registry_mutation_allowed",
        "blame_assignment_allowed",
        "remediation_scheduling_allowed",
        "goal_registry_mutation_allowed",
        "obligation_assignment_allowed",
        "work_scheduling_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    )
    for route in (
        RELATIONSHIP_LOSS_TRACK,
        PROJECTS_TRACK,
        VALUES_TRACK,
        ERRORS_TRACK,
        GOALS_TRACK,
    ):
        result = _route(route).to_dict()
        assert all(result[field] is False for field in denied)


def test_goal_route_is_deterministic_and_matches_schema() -> None:
    first = _route(GOALS_TRACK)
    second = _route(GOALS_TRACK)
    assert first.route_result_id == second.route_result_id
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(first.to_dict())) == []
