#!/usr/bin/env python3
"""Dependency-free validator and reducer for LS durable approval conformance v0.1."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

AUTHORITY_STATES = {"PENDING", "APPROVED", "REJECTED", "EXPIRED", "INVALIDATED", "LOST"}
REQUESTER_STATES = {"ATTACHED", "DETACHED", "CANCELLED"}
PRESENTATION_STATES = {"NOT_PRESENTED", "VISIBLE", "DISCONNECTED", "RESTORED"}
EXECUTION_STATES = {"UNUSED", "CLAIMED", "COMMITTED", "FAILED", "IN_DOUBT"}

BOUND_DIGEST_FIELDS = {
    "action_digest",
    "scope_digest",
    "policy_digest",
    "workspace_identity",
    "target_state_digest",
}
REQUIRED_ENVELOPE_FIELDS = {
    "schema_version",
    "approval_id",
    "trajectory_id",
    "continuation_id",
    "requester_id",
    "tool_call_id",
    *BOUND_DIGEST_FIELDS,
    "created_at",
    "expiry_policy",
    "single_use",
}
REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "approval_id",
    "sequence",
    "event_type",
    "occurred_at",
    "actor",
}
EVENT_OWNERS = {
    "ApprovalRequested": {"SYSTEM", "RUNTIME"},
    "ApprovalPresented": {"RUNTIME"},
    "RequesterDetached": {"AGENT", "RUNTIME"},
    "RequesterCancelled": {"AGENT", "RUNTIME"},
    "TransportDisconnected": {"TRANSPORT"},
    "TransportRestored": {"TRANSPORT"},
    "UiDismissed": {"USER", "RUNTIME"},
    "WaitWindowElapsed": {"RUNTIME"},
    "UserApproved": {"USER", "REVIEWER"},
    "UserRejected": {"USER", "REVIEWER"},
    "ApprovalExpired": {"POLICY"},
    "ApprovalInvalidated": {"RUNTIME", "VERIFIER"},
    "ExecutionClaimed": {"RUNTIME", "VERIFIER"},
    "EffectObserved": {"RUNTIME", "VERIFIER"},
    "RuntimeRestarted": {"RUNTIME"},
    "LostStateDetected": {"RUNTIME"},
}


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be an object")
    return value


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def parse_timestamp(value: Any, location: str, errors: list[str]) -> datetime | None:
    if not isinstance(value, str):
        errors.append(f"{location}: timestamp must be a string")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{location}: invalid RFC 3339 timestamp {value!r}")
        return None


def validate_schema_contracts(
    envelope_schema: dict[str, Any],
    event_schema: dict[str, Any],
    errors: list[str],
) -> None:
    expected_draft = "https://json-schema.org/draft/2020-12/schema"
    require(errors, envelope_schema.get("$schema") == expected_draft, "envelope schema: expected Draft 2020-12")
    require(errors, event_schema.get("$schema") == expected_draft, "event schema: expected Draft 2020-12")
    require(
        errors,
        envelope_schema.get("properties", {}).get("schema_version", {}).get("const")
        == "ls-durable-approval-envelope-v0.1",
        "envelope schema: unexpected schema_version",
    )
    require(
        errors,
        event_schema.get("properties", {}).get("schema_version", {}).get("const")
        == "ls-approval-lifecycle-event-v0.1",
        "event schema: unexpected schema_version",
    )
    declared_events = set(event_schema.get("properties", {}).get("event_type", {}).get("enum", []))
    require(errors, declared_events == set(EVENT_OWNERS), "event schema: event_type enum does not match reducer")


def validate_envelope(envelope: Any, errors: list[str]) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        errors.append("fixture.envelope: must be an object")
        return {}
    missing = REQUIRED_ENVELOPE_FIELDS - envelope.keys()
    require(errors, not missing, f"fixture.envelope: missing {sorted(missing)}")
    require(
        errors,
        envelope.get("schema_version") == "ls-durable-approval-envelope-v0.1",
        "fixture.envelope: unexpected schema_version",
    )
    for field in REQUIRED_ENVELOPE_FIELDS - {"expiry_policy", "single_use"}:
        require(errors, isinstance(envelope.get(field), str) and bool(envelope.get(field)), f"fixture.envelope: {field} is required")
    for field in BOUND_DIGEST_FIELDS - {"workspace_identity"}:
        value = envelope.get(field)
        require(errors, isinstance(value, str) and value.startswith("sha256:"), f"fixture.envelope: {field} must use sha256:")
    require(errors, envelope.get("single_use") is True, "fixture.envelope: single_use must be true")
    parse_timestamp(envelope.get("created_at"), "fixture.envelope.created_at", errors)

    expiry = envelope.get("expiry_policy")
    if expiry is not None:
        require(errors, isinstance(expiry, dict), "fixture.envelope.expiry_policy: must be null or object")
        if isinstance(expiry, dict):
            require(errors, bool(expiry.get("policy_id")), "fixture.envelope.expiry_policy.policy_id is required")
            parse_timestamp(expiry.get("expires_at"), "fixture.envelope.expiry_policy.expires_at", errors)
    return envelope


def resolution_from(event: dict[str, Any]) -> dict[str, Any]:
    actor = event.get("actor", {})
    return {
        "event_type": event.get("event_type"),
        "actor_type": actor.get("type"),
        "actor_id": actor.get("id"),
        "reason": event.get("reason"),
        "evidence_ref": event.get("evidence_ref"),
    }


def reduce_case(
    envelope: dict[str, Any],
    case: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    case_id = str(case.get("case_id"))
    errors: list[str] = []
    events = case.get("events")
    if not isinstance(events, list) or not events:
        return {}, [f"{case_id}: events must be a non-empty array"]

    snapshot: dict[str, Any] = {
        "authority_state": None,
        "requester_state": None,
        "presentation_state": None,
        "execution_state": None,
        "resolution": None,
    }
    seen_ids: set[str] = set()
    previous_time: datetime | None = None
    claim_count = 0

    for index, event in enumerate(events):
        location = f"{case_id}.events[{index}]"
        if not isinstance(event, dict):
            errors.append(f"{location}: must be an object")
            continue

        missing = REQUIRED_EVENT_FIELDS - event.keys()
        require(errors, not missing, f"{location}: missing {sorted(missing)}")
        require(
            errors,
            event.get("schema_version") == "ls-approval-lifecycle-event-v0.1",
            f"{location}: unexpected schema_version",
        )
        event_id = event.get("event_id")
        require(errors, isinstance(event_id, str) and bool(event_id), f"{location}: event_id is required")
        require(errors, event_id not in seen_ids, f"{location}: duplicate event_id {event_id!r}")
        if isinstance(event_id, str):
            seen_ids.add(event_id)

        require(errors, event.get("sequence") == index + 1, f"{location}: sequence must equal {index + 1}")
        require(
            errors,
            event.get("approval_id") == envelope.get("approval_id"),
            f"{location}: approval_id mismatch",
        )
        occurred_at = parse_timestamp(event.get("occurred_at"), f"{location}.occurred_at", errors)
        if occurred_at is not None and previous_time is not None:
            require(errors, occurred_at >= previous_time, f"{location}: timestamps must be non-decreasing")
        if occurred_at is not None:
            previous_time = occurred_at

        event_type = event.get("event_type")
        require(errors, event_type in EVENT_OWNERS, f"{location}: unsupported event_type {event_type!r}")
        actor = event.get("actor")
        if not isinstance(actor, dict):
            errors.append(f"{location}.actor: must be an object")
            actor_type = None
            actor_id = None
        else:
            actor_type = actor.get("type")
            actor_id = actor.get("id")
            require(errors, bool(actor_id), f"{location}.actor.id is required")
        if event_type in EVENT_OWNERS:
            require(
                errors,
                actor_type in EVENT_OWNERS[event_type],
                f"{location}: actor {actor_type!r} cannot emit {event_type}",
            )

        if index == 0:
            require(errors, event_type == "ApprovalRequested", f"{location}: first event must be ApprovalRequested")

        if event_type == "ApprovalRequested":
            require(errors, snapshot["authority_state"] is None, f"{location}: approval already requested")
            snapshot.update(
                authority_state="PENDING",
                requester_state="ATTACHED",
                presentation_state="NOT_PRESENTED",
                execution_state="UNUSED",
                resolution=None,
            )

        elif snapshot["authority_state"] is None:
            errors.append(f"{location}: event before ApprovalRequested")

        elif event_type == "ApprovalPresented":
            snapshot["presentation_state"] = "VISIBLE"

        elif event_type == "RequesterDetached":
            snapshot["requester_state"] = "DETACHED"

        elif event_type == "RequesterCancelled":
            snapshot["requester_state"] = "CANCELLED"

        elif event_type == "TransportDisconnected":
            snapshot["presentation_state"] = "DISCONNECTED"

        elif event_type == "TransportRestored":
            snapshot["presentation_state"] = "RESTORED"

        elif event_type == "UiDismissed":
            snapshot["presentation_state"] = "NOT_PRESENTED"

        elif event_type == "WaitWindowElapsed":
            pass

        elif event_type in {"UserApproved", "UserRejected", "ApprovalExpired", "ApprovalInvalidated"}:
            require(
                errors,
                snapshot["authority_state"] == "PENDING",
                f"{location}: authority resolution requires PENDING",
            )
            require(errors, bool(event.get("reason")), f"{location}: resolution reason is required")

            if event_type == "UserApproved":
                snapshot["authority_state"] = "APPROVED"
            elif event_type == "UserRejected":
                snapshot["authority_state"] = "REJECTED"
            elif event_type == "ApprovalExpired":
                require(
                    errors,
                    envelope.get("expiry_policy") is not None,
                    f"{location}: expiry requires configured expiry_policy",
                )
                require(errors, bool(event.get("evidence_ref")), f"{location}: expiry evidence_ref is required")
                snapshot["authority_state"] = "EXPIRED"
            elif event_type == "ApprovalInvalidated":
                require(errors, bool(event.get("evidence_ref")), f"{location}: invalidation evidence_ref is required")
                snapshot["authority_state"] = "INVALIDATED"
            snapshot["resolution"] = resolution_from(event)

        elif event_type == "ExecutionClaimed":
            require(errors, snapshot["authority_state"] == "APPROVED", f"{location}: execution requires APPROVED authority")
            require(errors, snapshot["requester_state"] == "ATTACHED", f"{location}: cancelled/detached requester cannot claim execution")
            require(errors, snapshot["execution_state"] == "UNUSED", f"{location}: execution approval is single-use")
            bindings = event.get("bindings")
            require(errors, isinstance(bindings, dict), f"{location}: bindings are required")
            if isinstance(bindings, dict):
                for field in BOUND_DIGEST_FIELDS:
                    require(
                        errors,
                        bindings.get(field) == envelope.get(field),
                        f"{location}: binding mismatch for {field}",
                    )
            claim_count += 1
            require(errors, claim_count == 1, f"{location}: duplicate execution claim")
            snapshot["execution_state"] = "CLAIMED"

        elif event_type == "EffectObserved":
            require(
                errors,
                snapshot["execution_state"] in {"CLAIMED", "IN_DOUBT"},
                f"{location}: effect observation requires CLAIMED or IN_DOUBT",
            )
            outcome = event.get("outcome")
            require(errors, outcome in {"COMMITTED", "FAILED"}, f"{location}: invalid effect outcome")
            if outcome in {"COMMITTED", "FAILED"}:
                snapshot["execution_state"] = outcome

        elif event_type == "RuntimeRestarted":
            if snapshot["execution_state"] == "CLAIMED":
                snapshot["execution_state"] = "IN_DOUBT"

        elif event_type == "LostStateDetected":
            require(errors, bool(event.get("reason")), f"{location}: lost-state reason is required")
            require(errors, bool(event.get("evidence_ref")), f"{location}: lost-state evidence_ref is required")
            snapshot["authority_state"] = "LOST"
            snapshot["resolution"] = resolution_from(event)

    for state_name, allowed in (
        ("authority_state", AUTHORITY_STATES),
        ("requester_state", REQUESTER_STATES),
        ("presentation_state", PRESENTATION_STATES),
        ("execution_state", EXECUTION_STATES),
    ):
        require(errors, snapshot.get(state_name) in allowed, f"{case_id}: invalid reconstructed {state_name}")

    has_user_rejected = any(
        isinstance(event, dict) and event.get("event_type") == "UserRejected" for event in events
    )
    require(
        errors,
        snapshot.get("authority_state") != "REJECTED" or has_user_rejected,
        f"{case_id}: REJECTED requires explicit UserRejected",
    )

    expected = case.get("expected_snapshot")
    require(errors, isinstance(expected, dict), f"{case_id}: expected_snapshot is required")
    if isinstance(expected, dict):
        require(errors, snapshot == expected, f"{case_id}: snapshot mismatch: expected {expected}, observed {snapshot}")

    return snapshot, errors


def validate(
    fixture: dict[str, Any],
    envelope_schema: dict[str, Any],
    event_schema: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    validate_schema_contracts(envelope_schema, event_schema, errors)

    require(
        errors,
        fixture.get("fixture_id") == "pending_approval_not_missing_authority_v0.1",
        "fixture: unexpected fixture_id",
    )
    require(
        errors,
        fixture.get("fixture_version") == "ls-durable-approval-conformance-v0.1",
        "fixture: unexpected fixture_version",
    )
    envelope = validate_envelope(fixture.get("envelope"), errors)

    cases = fixture.get("cases")
    require(errors, isinstance(cases, list) and bool(cases), "fixture: cases must be a non-empty array")
    case_ids = {
        case.get("case_id") for case in cases if isinstance(case, dict)
    } if isinstance(cases, list) else set()
    required_cases = {
        "agent_cancels_requester",
        "transport_disconnects",
        "elapsed_wait_without_expiry",
        "explicit_user_rejection",
        "restart_after_execution_claim",
    }
    require(errors, case_ids == required_cases, "fixture: required v0.1 cases must appear exactly once")

    observed: dict[str, Any] = {}
    if isinstance(cases, list):
        for case in cases:
            if not isinstance(case, dict):
                errors.append("fixture.cases: each case must be an object")
                continue
            snapshot, case_errors = reduce_case(envelope, case)
            observed[str(case.get("case_id"))] = snapshot
            errors.extend(case_errors)

    for case_id in ("agent_cancels_requester", "transport_disconnects", "elapsed_wait_without_expiry"):
        snapshot = observed.get(case_id, {})
        require(errors, snapshot.get("authority_state") == "PENDING", f"{case_id}: authority must remain PENDING")
        require(errors, snapshot.get("execution_state") == "UNUSED", f"{case_id}: execution must remain UNUSED")
    require(
        errors,
        observed.get("explicit_user_rejection", {}).get("authority_state") == "REJECTED",
        "explicit_user_rejection: must reconstruct REJECTED",
    )
    require(
        errors,
        observed.get("restart_after_execution_claim", {}).get("execution_state") == "IN_DOUBT",
        "restart_after_execution_claim: must reconstruct IN_DOUBT",
    )

    return {
        "fixture_id": fixture.get("fixture_id"),
        "fixture_version": fixture.get("fixture_version"),
        "passed": not errors,
        "errors": errors,
        "observed_snapshots": observed,
        "invariants": {
            "requester_cancellation_is_not_rejection": observed.get("agent_cancels_requester", {}).get("authority_state") == "PENDING",
            "transport_loss_is_not_rejection": observed.get("transport_disconnects", {}).get("authority_state") == "PENDING",
            "wait_timeout_without_policy_is_not_expiry": observed.get("elapsed_wait_without_expiry", {}).get("authority_state") == "PENDING",
            "only_explicit_user_rejection_rejects": observed.get("explicit_user_rejection", {}).get("authority_state") == "REJECTED",
            "claim_without_effect_is_in_doubt_after_restart": observed.get("restart_after_execution_claim", {}).get("execution_state") == "IN_DOUBT",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("envelope_schema", type=Path)
    parser.add_argument("event_schema", type=Path)
    args = parser.parse_args()

    result = validate(
        load_object(args.fixture),
        load_object(args.envelope_schema),
        load_object(args.event_schema),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
