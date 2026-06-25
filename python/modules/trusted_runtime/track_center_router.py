"""Deterministic fail-closed routing for LS track-center events."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Union

from .continuity_coordinator import EntityStatus, KnowledgeClass
from .projects_track_center import (
    PROJECTS_TRACK,
    ProjectEvent,
    ProjectEventType,
    ProjectStatus,
    ProjectTrackResult,
    process_project_event,
)
from .relationship_loss_track_center import (
    RELATIONSHIP_LOSS_TRACK,
    RelationshipEventType,
    RelationshipLossEvent,
    RelationshipLossResult,
    process_relationship_event,
)
from .values_track_center import (
    VALUES_TRACK,
    ValueEvent,
    ValueEventType,
    ValueStatus,
    ValueTrackResult,
    process_value_event,
)

TRACK_CENTER_ENVELOPE_VERSION = "trusted_runtime.track_center_envelope.v0.1"
TRACK_CENTER_ROUTE_RESULT_VERSION = "trusted_runtime.track_center_route_result.v0.1"
TRACK_CENTER_ROUTER_POLICY_VERSION = "track_center_router.v0.1"
TRACK_CENTER_ROUTER_ID = "runtime:track-center-router"

RoutedTrackResult = Union[RelationshipLossResult, ProjectTrackResult, ValueTrackResult]


class TrackCenterRoute(str, Enum):
    RELATIONSHIPS_LOSS = RELATIONSHIP_LOSS_TRACK
    PROJECTS_LIFECYCLE = PROJECTS_TRACK
    VALUES_EVIDENCE = VALUES_TRACK


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
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def supported_track_center_routes() -> tuple[str, ...]:
    return tuple(route.value for route in TrackCenterRoute)


def route_track_center_envelope(
    envelope: TrackCenterEnvelope,
    *,
    processed_at: str,
    processed_by: str = TRACK_CENTER_ROUTER_ID,
) -> TrackCenterRouteResult:
    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")

    routes = set(supported_track_center_routes())
    if envelope.route_key not in routes:
        selected_route = None
        routed_result = None
        decision = RouterDecision.HOLD_UNKNOWN_ROUTE
        reasons = (RouterReason.UNKNOWN_ROUTE, RouterReason.NO_ROUTE_INFERENCE)
        diagnostic = "unknown_track_center_route"
    else:
        selected_route = envelope.route_key
        try:
            routed_result = _dispatch(envelope, processed_at)
        except (KeyError, TypeError, ValueError):
            routed_result = None
            decision = RouterDecision.HOLD_MALFORMED_PAYLOAD
            reasons = (RouterReason.MALFORMED_PAYLOAD,)
            diagnostic = _diagnostic_for_route(envelope.route_key)
        else:
            decision = RouterDecision.ROUTED
            reasons = (RouterReason.EXACT_ROUTE_MATCH,)
            diagnostic = None

    payload = {
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
        route_result_id="track-center-route-result:sha256:" + _digest(payload),
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


def _dispatch(
    envelope: TrackCenterEnvelope,
    processed_at: str,
) -> RoutedTrackResult:
    if envelope.route_key == RELATIONSHIP_LOSS_TRACK:
        return process_relationship_event(
            _relationship_event(envelope.payload),
            processed_at=processed_at,
            processed_by="runtime:relationship-loss-track-center",
        )
    if envelope.route_key == PROJECTS_TRACK:
        return process_project_event(
            _project_event(envelope.payload),
            processed_at=processed_at,
            processed_by="runtime:projects-track-center",
        )
    return process_value_event(
        _value_event(envelope.payload),
        processed_at=processed_at,
        processed_by="runtime:values-track-center",
    )


def _relationship_event(payload: Mapping[str, Any]) -> RelationshipLossEvent:
    return RelationshipLossEvent(
        event_id=str(payload["event_id"]),
        relationship_id=str(payload["relationship_id"]),
        subject_id=str(payload["subject_id"]),
        event_type=RelationshipEventType(str(payload["event_type"])),
        entity_status=EntityStatus(str(payload["entity_status"])),
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "relationship"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.relationship_loss_event.v0.1")),
    )


def _project_event(payload: Mapping[str, Any]) -> ProjectEvent:
    previous = payload.get("previous_status")
    return ProjectEvent(
        event_id=str(payload["event_id"]),
        project_id=str(payload["project_id"]),
        event_type=ProjectEventType(str(payload["event_type"])),
        project_status=ProjectStatus(str(payload["project_status"])),
        previous_status=ProjectStatus(str(previous)) if previous is not None else None,
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "project"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.project_event.v0.1")),
    )


def _value_event(payload: Mapping[str, Any]) -> ValueEvent:
    return ValueEvent(
        event_id=str(payload["event_id"]),
        value_key=str(payload["value_key"]),
        event_type=ValueEventType(str(payload["event_type"])),
        value_status=ValueStatus(str(payload["value_status"])),
        knowledge_class=KnowledgeClass(str(payload["knowledge_class"])),
        statement=str(payload["statement"]),
        occurred_at=str(payload["occurred_at"]),
        confidence=float(payload["confidence"]),
        repeat_count=int(payload["repeat_count"]),
        evidence_refs=_refs(payload, "evidence_refs"),
        context_refs=_refs(payload, "context_refs"),
        identity_candidate_statement=_optional(payload, "identity_candidate_statement"),
        identity_scope=_optional(payload, "identity_scope"),
        identity_repeat_key=_optional(payload, "identity_repeat_key"),
        metadata=_metadata(payload, "value"),
        schema_version=str(payload.get("schema_version", "trusted_runtime.value_event.v0.1")),
    )


def _refs(payload: Mapping[str, Any], field_name: str) -> tuple[str, ...]:
    raw = payload[field_name]
    if isinstance(raw, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence")
    return tuple(str(value) for value in raw)


def _metadata(payload: Mapping[str, Any], kind: str) -> dict[str, Any]:
    raw = payload.get("metadata", {})
    if not isinstance(raw, Mapping):
        raise ValueError(f"{kind} metadata must be a mapping")
    return dict(raw)


def _optional(payload: Mapping[str, Any], field_name: str) -> Optional[str]:
    value = payload.get(field_name)
    return None if value is None else str(value)


def _diagnostic_for_route(route: str) -> str:
    return {
        RELATIONSHIP_LOSS_TRACK: "relationship_loss_payload_invalid",
        PROJECTS_TRACK: "project_payload_invalid",
        VALUES_TRACK: "value_payload_invalid",
    }[route]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
