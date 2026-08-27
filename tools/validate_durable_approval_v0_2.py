#!/usr/bin/env python3
"""Validator for LS durable approval terminal and reconciliation vectors v0.2."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

BASE_PATH = Path(__file__).with_name("validate_durable_approval_v0_1.py")
_spec = importlib.util.spec_from_file_location("durable_approval_v0_1", BASE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import base validator from {BASE_PATH}")
base = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = base
_spec.loader.exec_module(base)

EXPECTED = {
    "configured_policy_expiry": ("EXPIRED", "UNUSED"),
    "verified_context_invalidation": ("INVALIDATED", "UNUSED"),
    "durable_state_loss": ("LOST", "UNUSED"),
    "reconcile_in_doubt_committed": ("APPROVED", "COMMITTED"),
    "reconcile_in_doubt_failed": ("APPROVED", "FAILED"),
}
WIRE_CONTRACTS = {
    "ls-durable-approval-envelope-v0.1",
    "ls-approval-lifecycle-event-v0.1",
}


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be an object")
    return value


def event_of(fixture: dict[str, Any], event_type: str) -> dict[str, Any] | None:
    for event in fixture.get("events", []):
        if isinstance(event, dict) and event.get("event_type") == event_type:
            return event
    return None


def validate_fixture(
    fixture: dict[str, Any],
    envelope_schema: dict[str, Any],
    event_schema: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    base.validate_schema_contracts(envelope_schema, event_schema, errors)
    envelope = base.validate_envelope(fixture.get("envelope"), errors)

    fixture_id = fixture.get("fixture_id")
    base.require(errors, fixture_id in EXPECTED, f"fixture: unsupported fixture_id {fixture_id!r}")
    base.require(
        errors,
        fixture.get("fixture_version") == "ls-durable-approval-conformance-v0.2",
        "fixture: unexpected fixture_version",
    )
    meta = fixture.get("_meta", {})
    base.require(
        errors,
        isinstance(meta, dict)
        and meta.get("previous_fixture_version") == "ls-durable-approval-conformance-v0.1",
        "fixture: v0.1 lineage must remain explicit",
    )
    base.require(
        errors,
        isinstance(meta, dict) and set(meta.get("wire_contracts", [])) == WIRE_CONTRACTS,
        "fixture: v0.1 wire contracts must remain frozen",
    )

    case = {
        "case_id": fixture_id,
        "events": fixture.get("events"),
        "expected_snapshot": fixture.get("expected_snapshot"),
    }
    snapshot, case_errors = base.reduce_case(envelope, case)
    errors.extend(case_errors)

    if fixture_id in EXPECTED:
        expected_authority, expected_execution = EXPECTED[str(fixture_id)]
        base.require(
            errors,
            snapshot.get("authority_state") == expected_authority,
            f"{fixture_id}: expected authority {expected_authority}",
        )
        base.require(
            errors,
            snapshot.get("execution_state") == expected_execution,
            f"{fixture_id}: expected execution {expected_execution}",
        )

    if fixture_id == "configured_policy_expiry":
        expiry = envelope.get("expiry_policy") if isinstance(envelope, dict) else None
        event = event_of(fixture, "ApprovalExpired")
        base.require(errors, isinstance(expiry, dict), "configured_policy_expiry: expiry_policy is required")
        base.require(errors, event is not None, "configured_policy_expiry: ApprovalExpired is required")
        if isinstance(expiry, dict) and isinstance(event, dict):
            actor = event.get("actor", {})
            base.require(
                errors,
                isinstance(actor, dict) and actor.get("id") == expiry.get("policy_id"),
                "configured_policy_expiry: actor id must match expiry policy id",
            )
            expires_at = base.parse_timestamp(
                expiry.get("expires_at"),
                "configured_policy_expiry.envelope.expiry_policy.expires_at",
                errors,
            )
            occurred_at = base.parse_timestamp(
                event.get("occurred_at"),
                "configured_policy_expiry.ApprovalExpired.occurred_at",
                errors,
            )
            base.require(
                errors,
                expires_at is not None and occurred_at is not None and occurred_at >= expires_at,
                "configured_policy_expiry: expiry event cannot precede expires_at",
            )

    if fixture_id == "verified_context_invalidation":
        event = event_of(fixture, "ApprovalInvalidated")
        base.require(
            errors,
            isinstance(event, dict) and bool(event.get("evidence_ref")),
            "verified_context_invalidation: evidence_ref is required",
        )

    if fixture_id == "durable_state_loss":
        event = event_of(fixture, "LostStateDetected")
        base.require(
            errors,
            isinstance(event, dict) and bool(event.get("evidence_ref")),
            "durable_state_loss: evidence_ref is required",
        )
        base.require(
            errors,
            snapshot.get("authority_state") != "REJECTED",
            "durable_state_loss: LOST must never become REJECTED",
        )

    if fixture_id in {"reconcile_in_doubt_committed", "reconcile_in_doubt_failed"}:
        restart = event_of(fixture, "RuntimeRestarted")
        effect = event_of(fixture, "EffectObserved")
        base.require(errors, restart is not None, f"{fixture_id}: RuntimeRestarted is required")
        base.require(errors, effect is not None, f"{fixture_id}: EffectObserved is required")
        base.require(
            errors,
            isinstance(effect, dict) and bool(effect.get("evidence_ref")),
            f"{fixture_id}: reconciliation evidence_ref is required",
        )
        base.require(
            errors,
            snapshot.get("authority_state") == "APPROVED",
            f"{fixture_id}: reconciliation must not mint new authority",
        )

    return {
        "fixture_id": fixture_id,
        "fixture_version": fixture.get("fixture_version"),
        "passed": not errors,
        "errors": errors,
        "observed_snapshot": snapshot,
    }


def validate_suite(
    fixtures: list[dict[str, Any]],
    envelope_schema: dict[str, Any],
    event_schema: dict[str, Any],
) -> dict[str, Any]:
    results = [validate_fixture(fixture, envelope_schema, event_schema) for fixture in fixtures]
    suite_errors: list[str] = []
    ids = [result.get("fixture_id") for result in results]
    if len(ids) != len(set(ids)):
        suite_errors.append("suite: duplicate fixture_id")
    if set(ids) != set(EXPECTED):
        suite_errors.append(f"suite: expected exactly {sorted(EXPECTED)}")

    return {
        "suite_version": "ls-durable-approval-conformance-v0.2",
        "passed": not suite_errors and all(result["passed"] for result in results),
        "suite_errors": suite_errors,
        "results": results,
        "invariants": {
            "expiry_is_policy_owned": next((r["passed"] for r in results if r["fixture_id"] == "configured_policy_expiry"), False),
            "invalidation_is_evidence_backed": next((r["passed"] for r in results if r["fixture_id"] == "verified_context_invalidation"), False),
            "lost_is_explicit_not_rejection": next((r["passed"] for r in results if r["fixture_id"] == "durable_state_loss"), False),
            "in_doubt_can_reconcile_committed": next((r["passed"] for r in results if r["fixture_id"] == "reconcile_in_doubt_committed"), False),
            "in_doubt_can_reconcile_failed": next((r["passed"] for r in results if r["fixture_id"] == "reconcile_in_doubt_failed"), False),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--envelope-schema", required=True, type=Path)
    parser.add_argument("--event-schema", required=True, type=Path)
    parser.add_argument("fixtures", nargs="+", type=Path)
    args = parser.parse_args()

    result = validate_suite(
        [load_object(path) for path in args.fixtures],
        load_object(args.envelope_schema),
        load_object(args.event_schema),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
