from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal, Optional, Set

ReleaseDecision = Literal[
    "AUTHORIZED",
    "BLOCKED_UNVERIFIED",
    "BLOCKED_PROVENANCE",
    "INCONCLUSIVE_MISSING_EVIDENCE",
]


class ContractViolation(ValueError):
    """Raised when a benchmark artifact violates a frozen v0.1 contract."""


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 for a JSON-compatible mapping."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _require_mapping(payload: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ContractViolation(f"{name} must be an object")
    return payload


def _require_non_empty_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{field} must be a non-empty string")
    return value


def _require_sequence(payload: Mapping[str, Any], field: str) -> Sequence[Any]:
    value = payload.get(field)
    if not isinstance(value, list):
        raise ContractViolation(f"{field} must be an array")
    return value


def _require_unique(values: Sequence[str], field: str) -> None:
    if len(values) != len(set(values)):
        raise ContractViolation(f"{field} must contain unique values")


def validate_scenario(payload: Mapping[str, Any]) -> None:
    payload = _require_mapping(payload, "scenario")
    if payload.get("schema") != "ls.multi-session.scenario.v0.1":
        raise ContractViolation("unsupported scenario schema")

    _require_non_empty_string(payload, "scenario_id")
    sessions = _require_sequence(payload, "sessions")
    if len(sessions) < 2:
        raise ContractViolation("sessions must contain at least two entries")

    session_ids: list[str] = []
    for session in sessions:
        session = _require_mapping(session, "session")
        session_ids.append(_require_non_empty_string(session, "session_id"))
        _require_non_empty_string(session, "role")
    _require_unique(session_ids, "session_id")

    dependencies = _require_sequence(payload, "dependencies")
    dependency_ids: list[str] = []
    for dependency in dependencies:
        dependency = _require_mapping(dependency, "dependency")
        dependency_ids.append(_require_non_empty_string(dependency, "dependency_id"))
        producer = _require_non_empty_string(dependency, "producer_session")
        consumer = _require_non_empty_string(dependency, "consumer_session")
        if producer not in session_ids or consumer not in session_ids:
            raise ContractViolation("dependency references an unknown session")
        if producer == consumer:
            raise ContractViolation("dependency cannot target its producer")
    _require_unique(dependency_ids, "dependency_id")

    events = _require_sequence(payload, "events")
    if not events:
        raise ContractViolation("events must not be empty")

    event_ids: list[str] = []
    sequence_numbers: list[int] = []
    for event in events:
        validate_coordination_event(event, known_sessions=set(session_ids))
        event_ids.append(str(event["event_id"]))
        sequence_numbers.append(int(event["sequence"]))
    _require_unique(event_ids, "event_id")
    if sequence_numbers != sorted(sequence_numbers) or len(sequence_numbers) != len(set(sequence_numbers)):
        raise ContractViolation("event sequence values must be strictly increasing")


def validate_coordination_event(
    payload: Mapping[str, Any], *, known_sessions: Optional[Set[str]] = None
) -> None:
    payload = _require_mapping(payload, "coordination event")
    if payload.get("schema") != "ls.multi-session.coordination-event.v0.1":
        raise ContractViolation("unsupported coordination event schema")

    _require_non_empty_string(payload, "event_id")
    _require_non_empty_string(payload, "event_type")
    producer = _require_non_empty_string(payload, "producer_session")
    if known_sessions is not None and producer not in known_sessions:
        raise ContractViolation("event producer references an unknown session")

    sequence = payload.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise ContractViolation("sequence must be a positive integer")

    generation = payload.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise ContractViolation("generation must be a non-negative integer")

    affected = _require_sequence(payload, "affected_sessions")
    if not all(isinstance(item, str) and item for item in affected):
        raise ContractViolation("affected_sessions must contain non-empty strings")
    _require_unique(list(affected), "affected_sessions")
    if known_sessions is not None and not set(affected).issubset(known_sessions):
        raise ContractViolation("event affects an unknown session")

    _require_mapping(payload.get("payload"), "event payload")


def validate_lifecycle_receipt(
    payload: Mapping[str, Any], *, scenario: Optional[Mapping[str, Any]] = None
) -> None:
    payload = _require_mapping(payload, "lifecycle receipt")
    if payload.get("schema") != "ls.multi-session.lifecycle-receipt.v0.1":
        raise ContractViolation("unsupported lifecycle receipt schema")

    event_id = _require_non_empty_string(payload, "event_id")
    producer = _require_non_empty_string(payload, "producer_session")
    _require_non_empty_string(payload, "transition")
    _require_non_empty_string(payload, "previous_state_hash")
    _require_non_empty_string(payload, "new_state_hash")
    _require_non_empty_string(payload, "dependency_id")

    generation = payload.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise ContractViolation("generation must be a non-negative integer")

    affected = _require_sequence(payload, "affected_sessions")
    if not affected or not all(isinstance(item, str) and item for item in affected):
        raise ContractViolation("affected_sessions must contain at least one session")
    _require_unique(list(affected), "affected_sessions")

    verification = _require_mapping(payload.get("verification"), "verification")
    status = verification.get("status")
    if status not in {"VERIFIED", "FAILED", "NOT_RUN"}:
        raise ContractViolation("verification.status is invalid")
    if status == "VERIFIED":
        _require_non_empty_string(verification, "verifier")
        _require_non_empty_string(verification, "evidence_ref")

    if scenario is not None:
        validate_scenario(scenario)
        events = {event["event_id"]: event for event in scenario["events"]}
        event = events.get(event_id)
        if event is None:
            raise ContractViolation("receipt event_id is not present in scenario")
        if producer != event["producer_session"]:
            raise ContractViolation("receipt producer does not match scenario event")
        if generation != event["generation"]:
            raise ContractViolation("receipt generation does not match scenario event")
        known_sessions = {session["session_id"] for session in scenario["sessions"]}
        if not set(affected).issubset(known_sessions):
            raise ContractViolation("receipt affects an unknown session")


def validate_route_result(payload: Mapping[str, Any]) -> None:
    payload = _require_mapping(payload, "route result")
    if payload.get("schema") != "ls.multi-session.route-result.v0.1":
        raise ContractViolation("unsupported route result schema")

    _require_non_empty_string(payload, "route_id")
    _require_non_empty_string(payload, "scenario_hash")
    verdict = payload.get("verdict")
    allowed = {
        "SAFE_PARETO_CANDIDATE",
        "SAFE_DOMINATED",
        "UNSAFE_STALE_ACTION",
        "UNSAFE_DEPENDENCY_RELEASE",
        "UNSAFE_UNAUTHORIZED_EVENT",
        "UNSAFE_DUPLICATE_EFFECT",
        "INCONCLUSIVE_MISSING_EVIDENCE",
    }
    if verdict not in allowed:
        raise ContractViolation("route verdict is invalid")

    metrics = _require_mapping(payload.get("metrics"), "metrics")
    for name in (
        "stale_action_count",
        "dependency_violation_count",
        "unverified_release_count",
        "unauthorized_event_acceptance_count",
        "duplicate_side_effect_count",
    ):
        value = metrics.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ContractViolation(f"metrics.{name} must be a non-negative integer")

    evidence_refs = _require_sequence(payload, "evidence_refs")
    if not all(isinstance(item, str) and item for item in evidence_refs):
        raise ContractViolation("evidence_refs must contain non-empty strings")


def classify_dependency_release(
    receipt: Optional[Mapping[str, Any]],
    *, expected_producer_session: str,
    expected_generation: int,
) -> ReleaseDecision:
    """Fail closed unless a receipt proves provenance, freshness, and verification."""

    if receipt is None:
        return "INCONCLUSIVE_MISSING_EVIDENCE"

    try:
        validate_lifecycle_receipt(receipt)
    except ContractViolation:
        return "INCONCLUSIVE_MISSING_EVIDENCE"

    if (
        receipt["producer_session"] != expected_producer_session
        or receipt["generation"] != expected_generation
    ):
        return "BLOCKED_PROVENANCE"

    if receipt["verification"]["status"] != "VERIFIED":
        return "BLOCKED_UNVERIFIED"

    return "AUTHORIZED"
