"""Deterministic fail-closed routing for LS track-center events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from .track_routes import (
    SUPPORTED_ROUTES,
    RoutedTrackResult,
    diagnostic_for_route,
    dispatch_track_event,
)

TRACK_CENTER_ENVELOPE_VERSION = "trusted_runtime.track_center_envelope.v0.1"
TRACK_CENTER_ROUTE_RESULT_VERSION = "trusted_runtime.track_center_route_result.v0.1"
TRACK_CENTER_ROUTER_POLICY_VERSION = "track_center_router.v0.1"
TRACK_CENTER_ROUTER_ID = "runtime:track-center-router"


class TrackCenterRoute(str, Enum):
    RELATIONSHIPS_LOSS = "relationships.loss"
    PROJECTS_LIFECYCLE = "projects.lifecycle"
    VALUES_EVIDENCE = "values.evidence"
    ERRORS_LEARNING = "errors.learning"
    GOALS_COMMITMENTS = "goals.commitments"
    CAPABILITIES_CONSTRAINTS = "capabilities.constraints"


class RouterDecision(str, Enum):
    ROUTED = "ROUTED"
    HOLD_UNKNOWN_ROUTE = "HOLD_UNKNOWN_ROUTE"
    HOLD_MALFORMED_PAYLOAD = "HOLD_MALFORMED_PAYLOAD"


class RouterReason(str, Enum):
    EXACT_ROUTE_MATCH = "EXACT_ROUTE_MATCH"
    UNKNOWN_ROUTE = "UNKNOWN_ROUTE"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    NO_ROUTE_INFERENCE = "NO_ROUTE_INFERENCE"


@dataclass(frozen=True)
class TrackCenterEnvelope:
    envelope_id: str
    route_key: str
    payload: Mapping[str, Any]
    submitted_at: str
    source_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = TRACK_CENTER_ENVELOPE_VERSION

    def __post_init__(self) -> None:
        if not all((self.envelope_id, self.route_key, self.submitted_at)):
            raise ValueError("track-center envelope fields must not be empty")
        if self.schema_version != TRACK_CENTER_ENVELOPE_VERSION:
            raise ValueError(f"unsupported track-center envelope: {self.schema_version}")
        if not isinstance(self.payload, Mapping):
            raise ValueError("track-center payload must be a mapping")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("track-center source_refs must be unique")

    @property
    def envelope_digest(self) -> str:
        return _digest(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "envelope_id": self.envelope_id,
            "route_key": self.route_key,
            "payload": dict(self.payload),
            "submitted_at": self.submitted_at,
            "source_refs": list(self.source_refs),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrackCenterRouteResult:
    route_result_id: str
    envelope_id: str
    envelope_digest: str
    requested_route: str
    selected_route: Optional[str]
    decision: RouterDecision
    reason_codes: tuple[RouterReason, ...]
    routed_result: Optional[RoutedTrackResult]
    diagnostic_code: Optional[str]
    processed_at: str
    processed_by: str = TRACK_CENTER_ROUTER_ID
    metadata: Mapping[str, Any] = field(default_factory=dict)
    policy_version: str = TRACK_CENTER_ROUTER_POLICY_VERSION
    schema_version: str = TRACK_CENTER_ROUTE_RESULT_VERSION

    def __post_init__(self) -> None:
        required = (
            self.route_result_id,
            self.envelope_id,
            self.envelope_digest,
            self.requested_route,
            self.processed_at,
            self.processed_by,
            self.policy_version,
        )
        if not all(required):
            raise ValueError("track-center route result fields must not be empty")
        if self.schema_version != TRACK_CENTER_ROUTE_RESULT_VERSION:
            raise ValueError(f"unsupported route result: {self.schema_version}")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("router reason codes must be unique")
        if self.decision is RouterDecision.ROUTED:
            if self.selected_route is None or self.routed_result is None:
                raise ValueError("routed result requires selected route and payload")
            if self.diagnostic_code is not None:
                raise ValueError("routed result cannot contain a diagnostic code")
        else:
            if self.routed_result is not None or self.diagnostic_code is None:
                raise ValueError("held route result requires only a diagnostic")
        if self.decision is RouterDecision.HOLD_UNKNOWN_ROUTE:
            if self.selected_route is not None:
                raise ValueError("unknown route cannot select a track center")
        elif self.selected_route is None:
            raise ValueError("malformed payload hold requires a known route")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "route_result_id": self.route_result_id,
            "envelope_id": self.envelope_id,
            "envelope_digest": self.envelope_digest,
            "requested_route": self.requested_route,
            "selected_route": self.selected_route,
            "decision": self.decision.value,
            "reason_codes": [reason.value for reason in self.reason_codes],
            "routed_result": self.routed_result.to_dict() if self.routed_result else None,
            "diagnostic_code": self.diagnostic_code,
            "relational_self_mutation_allowed": False,
            "project_registry_mutation_allowed": False,
            "task_scheduling_allowed": False,
            "value_registry_mutation_allowed": False,
            "priority_mutation_allowed": False,
            "incident_registry_mutation_allowed": False,
            "blame_assignment_allowed": False,
            "remediation_scheduling_allowed": False,
            "goal_registry_mutation_allowed": False,
            "obligation_assignment_allowed": False,
            "work_scheduling_allowed": False,
            "capability_registry_mutation_allowed": False,
            "capability_restriction_allowed": False,
            "global_limitation_assignment_allowed": False,
            "training_scheduling_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def supported_track_center_routes() -> tuple[str, ...]:
    routes = tuple(route.value for route in TrackCenterRoute)
    if routes != SUPPORTED_ROUTES:
        raise RuntimeError("track-center route registry mismatch")
    return routes


def route_track_center_envelope(
    envelope: TrackCenterEnvelope,
    *,
    processed_at: str,
    processed_by: str = TRACK_CENTER_ROUTER_ID,
) -> TrackCenterRouteResult:
    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")

    if envelope.route_key not in supported_track_center_routes():
        selected_route = None
        routed_result = None
        decision = RouterDecision.HOLD_UNKNOWN_ROUTE
        reasons = (RouterReason.UNKNOWN_ROUTE, RouterReason.NO_ROUTE_INFERENCE)
        diagnostic = "unknown_track_center_route"
    else:
        selected_route = envelope.route_key
        try:
            routed_result = dispatch_track_event(
                envelope.route_key,
                envelope.payload,
                processed_at=processed_at,
            )
        except (KeyError, TypeError, ValueError):
            routed_result = None
            decision = RouterDecision.HOLD_MALFORMED_PAYLOAD
            reasons = (RouterReason.MALFORMED_PAYLOAD,)
            diagnostic = diagnostic_for_route(envelope.route_key)
        else:
            decision = RouterDecision.ROUTED
            reasons = (RouterReason.EXACT_ROUTE_MATCH,)
            diagnostic = None

    identity = {
        "envelope_digest": envelope.envelope_digest,
        "requested_route": envelope.route_key,
        "selected_route": selected_route,
        "decision": decision.value,
        "reason_codes": [reason.value for reason in reasons],
        "routed_result_id": routed_result.result_id if routed_result else None,
        "diagnostic_code": diagnostic,
        "policy_version": TRACK_CENTER_ROUTER_POLICY_VERSION,
    }
    return TrackCenterRouteResult(
        route_result_id="track-center-route-result:sha256:" + _digest(identity),
        envelope_id=envelope.envelope_id,
        envelope_digest=envelope.envelope_digest,
        requested_route=envelope.route_key,
        selected_route=selected_route,
        decision=decision,
        reason_codes=reasons,
        routed_result=routed_result,
        diagnostic_code=diagnostic,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "supported_routes": list(supported_track_center_routes()),
            "route_matching": "exact_only",
            "free_text_route_inference": False,
            "router_output_is_not_authority": True,
        },
    )


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
