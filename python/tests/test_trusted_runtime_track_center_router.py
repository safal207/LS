from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pytest
from jsonschema import Draft202012Validator

from router_payloads_a import payload_a
from router_payloads_b import payload_b
from trusted_runtime.capabilities_constraints_track_center import CAPABILITIES_TRACK
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
ROUTES = (
    RELATIONSHIP_LOSS_TRACK,
    PROJECTS_TRACK,
    VALUES_TRACK,
    ERRORS_TRACK,
    GOALS_TRACK,
    CAPABILITIES_TRACK,
)


def _payload(route: str) -> dict[str, object]:
    primary = payload_a(route)
    return primary if primary is not None else payload_b(route)


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
    assert supported_track_center_routes() == ROUTES


@pytest.mark.parametrize("route", ROUTES)
def test_valid_payload_routes_exactly(route: str) -> None:
    result = _route(route)
    assert result.decision is RouterDecision.ROUTED
    assert result.selected_route == route
    assert result.routed_result is not None
    assert (
        result.routed_result.assessment.decision
        is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    )


def test_capability_hold_and_block_are_preserved() -> None:
    held_payload = _payload(CAPABILITIES_TRACK)
    held_payload.update(
        {
            "event_type": "CURRENT_LIMITATION_CLAIM",
            "capability_status": "CONSTRAINED",
            "constraint_kind": "CONTEXTUAL",
            "repeat_count": 1,
            "evidence_refs": ["evidence:claim"],
            "context_refs": [],
            "observer_refs": ["observer:qa"],
            "identity_candidate_statement": None,
            "identity_scope": None,
            "identity_repeat_key": None,
        }
    )
    blocked_payload = dict(held_payload)
    blocked_payload.update(
        {
            "capability_status": "RECOVERED",
            "constraint_kind": "UNKNOWN",
            "context_refs": ["context:browser"],
        }
    )
    held = _route(CAPABILITIES_TRACK, held_payload)
    blocked = _route(CAPABILITIES_TRACK, blocked_payload)
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
        (CAPABILITIES_TRACK, "capability_id", "capability_constraint_payload_invalid"),
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
        "capability_registry_mutation_allowed",
        "capability_restriction_allowed",
        "global_limitation_assignment_allowed",
        "training_scheduling_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    )
    for route in ROUTES:
        result = _route(route).to_dict()
        assert all(result[field] is False for field in denied)


def test_capability_route_is_deterministic_and_matches_schema() -> None:
    first = _route(CAPABILITIES_TRACK)
    second = _route(CAPABILITIES_TRACK)
    assert first.route_result_id == second.route_result_id
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(first.to_dict())) == []
