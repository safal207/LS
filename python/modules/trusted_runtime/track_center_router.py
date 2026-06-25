"""Deterministic fail-closed routing for LS track-center events.

The router performs exact route matching only. It does not infer a route from
free-form text, mutate identity, write Relational Self, or authorize execution.
Known-route malformed payloads and unknown routes are held for review.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from .continuity_coordinator import EntityStatus, KnowledgeClass
from .relationship_loss_track_center import (
    RELATIONSHIP_LOSS_TRACK,
    RelationshipEventType,
    RelationshipLossEvent,
    RelationshipLossResult,
    process_relationship_event,
)


TRACK_CENTER_ENVELOPE_VERSION = "trusted_runtime.track_center_envelope.v0.1"
TRACK_CENTER_ROUTE_RESULT_VERSION = "trusted_runtime.track_center_route_result.v0.1"
TRACK_CENTER_ROUTER_POLICY_VERSION = "track_center_router.v0.1"
TRACK_CENTER_ROUTER_ID = "runtime:track-center-router"


class TrackCenterRoute(str, Enum):
    RELATIONSHIPS_LOSS = RELATIONSHIP_LOSS_TRACK


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
    routed_result: Optional[RelationshipLossResult]
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
            raise ValueError(
                f"unsupported track-center route result: {self.schema_version}"
            )
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("router reason codes must be unique")

        if self.decision is RouterDecision.ROUTED:
            if self.selected_route is None or self.routed_result is None:
                raise ValueError("routed result requires selected route and payload")
            if self.diagnostic_code is not None:
                raise ValueError("routed result cannot contain a diagnostic code")
        else:
            if self.routed_result is not None:
                raise ValueError("held route result cannot contain routed output")
            if self.diagnostic_code is None:
                raise ValueError("held route result requires a diagnostic code")

        if self.decision is RouterDecision.HOLD_UNKNOWN_ROUTE:
            if self.selected_route is not None:
                raise ValueError("unknown route cannot select a track center")
        elif self.decision is RouterDecision.HOLD_MALFORMED_PAYLOAD:
            if self.selected_route is None:
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
            "routed_result": (
                self.routed_result.to_dict() if self.routed_result else None
            ),
            "diagnostic_code": self.diagnostic_code,
            "relational_self_mutation_allowed": False,
            "stable_identity_update_allowed": False,
            "execution_authorized": False,
            "policy_version": self.policy_version,
            "processed_at": self.processed_at,
            "processed_by": self.processed_by,
            "metadata": dict(self.metadata),
        }


def supported_track_center_routes() -> tuple[str, ...]:
    """Return the immutable v0.1 exact-match route set."""

    return tuple(route.value for route in TrackCenterRoute)


def route_track_center_envelope(
    envelope: TrackCenterEnvelope,
    *,
    processed_at: str,
    processed_by: str = TRACK_CENTER_ROUTER_ID,
) -> TrackCenterRouteResult:
    """Route one envelope without guessing or granting downstream authority."""

    if not processed_at or not processed_by:
        raise ValueError("processed_at and processed_by are required")

    selected_route: Optional[str] = None
    routed_result: Optional[RelationshipLossResult] = None
    diagnostic_code: Optional[str] = None

    if envelope.route_key != TrackCenterRoute.RELATIONSHIPS_LOSS.value:
        decision = RouterDecision.HOLD_UNKNOWN_ROUTE
        reason_codes = (
            RouterReason.UNKNOWN_ROUTE,
            RouterReason.NO_ROUTE_INFERENCE,
        )
        diagnostic_code = "unknown_track_center_route"
    else:
        selected_route = TrackCenterRoute.RELATIONSHIPS_LOSS.value
        try:
            event = _relationship_event_from_mapping(envelope.payload)
            routed_result = process_relationship_event(
                event,
                processed_at=processed_at,
                processed_by="runtime:relationship-loss-track-center",
            )
        except (KeyError, TypeError, ValueError):
            decision = RouterDecision.HOLD_MALFORMED_PAYLOAD
            reason_codes = (RouterReason.MALFORMED_PAYLOAD,)
            diagnostic_code = "relationship_loss_payload_invalid"
        else:
            decision = RouterDecision.ROUTED
            reason_codes = (RouterReason.EXACT_ROUTE_MATCH,)

    result_payload = {
        "envelope_digest": envelope.envelope_digest,
        "requested_route": envelope.route_key,
        "selected_route": selected_route,
        "decision": decision.value,
        "reason_codes": [reason.value for reason in reason_codes],
        "routed_result_id": routed_result.result_id if routed_result else None,
        "diagnostic_code": diagnostic_code,
        "policy_version": TRACK_CENTER_ROUTER_POLICY_VERSION,
    }
    route_result_id = "track-center-route-result:sha256:" + _digest(result_payload)

    return TrackCenterRouteResult(
        route_result_id=route_result_id,
        envelope_id=envelope.envelope_id,
        envelope_digest=envelope.envelope_digest,
        requested_route=envelope.route_key,
        selected_route=selected_route,
        decision=decision,
        reason_codes=reason_codes,
        routed_result=routed_result,
        diagnostic_code=diagnostic_code,
        processed_at=processed_at,
        processed_by=processed_by,
        metadata={
            "supported_routes": list(supported_track_center_routes()),
            "route_matching": "exact_only",
            "free_text_route_inference": False,
            "router_output_is_not_authority": True,
        },
    )


def _relationship_event_from_mapping(
    payload: Mapping[str, Any],
) -> RelationshipLossEvent:
    evidence_refs_raw = payload["evidence_refs"]
    if isinstance(evidence_refs_raw, (str, bytes)):
        raise ValueError("evidence_refs must be a sequence")
    evidence_refs = tuple(str(value) for value in evidence_refs_raw)

    metadata_raw = payload.get("metadata", {})
    if not isinstance(metadata_raw, Mapping):
        raise ValueError("relationship metadata must be a mapping")

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
        evidence_refs=evidence_refs,
        identity_candidate_statement=_optional_string(
            payload.get("identity_candidate_statement")
        ),
        identity_scope=_optional_string(payload.get("identity_scope")),
        identity_repeat_key=_optional_string(payload.get("identity_repeat_key")),
        metadata=dict(metadata_raw),
        schema_version=str(
            payload.get(
                "schema_version",
                "trusted_runtime.relationship_loss_event.v0.1",
            )
        ),
    )


def _optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()
