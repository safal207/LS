#!/usr/bin/env python3
"""Fail-closed schema-parity wrapper for durable approval conformance v0.1."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

LEGACY_PATH = Path(__file__).with_name("validate_durable_approval_v0_1_legacy.py")
_spec = importlib.util.spec_from_file_location("durable_approval_v0_1_legacy", LEGACY_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import legacy validator from {LEGACY_PATH}")
legacy = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = legacy
_spec.loader.exec_module(legacy)

AUTHORITY_STATES = legacy.AUTHORITY_STATES
REQUESTER_STATES = legacy.REQUESTER_STATES
PRESENTATION_STATES = legacy.PRESENTATION_STATES
EXECUTION_STATES = legacy.EXECUTION_STATES
BOUND_DIGEST_FIELDS = legacy.BOUND_DIGEST_FIELDS
DIGEST_FIELDS = legacy.DIGEST_FIELDS
DIGEST_PATTERN = legacy.DIGEST_PATTERN
REQUIRED_ENVELOPE_FIELDS = legacy.REQUIRED_ENVELOPE_FIELDS
REQUIRED_EVENT_FIELDS = legacy.REQUIRED_EVENT_FIELDS
EVENT_OWNERS = legacy.EVENT_OWNERS
REASON_REQUIRED_EVENTS = legacy.REASON_REQUIRED_EVENTS
EVIDENCE_REQUIRED_EVENTS = legacy.EVIDENCE_REQUIRED_EVENTS

ALLOWED_ENVELOPE_FIELDS = set(REQUIRED_ENVELOPE_FIELDS)
ALLOWED_EXPIRY_POLICY_FIELDS = {"policy_id", "expires_at"}
ALLOWED_EVENT_FIELDS = REQUIRED_EVENT_FIELDS | {
    "reason",
    "evidence_ref",
    "bindings",
    "outcome",
}
ALLOWED_ACTOR_FIELDS = {"type", "id"}
ALLOWED_BINDING_FIELDS = set(BOUND_DIGEST_FIELDS)
RFC3339_LOCAL_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?$"
)
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?"
    r"(?:[Zz]|[+-]\d{2}:\d{2})$"
)

load_object = legacy.load_object
require = legacy.require
validate_schema_contracts = legacy.validate_schema_contracts
_conditional_event_types = legacy._conditional_event_types


def reject_unknown_properties(
    value: Any,
    allowed: set[str],
    location: str,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        return
    unknown = set(value) - allowed
    require(
        errors,
        not unknown,
        f"{location}: unexpected properties {sorted(unknown)}",
    )


def parse_timestamp(
    value: Any,
    location: str,
    errors: list[str],
) -> datetime | None:
    if not isinstance(value, str):
        errors.append(f"{location}: timestamp must be a string")
        return None
    if RFC3339_LOCAL_PATTERN.fullmatch(value) is not None:
        errors.append(f"{location}: timestamp must include timezone offset")
        return None
    if RFC3339_PATTERN.fullmatch(value) is None:
        errors.append(f"{location}: invalid RFC 3339 timestamp {value!r}")
        return None
    normalized = value[:-1] + "+00:00" if value[-1] in {"Z", "z"} else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        errors.append(f"{location}: invalid RFC 3339 timestamp {value!r}")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{location}: timestamp must include timezone offset")
        return None
    return parsed


def _strict_validate_envelope(envelope: Any, errors: list[str]) -> None:
    if not isinstance(envelope, dict):
        return
    reject_unknown_properties(
        envelope,
        ALLOWED_ENVELOPE_FIELDS,
        "fixture.envelope",
        errors,
    )
    parse_timestamp(
        envelope.get("created_at"),
        "fixture.envelope.created_at",
        errors,
    )
    expiry = envelope.get("expiry_policy")
    if isinstance(expiry, dict):
        reject_unknown_properties(
            expiry,
            ALLOWED_EXPIRY_POLICY_FIELDS,
            "fixture.envelope.expiry_policy",
            errors,
        )
        require(
            errors,
            isinstance(expiry.get("policy_id"), str)
            and bool(expiry.get("policy_id")),
            "fixture.envelope.expiry_policy.policy_id is required",
        )
        parse_timestamp(
            expiry.get("expires_at"),
            "fixture.envelope.expiry_policy.expires_at",
            errors,
        )


def validate_envelope(envelope: Any, errors: list[str]) -> dict[str, Any]:
    _strict_validate_envelope(envelope, errors)
    return legacy.validate_envelope(envelope, errors)


def _strict_sanitize_case(
    case: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    safe = copy.deepcopy(case)
    errors: list[str] = []
    case_id = str(case.get("case_id"))
    events = safe.get("events")
    if not isinstance(events, list):
        return safe, errors

    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        location = f"{case_id}.events[{index}]"
        reject_unknown_properties(event, ALLOWED_EVENT_FIELDS, location, errors)

        event_id = event.get("event_id")
        if not isinstance(event_id, str):
            errors.append(f"{location}: event_id must be a string")
            event["event_id"] = ""

        sequence = event.get("sequence")
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            errors.append(f"{location}: sequence must be an integer")
            event["sequence"] = 0

        event_type = event.get("event_type")
        if not isinstance(event_type, str):
            errors.append(f"{location}: event_type must be a string")
            event["event_type"] = ""

        parse_timestamp(
            event.get("occurred_at"),
            f"{location}.occurred_at",
            errors,
        )

        actor = event.get("actor")
        if isinstance(actor, dict):
            reject_unknown_properties(
                actor,
                ALLOWED_ACTOR_FIELDS,
                f"{location}.actor",
                errors,
            )
            if not isinstance(actor.get("type"), str):
                errors.append(f"{location}.actor.type must be a string")
                actor["type"] = ""
            if not isinstance(actor.get("id"), str):
                errors.append(f"{location}.actor.id must be a string")
                actor["id"] = ""

        bindings = event.get("bindings")
        if isinstance(bindings, dict):
            reject_unknown_properties(
                bindings,
                ALLOWED_BINDING_FIELDS,
                f"{location}.bindings",
                errors,
            )

        if "outcome" in event and not isinstance(event.get("outcome"), str):
            errors.append(f"{location}.outcome must be a string")
            event["outcome"] = ""

    return safe, errors


def resolution_from(event: dict[str, Any]) -> dict[str, Any]:
    actor_value = event.get("actor")
    actor = actor_value if isinstance(actor_value, dict) else {}
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
    safe_case, strict_errors = _strict_sanitize_case(case)
    snapshot, legacy_errors = legacy.reduce_case(envelope, safe_case)
    return snapshot, [*strict_errors, *legacy_errors]


def validate(
    fixture: dict[str, Any],
    envelope_schema: dict[str, Any],
    event_schema: dict[str, Any],
) -> dict[str, Any]:
    safe_fixture = copy.deepcopy(fixture)
    strict_errors: list[str] = []
    _strict_validate_envelope(safe_fixture.get("envelope"), strict_errors)

    cases = safe_fixture.get("cases")
    if isinstance(cases, list):
        safe_cases = []
        for case in cases:
            if isinstance(case, dict):
                safe_case, case_errors = _strict_sanitize_case(case)
                safe_cases.append(safe_case)
                strict_errors.extend(case_errors)
            else:
                safe_cases.append(case)
        safe_fixture["cases"] = safe_cases

    result = legacy.validate(safe_fixture, envelope_schema, event_schema)
    errors = [*strict_errors, *result["errors"]]
    return {**result, "passed": not errors, "errors": errors}


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
