#!/usr/bin/env python3
"""Dependency-free validator for inter-agent dispatch audit fixture v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "inter-agent-dispatch-audit/v0.1"
FIXTURE_ID = "encrypted_inter_agent_dispatch_chain"
MACHINE_SURFACES = {"app_server", "hook", "audit_export"}
DISPATCH_OPERATIONS = {"spawn_agent", "send_message", "followup_task"}
PATH_PART = re.compile(r"^(?P<key>[^\[]+)(?:\[(?P<index>\d+)\])?$")


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be an object")
    return value


def error(errors: list[dict[str, str]], code: str, location: str, message: str) -> None:
    errors.append({"code": code, "location": location, "message": message})


def sha256_text(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_record(record: Any) -> list[dict[str, str]]:
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
    else:
        if audit.get("available") is not True or audit.get("surface") not in MACHINE_SURFACES or audit.get("format") != "json":
            error(errors, "AUDIT_SURFACE_MISSING", "machine_readable_audit", "an available machine-readable JSON audit surface is required")

    dispatches = record.get("dispatches")
    if not isinstance(dispatches, list) or not dispatches:
        error(errors, "DISPATCHES_MISSING", "dispatches", "at least one dispatch is required")
        return errors

    ids: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    expected_sequence = 1
    root_sender: str | None = None
    root_recipient: str | None = None

    for index, dispatch in enumerate(dispatches):
        location = f"dispatches[{index}]"
        if not isinstance(dispatch, dict):
            error(errors, "DISPATCH_INVALID", location, "dispatch must be an object")
            continue

        dispatch_id = dispatch.get("dispatch_id")
        if not isinstance(dispatch_id, str) or not dispatch_id:
            error(errors, "DISPATCH_ID_MISSING", f"{location}.dispatch_id", "dispatch_id is required")
        elif dispatch_id in by_id:
            error(errors, "DISPATCH_ID_DUPLICATE", f"{location}.dispatch_id", "dispatch_id must be unique")
        else:
            ids.append(dispatch_id)
            by_id[dispatch_id] = dispatch

        operation = dispatch.get("operation")
        if operation not in DISPATCH_OPERATIONS:
            error(errors, "DISPATCH_OPERATION_INVALID", f"{location}.operation", "unsupported dispatch operation")

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
            if dispatch.get("parent_dispatch_id") is not None:
                error(errors, "ROOT_PARENT_INVALID", f"{location}.parent_dispatch_id", "initial dispatch must not have a parent")
        else:
            parent_id = dispatch.get("parent_dispatch_id")
            if not isinstance(parent_id, str) or parent_id not in by_id:
                error(errors, "PARENT_DISPATCH_MISSING", f"{location}.parent_dispatch_id", "follow-up must reference an earlier dispatch")
            if sender != root_sender or recipient != root_recipient:
                error(errors, "DISPATCH_PARTICIPANT_DRIFT", location, "sender and recipient must remain stable within the fixture chain")

        timestamp = dispatch.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            error(errors, "TIMESTAMP_INVALID", f"{location}.timestamp", "UTC timestamp is required")

        payload = dispatch.get("payload")
        if not isinstance(payload, dict):
            error(errors, "PAYLOAD_INVALID", f"{location}.payload", "payload must be an object")
            continue
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
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            error(errors, "CONTENT_DIGEST_INVALID", f"{location}.payload.content_digest", "sha256 content digest is required")
        elif isinstance(exact_content, str) and exact_content and digest != sha256_text(exact_content):
            error(errors, "CONTENT_DIGEST_MISMATCH", f"{location}.payload.content_digest", "digest must bind the authorized exact content")

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
    if not isinstance(output_digest, str) or not output_digest.startswith("sha256:"):
        error(errors, "RESULT_DIGEST_INVALID", "result.output_digest", "result output digest is required")

    return errors


def resolve_parent(root: dict[str, Any], path: str) -> tuple[Any, str | int]:
    parts = path.split(".")
    current: Any = root
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
    mutated = copy.deepcopy(record)
    op = mutation.get("op")
    path = mutation.get("path")
    if op not in {"set", "delete"} or not isinstance(path, str):
        raise ValueError("mutation requires op=set|delete and a path")
    parent, key = resolve_parent(mutated, path)
    if op == "delete":
        if isinstance(parent, list):
            del parent[key]
        else:
            del parent[key]
    else:
        parent[key] = copy.deepcopy(mutation.get("value"))
    return mutated


def validate_fixture(fixture: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    fixture_errors: list[dict[str, str]] = []
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        error(fixture_errors, "SCHEMA_DRAFT_INVALID", "schema.$schema", "Draft 2020-12 is required")
    properties = schema.get("properties", {})
    if properties.get("fixture_id", {}).get("const") != FIXTURE_ID:
        error(fixture_errors, "SCHEMA_FIXTURE_ID_INVALID", "schema.properties.fixture_id", "unexpected fixture id const")
    if properties.get("contract_version", {}).get("const") != CONTRACT_VERSION:
        error(fixture_errors, "SCHEMA_VERSION_INVALID", "schema.properties.contract_version", "unexpected contract version const")

    if fixture.get("fixture_id") != FIXTURE_ID:
        error(fixture_errors, "FIXTURE_ID_INVALID", "fixture_id", "unexpected fixture id")
    if fixture.get("contract_version") != CONTRACT_VERSION:
        error(fixture_errors, "CONTRACT_VERSION_INVALID", "contract_version", "unexpected contract version")

    canonical = fixture.get("canonical_record")
    canonical_errors = validate_record(canonical)

    vector_results: list[dict[str, Any]] = []
    negative_vectors = fixture.get("negative_vectors")
    if not isinstance(negative_vectors, list) or not negative_vectors:
        error(fixture_errors, "NEGATIVE_VECTORS_MISSING", "negative_vectors", "negative vectors are required")
    else:
        seen_cases: set[str] = set()
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
            try:
                mutated = apply_mutation(canonical, vector.get("mutation", {}))
                observed_errors = validate_record(mutated)
            except (KeyError, ValueError, TypeError) as exc:
                error(fixture_errors, "MUTATION_INVALID", f"{location}.mutation", str(exc))
                continue
            observed_codes = sorted({item["code"] for item in observed_errors})
            vector_results.append({
                "case": case,
                "expected_error_code": expected_code,
                "observed_error_codes": observed_codes,
                "rejected": expected_code in observed_codes,
            })
            if expected_code not in observed_codes:
                error(fixture_errors, "NEGATIVE_VECTOR_NOT_REJECTED", location, f"expected {expected_code}, observed {observed_codes}")

    expected = fixture.get("expected", {})
    if expected.get("canonical_passes") is not True or expected.get("negative_vectors_rejected") is not True:
        error(fixture_errors, "EXPECTED_OUTCOME_INVALID", "expected", "expected outcomes must require canonical pass and negative rejection")

    passed = not fixture_errors and not canonical_errors and all(item["rejected"] for item in vector_results)
    return {
        "fixture_id": fixture.get("fixture_id"),
        "contract_version": fixture.get("contract_version"),
        "passed": passed,
        "fixture_errors": fixture_errors,
        "canonical": {"passed": not canonical_errors, "errors": canonical_errors},
        "negative_vectors": vector_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("schema", type=Path)
    args = parser.parse_args()

    result = validate_fixture(load_object(args.fixture), load_object(args.schema))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
