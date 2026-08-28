#!/usr/bin/env python3
"""Dependency-free validator for inter-agent dispatch audit fixture v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

CONTRACT_VERSION = "inter-agent-dispatch-audit/v0.1"
FIXTURE_ID = "encrypted_inter_agent_dispatch_chain"
MACHINE_SURFACES = {"app_server", "hook", "audit_export"}
DISPATCH_OPERATIONS = {"spawn_agent", "send_message", "followup_task"}
FOLLOWUP_OPERATIONS = {"send_message", "followup_task"}
SHA256_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
PATH_PART = re.compile(r"^(?P<key>[^\[]+)(?:\[(?P<index>\d+)\])?$")
RFC3339_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})[Tt]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
    r"(?P<fraction>\.\d+)?(?P<zone>[Zz]|[+-]\d{2}:\d{2})$"
)
URI_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
URI_CHARACTER_PATTERN = re.compile(
    r"^[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*$"
)
INVALID_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
REQUIRED_VECTOR_CONTRACTS: dict[str, dict[str, Any]] = {
    "missing_authorized_exact_content": {
        "mutation": {"op": "delete", "path": "dispatches[0].payload.authorized_view.exact_content"},
        "expected_error_code": "AUTHORIZED_EXACT_CONTENT_MISSING",
    },
    "ui_only_without_machine_readable_audit": {
        "mutation": {"op": "set", "path": "machine_readable_audit.available", "value": False},
        "expected_error_code": "AUDIT_SURFACE_MISSING",
    },
    "missing_followup_parent_link": {
        "mutation": {"op": "delete", "path": "dispatches[1].parent_dispatch_id"},
        "expected_error_code": "PARENT_DISPATCH_MISSING",
    },
    "ambiguous_followup_order": {
        "mutation": {"op": "set", "path": "dispatches[1].sequence", "value": 1},
        "expected_error_code": "DISPATCH_SEQUENCE_INVALID",
    },
    "result_omits_effective_followup": {
        "mutation": {"op": "set", "path": "result.effective_dispatch_ids", "value": ["dispatch-root-child-001"]},
        "expected_error_code": "RESULT_DISPATCH_BINDING_INCOMPLETE",
    },
    "authorized_content_changed_without_digest_update": {
        "mutation": {"op": "set", "path": "dispatches[1].payload.authorized_view.exact_content", "value": "FOLLOWUP_AUDIT_SENTINEL_MUTATED."},
        "expected_error_code": "CONTENT_DIGEST_MISMATCH",
    },
    "missing_root_parent_key": {
        "mutation": {"op": "delete", "path": "dispatches[0].parent_dispatch_id"},
        "expected_error_code": "ROOT_PARENT_MISSING",
    },
    "self_parent_followup": {
        "mutation": {"op": "set", "path": "dispatches[1].parent_dispatch_id", "value": "dispatch-root-child-002"},
        "expected_error_code": "PARENT_DISPATCH_MISSING",
    },
    "invalid_root_operation": {
        "mutation": {"op": "set", "path": "dispatches[0].operation", "value": "followup_task"},
        "expected_error_code": "ROOT_OPERATION_INVALID",
    },
    "invalid_dispatch_timestamp": {
        "mutation": {"op": "set", "path": "dispatches[1].timestamp", "value": "not-a-timeZ"},
        "expected_error_code": "TIMESTAMP_INVALID",
    },
    "invalid_leap_second_timestamp": {
        "mutation": {"op": "set", "path": "dispatches[1].timestamp", "value": "2026-07-13T10:00:60Z"},
        "expected_error_code": "TIMESTAMP_INVALID",
    },
    "malformed_result_digest": {
        "mutation": {"op": "set", "path": "result.output_digest", "value": "sha256:bogus"},
        "expected_error_code": "RESULT_DIGEST_INVALID",
    },
    "missing_required_result_id": {
        "mutation": {"op": "delete", "path": "result.result_id"},
        "expected_error_code": "SCHEMA_VALIDATION_FAILED",
    },
    "malformed_content_digest": {
        "mutation": {"op": "set", "path": "dispatches[0].payload.content_digest", "value": "sha256:bogus"},
        "expected_error_code": "CONTENT_DIGEST_INVALID",
    },
}
RFC3339_CONTRACT_CASES = {
    "2026-07-13T10:00:00Z": True,
    "2026-07-13t10:00:00z": True,
    "2026-07-13T10:00:00.123456789Z": True,
    "2026-07-13T10:00:00+00:00": True,
    "2026-07-13T13:00:00+03:00": True,
    "2026-07-13T10:00:60Z": False,
    "2016-12-31T23:59:60Z": False,
    "2026-W29-1T10:00:00Z": False,
    "20260713T100000Z": False,
    "not-a-timeZ": False,
}
UTC_CONTRACT_CASES = {
    "2026-07-13T10:00:00Z": True,
    "2026-07-13t10:00:00z": True,
    "2026-07-13T10:00:00+00:00": True,
    "2026-07-13T13:00:00+03:00": False,
    "2026-07-13T10:00:00-00:00": False,
    "2026-07-13T10:00:60Z": False,
    "2016-12-31T23:59:60Z": False,
    "2026-W29-1T10:00:00Z": False,
    "20260713T100000Z": False,
}


def load_object(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object from *path*."""
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be an object")
    return value


def error(errors: list[dict[str, str]], code: str, location: str, message: str) -> None:
    """Append one normalized validation error."""
    errors.append({"code": code, "location": location, "message": message})


def sha256_text(value: str) -> str:
    """Return the canonical prefixed SHA-256 digest for UTF-8 text."""
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def match_rfc3339(value: Any) -> re.Match[str] | None:
    """Return a strict RFC3339-profile match after calendar and offset checks.

    The dependency-free v0.1 profile rejects all leap-second ``:60`` forms
    because it has no maintained trusted leap-second table with which to
    distinguish real insertions from malformed timestamps.
    """
    if not isinstance(value, str):
        return None
    match = RFC3339_PATTERN.fullmatch(value)
    if match is None:
        return None

    parts = {name: int(match.group(name)) for name in (
        "year", "month", "day", "hour", "minute", "second"
    )}
    if parts["hour"] > 23 or parts["minute"] > 59 or parts["second"] > 59:
        return None
    try:
        datetime(parts["year"], parts["month"], parts["day"])
    except ValueError:
        return None

    zone = match.group("zone")
    if zone not in {"Z", "z"}:
        offset_hour = int(zone[1:3])
        offset_minute = int(zone[4:6])
        if offset_hour > 23 or offset_minute > 59:
            return None
    return match


def is_rfc3339_datetime(value: Any) -> bool:
    """Return whether *value* conforms to the dependency-free v0.1 profile."""
    return match_rfc3339(value) is not None


def is_rfc3986_uri(value: Any) -> bool:
    """Validate an absolute ASCII URI without assuming a URL authority.

    RFC 3986 permits opaque absolute forms such as ``urn:`` and ``mailto:``.
    This dependency-free check also rejects raw illegal characters, malformed
    percent escapes, invalid bracketed authorities, and invalid ports.
    """
    if (
        not isinstance(value, str)
        or not value.isascii()
        or URI_SCHEME_PATTERN.match(value) is None
        or URI_CHARACTER_PATTERN.fullmatch(value) is None
        or INVALID_PERCENT_ESCAPE.search(value) is not None
        or value.count("#") > 1
    ):
        return False

    try:
        parsed = urlparse(value)
        parsed.port
    except ValueError:
        return False

    remainder = value.split(":", 1)[1]
    if remainder.startswith("//"):
        authority_and_rest = remainder[2:]
        boundary = min(
            (
                index
                for marker in "/?#"
                if (index := authority_and_rest.find(marker)) >= 0
            ),
            default=len(authority_and_rest),
        )
        authority = authority_and_rest[:boundary]
        trailing = authority_and_rest[boundary:]
        if authority.count("@") > 1 or "[" in trailing or "]" in trailing:
            return False
    elif "[" in remainder or "]" in remainder:
        return False
    return bool(parsed.scheme)


def is_utc_timestamp(value: Any) -> bool:
    """Return whether *value* is an RFC3339-profile timestamp with known UTC."""
    match = match_rfc3339(value)
    return match is not None and match.group("zone") in {"Z", "z", "+00:00"}


def validate_timestamp_helpers(errors: list[dict[str, str]]) -> None:
    """Fail closed if timestamp helper semantics drift from their contract."""
    for sample, expected in RFC3339_CONTRACT_CASES.items():
        observed = is_rfc3339_datetime(sample)
        if observed is not expected:
            error(
                errors,
                "RFC3339_VALIDATOR_CONTRACT_BROKEN",
                "validator.is_rfc3339_datetime",
                f"sample {sample!r}: expected {expected}, observed {observed}",
            )
    for sample, expected in UTC_CONTRACT_CASES.items():
        observed = is_utc_timestamp(sample)
        if observed is not expected:
            error(
                errors,
                "UTC_TIMESTAMP_VALIDATOR_CONTRACT_BROKEN",
                "validator.is_utc_timestamp",
                f"sample {sample!r}: expected {expected}, observed {observed}",
            )


def required_vector_objects() -> list[dict[str, Any]]:
    """Return canonical full vector objects for the trusted v0.1 contract."""
    return [
        {
            "case": case,
            "mutation": copy.deepcopy(contract["mutation"]),
            "expected_error_code": contract["expected_error_code"],
        }
        for case, contract in REQUIRED_VECTOR_CONTRACTS.items()
    ]


def validate_required_schema_contracts(
    schema: dict[str, Any],
    errors: list[dict[str, str]],
) -> None:
    """Require the input schema to preserve the exact trusted vector set."""
    negative = schema.get("properties", {}).get("negative_vectors", {})
    expected_count = len(REQUIRED_VECTOR_CONTRACTS)
    for bound in ("minItems", "maxItems"):
        if negative.get(bound) != expected_count:
            error(
                errors,
                "SCHEMA_VECTOR_COUNT_INVALID",
                f"schema.properties.negative_vectors.{bound}",
                f"expected exactly {expected_count} required vectors",
            )

    actual: list[dict[str, Any]] = []
    all_of = negative.get("allOf")
    if isinstance(all_of, list):
        for entry in all_of:
            if not isinstance(entry, dict):
                continue
            contains = entry.get("contains")
            if isinstance(contains, dict) and isinstance(contains.get("const"), dict):
                actual.append(contains["const"])

    def canonical(value: Any) -> str:
        """Serialize a JSON value deterministically for contract comparison."""
        return json.dumps(value, sort_keys=True, separators=(",", ":"))

    observed = sorted(canonical(item) for item in actual)
    expected = sorted(canonical(item) for item in required_vector_objects())
    if observed != expected:
        error(
            errors,
            "SCHEMA_VECTOR_CONTRACT_SET_INVALID",
            "schema.properties.negative_vectors.allOf",
            "schema must preserve the exact fourteen case/mutation/error contracts",
        )


def resolve_schema_ref(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    """Resolve a local JSON Pointer reference within the root schema."""
    if not reference.startswith("#/"):
        raise ValueError(f"only local schema references are supported: {reference}")
    current: Any = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise KeyError(reference)
        current = current[part]
    if not isinstance(current, dict):
        raise ValueError(f"schema reference does not resolve to an object: {reference}")
    return current


def instance_matches_type(instance: Any, expected: str) -> bool:
    """Check one JSON Schema primitive type without bool/int ambiguity."""
    checks = {
        "object": lambda: isinstance(instance, dict),
        "array": lambda: isinstance(instance, list),
        "string": lambda: isinstance(instance, str),
        "integer": lambda: isinstance(instance, int) and not isinstance(instance, bool),
        "number": lambda: isinstance(instance, (int, float)) and not isinstance(instance, bool),
        "boolean": lambda: isinstance(instance, bool),
        "null": lambda: instance is None,
    }
    check = checks.get(expected)
    return check() if check else False


def json_schema_equal(left: Any, right: Any) -> bool:
    """Compare JSON values using Draft 2020-12 equality semantics."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if (
        isinstance(left, (int, float))
        and not isinstance(left, bool)
        and isinstance(right, (int, float))
        and not isinstance(right, bool)
    ):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            json_schema_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            json_schema_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right

def validate_schema_instance(
    instance: Any,
    schema: dict[str, Any],
    root_schema: dict[str, Any],
    path: str = "$",
) -> list[str]:
    """Validate the schema keyword subset used by the checked-in v0.1 schema."""
    issues: list[str] = []

    reference = schema.get("$ref")
    if isinstance(reference, str):
        try:
            referenced = resolve_schema_ref(root_schema, reference)
        except (KeyError, ValueError) as exc:
            return [f"{path}: invalid schema reference {reference!r}: {exc}"]
        issues.extend(validate_schema_instance(instance, referenced, root_schema, path))

    all_of = schema.get("allOf", [])
    if isinstance(all_of, list):
        for sub_schema in all_of:
            if isinstance(sub_schema, dict):
                issues.extend(validate_schema_instance(instance, sub_schema, root_schema, path))

    if "const" in schema and not json_schema_equal(instance, schema["const"]):
        issues.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and not any(
        json_schema_equal(instance, candidate) for candidate in schema["enum"]
    ):
        issues.append(f"{path}: value is not in the allowed enum")

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        type_valid = instance_matches_type(instance, expected_type)
    elif isinstance(expected_type, list):
        type_valid = any(
            isinstance(candidate, str) and instance_matches_type(instance, candidate)
            for candidate in expected_type
        )
    else:
        type_valid = True
    if not type_valid:
        issues.append(f"{path}: type mismatch, expected {expected_type!r}")
        return issues

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in instance:
                    issues.append(f"{path}.{key}: required property is missing")

        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in instance and isinstance(child_schema, dict):
                    issues.extend(validate_schema_instance(
                        instance[key], child_schema, root_schema, f"{path}.{key}"
                    ))
            if schema.get("additionalProperties") is False:
                for key in instance:
                    if key not in properties:
                        issues.append(f"{path}.{key}: additional property is not allowed")

    if isinstance(instance, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(instance) < minimum:
            issues.append(f"{path}: expected at least {minimum} items")
        if isinstance(maximum, int) and len(instance) > maximum:
            issues.append(f"{path}: expected at most {maximum} items")

        prefix_items = schema.get("prefixItems", [])
        prefix_count = len(prefix_items) if isinstance(prefix_items, list) else 0
        if isinstance(prefix_items, list):
            for index, child_schema in enumerate(prefix_items):
                if index < len(instance) and isinstance(child_schema, dict):
                    issues.extend(validate_schema_instance(
                        instance[index], child_schema, root_schema, f"{path}[{index}]"
                    ))

        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index in range(prefix_count, len(instance)):
                issues.extend(validate_schema_instance(
                    instance[index], item_schema, root_schema, f"{path}[{index}]"
                ))
        elif item_schema is False and len(instance) > prefix_count:
            issues.append(f"{path}: additional array items are not allowed")

        contains = schema.get("contains")
        if isinstance(contains, dict) and not any(
            not validate_schema_instance(item, contains, root_schema, f"{path}[{index}]")
            for index, item in enumerate(instance)
        ):
            issues.append(f"{path}: no item satisfies contains")

    if isinstance(instance, str):
        minimum_length = schema.get("minLength")
        if isinstance(minimum_length, int) and len(instance) < minimum_length:
            issues.append(f"{path}: string is shorter than {minimum_length}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            issues.append(f"{path}: string does not match {pattern!r}")
        format_name = schema.get("format")
        if format_name == "date-time" and not is_rfc3339_datetime(instance):
            issues.append(f"{path}: invalid RFC3339 date-time for v0.1 profile")
        if format_name == "uri":
            if not is_rfc3986_uri(instance):
                issues.append(f"{path}: invalid absolute URI")

    if isinstance(instance, int) and not isinstance(instance, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)) and instance < minimum:
            issues.append(f"{path}: number is below minimum {minimum}")

    return issues


def validate_record(record: Any) -> list[dict[str, str]]:
    """Validate semantic and causal invariants for one canonical audit record."""
    errors: list[dict[str, str]] = []
    if not isinstance(record, dict):
        error(errors, "RECORD_INVALID", "canonical_record", "record must be an object")
        return errors

    security = record.get("security")
    if not isinstance(security, dict):
        error(errors, "SECURITY_INVALID", "security", "security must be an object")
    else:
        if security.get("rollout_storage") != "encrypted":
            error(errors, "SECURITY_STORAGE_NOT_ENCRYPTED", "security.rollout_storage", "rollout storage must remain encrypted")
        if security.get("operator_access") != "authorized":
            error(errors, "OPERATOR_ACCESS_INVALID", "security.operator_access", "operator access must be explicitly authorized")
        if security.get("default_transcript_visibility") != "redacted":
            error(errors, "DEFAULT_VISIBILITY_INVALID", "security.default_transcript_visibility", "default transcript visibility must remain redacted")

    audit = record.get("machine_readable_audit")
    if not isinstance(audit, dict):
        error(errors, "AUDIT_SURFACE_MISSING", "machine_readable_audit", "machine-readable audit surface is required")
    elif audit.get("available") is not True or audit.get("surface") not in MACHINE_SURFACES or audit.get("format") != "json":
        error(errors, "AUDIT_SURFACE_MISSING", "machine_readable_audit", "an available machine-readable JSON audit surface is required")

    dispatches = record.get("dispatches")
    if not isinstance(dispatches, list) or not dispatches:
        error(errors, "DISPATCHES_MISSING", "dispatches", "at least one dispatch is required")
        return errors

    ids: list[str] = []
    seen_ids: set[str] = set()
    expected_sequence = 1
    root_sender: str | None = None
    root_recipient: str | None = None

    for index, dispatch in enumerate(dispatches):
        location = f"dispatches[{index}]"
        if not isinstance(dispatch, dict):
            error(errors, "DISPATCH_INVALID", location, "dispatch must be an object")
            continue

        dispatch_id = dispatch.get("dispatch_id")
        valid_unique_id = isinstance(dispatch_id, str) and bool(dispatch_id) and dispatch_id not in seen_ids
        if not isinstance(dispatch_id, str) or not dispatch_id:
            error(errors, "DISPATCH_ID_MISSING", f"{location}.dispatch_id", "dispatch_id is required")
        elif dispatch_id in seen_ids:
            error(errors, "DISPATCH_ID_DUPLICATE", f"{location}.dispatch_id", "dispatch_id must be unique")
        else:
            ids.append(dispatch_id)

        operation = dispatch.get("operation")
        if operation not in DISPATCH_OPERATIONS:
            error(errors, "DISPATCH_OPERATION_INVALID", f"{location}.operation", "unsupported dispatch operation")
        if index == 0 and operation != "spawn_agent":
            error(errors, "ROOT_OPERATION_INVALID", f"{location}.operation", "initial dispatch must use spawn_agent")
        if index > 0 and operation not in FOLLOWUP_OPERATIONS:
            error(errors, "FOLLOWUP_OPERATION_INVALID", f"{location}.operation", "non-root dispatch must be send_message or followup_task")

        sequence = dispatch.get("sequence")
        if sequence != expected_sequence:
            error(errors, "DISPATCH_SEQUENCE_INVALID", f"{location}.sequence", f"expected sequence {expected_sequence}")
        expected_sequence += 1

        sender = dispatch.get("sender_thread_id")
        recipient = dispatch.get("recipient_thread_id")
        if not isinstance(sender, str) or not sender:
            error(errors, "SENDER_MISSING", f"{location}.sender_thread_id", "sender_thread_id is required")
        if not isinstance(recipient, str) or not recipient:
            error(errors, "RECIPIENT_MISSING", f"{location}.recipient_thread_id", "recipient_thread_id is required")

        if index == 0:
            root_sender, root_recipient = sender, recipient
            if "parent_dispatch_id" not in dispatch:
                error(errors, "ROOT_PARENT_MISSING", f"{location}.parent_dispatch_id", "initial dispatch must explicitly declare a null parent")
            elif dispatch["parent_dispatch_id"] is not None:
                error(errors, "ROOT_PARENT_INVALID", f"{location}.parent_dispatch_id", "initial dispatch must not have a parent")
        else:
            parent_id = dispatch.get("parent_dispatch_id")
            if not isinstance(parent_id, str) or parent_id not in seen_ids:
                error(errors, "PARENT_DISPATCH_MISSING", f"{location}.parent_dispatch_id", "follow-up must reference an earlier dispatch")
            if sender != root_sender or recipient != root_recipient:
                error(errors, "DISPATCH_PARTICIPANT_DRIFT", location, "sender and recipient must remain stable within the fixture chain")

        if not is_utc_timestamp(dispatch.get("timestamp")):
            error(errors, "TIMESTAMP_INVALID", f"{location}.timestamp", "valid RFC3339-profile UTC timestamp is required")

        payload = dispatch.get("payload")
        if not isinstance(payload, dict):
            error(errors, "PAYLOAD_INVALID", f"{location}.payload", "payload must be an object")
        else:
            if payload.get("storage_mode") != "encrypted":
                error(errors, "PAYLOAD_STORAGE_NOT_ENCRYPTED", f"{location}.payload.storage_mode", "payload storage must remain encrypted")

            authorized = payload.get("authorized_view")
            exact_content: Any = None
            if not isinstance(authorized, dict) or authorized.get("access") != "granted":
                error(errors, "AUTHORIZED_VIEW_MISSING", f"{location}.payload.authorized_view", "authorized view with granted access is required")
            else:
                exact_content = authorized.get("exact_content")
                if not isinstance(exact_content, str) or not exact_content:
                    error(errors, "AUTHORIZED_EXACT_CONTENT_MISSING", f"{location}.payload.authorized_view.exact_content", "exact mechanically dispatched content is required")

            digest = payload.get("content_digest")
            if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
                error(errors, "CONTENT_DIGEST_INVALID", f"{location}.payload.content_digest", "64-hex SHA-256 content digest is required")
            elif isinstance(exact_content, str) and exact_content and digest != sha256_text(exact_content):
                error(errors, "CONTENT_DIGEST_MISMATCH", f"{location}.payload.content_digest", "digest must bind the authorized exact content")

        if valid_unique_id:
            seen_ids.add(dispatch_id)

    result = record.get("result")
    if not isinstance(result, dict):
        error(errors, "RESULT_MISSING", "result", "result is required")
        return errors

    if result.get("actor_thread_id") != root_recipient:
        error(errors, "RESULT_ACTOR_INVALID", "result.actor_thread_id", "result actor must be the recipient subagent")
    if result.get("status") != "completed":
        error(errors, "RESULT_STATUS_INVALID", "result.status", "fixture result must be completed")
    effective = result.get("effective_dispatch_ids")
    if effective != ids:
        error(errors, "RESULT_DISPATCH_BINDING_INCOMPLETE", "result.effective_dispatch_ids", "result must bind the complete ordered dispatch sequence")
    output_digest = result.get("output_digest")
    if not isinstance(output_digest, str) or SHA256_PATTERN.fullmatch(output_digest) is None:
        error(errors, "RESULT_DIGEST_INVALID", "result.output_digest", "64-hex SHA-256 result digest is required")
    if not is_utc_timestamp(result.get("timestamp")):
        error(errors, "RESULT_TIMESTAMP_INVALID", "result.timestamp", "valid RFC3339-profile UTC result timestamp is required")

    return errors


def resolve_parent(root: dict[str, Any], path: str) -> tuple[Any, str | int]:
    """Resolve the parent container and final key for a supported mutation path."""
    current: Any = root
    parts = path.split(".")
    for offset, raw in enumerate(parts):
        match = PATH_PART.match(raw)
        if not match:
            raise ValueError(f"unsupported mutation path segment: {raw}")
        key = match.group("key")
        index_text = match.group("index")
        is_last = offset == len(parts) - 1
        if not isinstance(current, dict) or key not in current:
            raise KeyError(path)
        value = current[key]
        if index_text is not None:
            index = int(index_text)
            if not isinstance(value, list) or index >= len(value):
                raise KeyError(path)
            if is_last:
                return value, index
            current = value[index]
        else:
            if is_last:
                return current, key
            current = value
    raise KeyError(path)


def apply_mutation(record: dict[str, Any], mutation: dict[str, Any]) -> dict[str, Any]:
    """Return a deep-copied record after applying one declared mutation."""
    mutated = copy.deepcopy(record)
    op = mutation.get("op")
    path = mutation.get("path")
    if op not in {"set", "delete"} or not isinstance(path, str):
        raise ValueError("mutation requires op=set|delete and a path")
    parent, key = resolve_parent(mutated, path)
    if op == "delete":
        del parent[key]
    else:
        parent[key] = copy.deepcopy(mutation.get("value"))
    return mutated


def schema_errors_as_records(issues: list[str]) -> list[dict[str, str]]:
    """Convert schema issue strings into normalized validator errors."""
    return [{
        "code": "SCHEMA_VALIDATION_FAILED",
        "location": issue.split(":", 1)[0],
        "message": issue,
    } for issue in issues]


def validate_fixture(fixture: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Validate the fixture, its schema contract, and all negative mutations."""
    fixture_errors: list[dict[str, str]] = []
    validate_timestamp_helpers(fixture_errors)

    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        error(fixture_errors, "SCHEMA_DRAFT_INVALID", "schema.$schema", "Draft 2020-12 is required")
    properties = schema.get("properties", {})
    if properties.get("fixture_id", {}).get("const") != FIXTURE_ID:
        error(fixture_errors, "SCHEMA_FIXTURE_ID_INVALID", "schema.properties.fixture_id", "unexpected fixture id const")
    if properties.get("contract_version", {}).get("const") != CONTRACT_VERSION:
        error(fixture_errors, "SCHEMA_VERSION_INVALID", "schema.properties.contract_version", "unexpected contract version const")
    validate_required_schema_contracts(schema, fixture_errors)

    fixture_errors.extend(schema_errors_as_records(validate_schema_instance(fixture, schema, schema)))
    if fixture.get("fixture_id") != FIXTURE_ID:
        error(fixture_errors, "FIXTURE_ID_INVALID", "fixture_id", "unexpected fixture id")
    if fixture.get("contract_version") != CONTRACT_VERSION:
        error(fixture_errors, "CONTRACT_VERSION_INVALID", "contract_version", "unexpected contract version")

    canonical = fixture.get("canonical_record")
    canonical_errors = validate_record(canonical)
    canonical_schema = schema.get("$defs", {}).get("auditRecord")
    if isinstance(canonical_schema, dict):
        canonical_errors.extend(schema_errors_as_records(
            validate_schema_instance(
                canonical,
                canonical_schema,
                schema,
                "canonical_record",
            )
        ))
    vector_results: list[dict[str, Any]] = []
    negative_vectors = fixture.get("negative_vectors")
    seen_cases: set[str] = set()

    if not isinstance(negative_vectors, list) or not negative_vectors:
        error(fixture_errors, "NEGATIVE_VECTORS_MISSING", "negative_vectors", "negative vectors are required")
    else:
        for index, vector in enumerate(negative_vectors):
            location = f"negative_vectors[{index}]"
            if not isinstance(vector, dict):
                error(fixture_errors, "NEGATIVE_VECTOR_INVALID", location, "negative vector must be an object")
                continue
            case = vector.get("case")
            expected_code = vector.get("expected_error_code")
            if not isinstance(case, str) or not case or case in seen_cases:
                error(fixture_errors, "NEGATIVE_CASE_INVALID", f"{location}.case", "case must be unique and non-empty")
                continue
            seen_cases.add(case)
            if not isinstance(expected_code, str) or not expected_code:
                error(fixture_errors, "EXPECTED_ERROR_CODE_MISSING", f"{location}.expected_error_code", "expected error code is required")
                continue
            required_contract = REQUIRED_VECTOR_CONTRACTS.get(case)
            if required_contract is not None:
                if json.dumps(vector.get("mutation"), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) != json.dumps(required_contract["mutation"], sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False):
                    error(
                        fixture_errors,
                        "REQUIRED_MUTATION_INVALID",
                        f"{location}.mutation",
                        f"required case {case} must use its exact mutation contract",
                    )
                    continue
                required_code = required_contract["expected_error_code"]
                if expected_code != required_code:
                    error(
                        fixture_errors,
                        "EXPECTED_ERROR_CODE_INVALID",
                        f"{location}.expected_error_code",
                        f"required case {case} must expect {required_code}",
                    )
                    continue
            try:
                mutated = apply_mutation(canonical, vector.get("mutation", {}))
                observed_errors = validate_record(mutated)
                mutated_fixture = copy.deepcopy(fixture)
                mutated_fixture["canonical_record"] = mutated
                observed_errors.extend(schema_errors_as_records(
                    validate_schema_instance(mutated_fixture, schema, schema)
                ))
            except (KeyError, ValueError, TypeError) as exc:
                error(fixture_errors, "MUTATION_INVALID", f"{location}.mutation", str(exc))
                continue
            observed_codes = sorted({item["code"] for item in observed_errors})
            rejected = expected_code in observed_codes
            vector_results.append({
                "case": case,
                "expected_error_code": expected_code,
                "observed_error_codes": observed_codes,
                "rejected": rejected,
            })
            if not rejected:
                error(fixture_errors, "NEGATIVE_VECTOR_NOT_REJECTED", location, f"expected {expected_code}, observed {observed_codes}")

    missing_cases = sorted(REQUIRED_VECTOR_CONTRACTS.keys() - seen_cases)
    if missing_cases:
        error(
            fixture_errors,
            "REQUIRED_NEGATIVE_CASES_MISSING",
            "negative_vectors",
            f"missing required v0.1 cases: {missing_cases}",
        )

    unexpected_cases = sorted(seen_cases - REQUIRED_VECTOR_CONTRACTS.keys())
    if unexpected_cases:
        error(
            fixture_errors,
            "UNEXPECTED_NEGATIVE_CASES",
            "negative_vectors",
            f"unexpected v0.1 cases: {unexpected_cases}",
        )

    expected = fixture.get("expected", {})
    if not isinstance(expected, dict) or expected.get("canonical_passes") is not True or expected.get("negative_vectors_rejected") is not True:
        error(fixture_errors, "EXPECTED_OUTCOME_INVALID", "expected", "expected outcomes must require canonical pass and negative rejection")

    passed = (
        not fixture_errors
        and not canonical_errors
        and len(vector_results) == len(REQUIRED_VECTOR_CONTRACTS)
        and all(item["rejected"] for item in vector_results)
    )
    return {
        "fixture_id": fixture.get("fixture_id"),
        "contract_version": fixture.get("contract_version"),
        "passed": passed,
        "fixture_errors": fixture_errors,
        "canonical": {"passed": not canonical_errors, "errors": canonical_errors},
        "negative_vectors": vector_results,
    }


def input_failure_report(exc: Exception) -> dict[str, Any]:
    """Build deterministic structured output for CLI input failures."""
    return {
        "fixture_id": None,
        "contract_version": CONTRACT_VERSION,
        "passed": False,
        "fixture_errors": [
  {
      "code": "INPUT_LOAD_FAILED",
      "location": "cli",
      "message": str(exc),
  }
        ],
        "canonical": {"passed": False, "errors": []},
        "negative_vectors": [],
    }


def main() -> int:
    """Run CLI validation and return a process-compatible status code."""
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("schema", type=Path)
    args = parser.parse_args()

    try:
        fixture = load_object(args.fixture)
        schema = load_object(args.schema)
        result = validate_fixture(fixture, schema)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        result = input_failure_report(exc)

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
