from __future__ import annotations

import argparse
import base64
import binascii
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from .canonical import (
    CANONICAL_PROFILE,
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    canonical_bytes,
    strict_loads,
)
from .canonical_trust_snapshot import (
    FIXTURE_SCHEMA_VERSION,
    PROFILE_ID,
    validate_bootstrap_authority_shape,
    validate_checkpoint_shape,
    validate_snapshot_shape,
    verify_canonical_trust_snapshot,
)

_FIXTURE_FIELDS = {
    "profile_id",
    "schema_version",
    "canonical_profile",
    "base_now_ms",
    "bootstrap_authority",
    "base_snapshot",
    "snapshot_variants",
    "checkpoints",
    "expected_fresh_signed_payload_base64",
    "expected_fresh_signature_base64",
    "expected_fresh_snapshot_digest",
    "cases",
}
_CASE_REQUIRED_FIELDS = {"id", "checkpoint_ref", "expected"}
_CASE_OPTIONAL_FIELDS = {
    "variant_ref",
    "snapshot_mutations",
    "bootstrap_mutations",
    "checkpoint_mutations",
}
_EXPECTED_FIELDS = {
    "valid",
    "snapshot_integrity_valid",
    "canonical_profile_valid",
    "bootstrap_signature_valid",
    "bootstrap_authority_valid",
    "freshness_valid",
    "continuity_valid",
    "reason_codes",
}
_MUTATION_FIELDS = {"path", "value"}
_DANGEROUS_PATH_PARTS = {"__proto__", "prototype", "constructor"}
_PATH_PART_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_-]*|0|[1-9][0-9]*)\Z")


def _fixture_error(detail: str) -> None:
    raise CanonicalizationError("FIXTURE_SCHEMA_INVALID", detail)


def _exact_dict(value: Any, fields: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _timestamp(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= MAX_SAFE_INTEGER
    )


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_base64(value: Any, *, length: int | None = None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return False
    return (
        base64.b64encode(decoded).decode("ascii") == value
        and (length is None or len(decoded) == length)
    )


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    if not _non_empty_string(path):
        _fixture_error("mutation path must be non-empty")
    parts = path.split(".")
    if any(
        part in _DANGEROUS_PATH_PARTS or not _PATH_PART_RE.fullmatch(part)
        for part in parts
    ):
        _fixture_error(f"unsafe mutation path: {path}")

    cursor: Any = document
    for part in parts[:-1]:
        if isinstance(cursor, list):
            if not part.isdigit() or int(part) >= len(cursor):
                _fixture_error(f"missing mutation path: {path}")
            cursor = cursor[int(part)]
        elif isinstance(cursor, dict) and part in cursor:
            cursor = cursor[part]
        else:
            _fixture_error(f"missing mutation path: {path}")

    last = parts[-1]
    if isinstance(cursor, list):
        if not last.isdigit() or int(last) >= len(cursor):
            _fixture_error(f"missing mutation path: {path}")
        previous = cursor[int(last)]
    elif isinstance(cursor, dict) and last in cursor:
        previous = cursor[last]
    else:
        _fixture_error(f"missing mutation path: {path}")

    try:
        is_noop = canonical_bytes(previous) == canonical_bytes(value)
    except CanonicalizationError as exc:
        _fixture_error(f"invalid mutation value for {path}: {exc.code}")
    if is_noop:
        _fixture_error(f"no-op mutation path: {path}")

    if isinstance(cursor, list):
        cursor[int(last)] = copy.deepcopy(value)
    else:
        cursor[last] = copy.deepcopy(value)


def _apply_variant(
    base_snapshot: Mapping[str, Any], variant: Mapping[str, Any] | None
) -> dict[str, Any]:
    snapshot = copy.deepcopy(dict(base_snapshot))
    if variant:
        for key, value in variant.items():
            snapshot[key] = copy.deepcopy(value)
    return snapshot


def _validate_fixture_shape(fixture: Any) -> None:
    if not _exact_dict(fixture, _FIXTURE_FIELDS):
        _fixture_error("fixture fields")
    if fixture["profile_id"] != PROFILE_ID:
        _fixture_error("profile_id")
    if fixture["schema_version"] != FIXTURE_SCHEMA_VERSION:
        _fixture_error("schema_version")
    if fixture["canonical_profile"] != CANONICAL_PROFILE:
        _fixture_error("canonical_profile")
    if not _timestamp(fixture["base_now_ms"]):
        _fixture_error("base_now_ms")

    base_snapshot = fixture["base_snapshot"]
    snapshot_reasons = validate_snapshot_shape(base_snapshot)
    if snapshot_reasons:
        _fixture_error(f"base_snapshot: {snapshot_reasons[0]}")

    authority_reasons = validate_bootstrap_authority_shape(
        fixture["bootstrap_authority"]
    )
    if authority_reasons:
        _fixture_error(f"bootstrap_authority: {authority_reasons[0]}")

    variants = fixture["snapshot_variants"]
    if not isinstance(variants, dict):
        _fixture_error("snapshot_variants")
    for name, variant in variants.items():
        if not _non_empty_string(name) or not isinstance(variant, dict) or not variant:
            _fixture_error(f"snapshot_variants[{name!r}]")
        if not set(variant).issubset(base_snapshot):
            _fixture_error(f"snapshot_variants[{name!r}] fields")
        for field, value in variant.items():
            try:
                is_noop = canonical_bytes(value) == canonical_bytes(base_snapshot[field])
            except CanonicalizationError as exc:
                _fixture_error(f"snapshot_variants[{name!r}].{field}: {exc.code}")
            if is_noop:
                _fixture_error(f"snapshot_variants[{name!r}].{field} is a no-op")
        variant_reasons = validate_snapshot_shape(_apply_variant(base_snapshot, variant))
        if variant_reasons:
            _fixture_error(f"snapshot_variants[{name!r}]: {variant_reasons[0]}")

    checkpoints = fixture["checkpoints"]
    if not isinstance(checkpoints, dict) or not checkpoints:
        _fixture_error("checkpoints")
    for name, checkpoint in checkpoints.items():
        if not _non_empty_string(name):
            _fixture_error("checkpoint name")
        checkpoint_reasons = validate_checkpoint_shape(checkpoint)
        if checkpoint_reasons:
            _fixture_error(f"checkpoints[{name!r}]: {checkpoint_reasons[0]}")

    if not _canonical_base64(fixture["expected_fresh_signed_payload_base64"]):
        _fixture_error("expected_fresh_signed_payload_base64")
    if not _canonical_base64(
        fixture["expected_fresh_signature_base64"], length=64
    ):
        _fixture_error("expected_fresh_signature_base64")
    if not _hex64(fixture["expected_fresh_snapshot_digest"]):
        _fixture_error("expected_fresh_snapshot_digest")

    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        _fixture_error("cases must be non-empty")
    identifiers: set[str] = set()
    referenced_variants: set[str] = set()
    referenced_checkpoints: set[str] = set()
    allowed_case_fields = _CASE_REQUIRED_FIELDS | _CASE_OPTIONAL_FIELDS
    for index, case in enumerate(cases):
        if (
            not isinstance(case, dict)
            or not _CASE_REQUIRED_FIELDS.issubset(case)
            or not set(case).issubset(allowed_case_fields)
        ):
            _fixture_error(f"cases[{index}] fields")
        case_id = case["id"]
        if not _non_empty_string(case_id):
            _fixture_error(f"cases[{index}].id")
        if case_id in identifiers:
            _fixture_error(f"duplicate case id: {case_id}")
        identifiers.add(case_id)

        checkpoint_ref = case["checkpoint_ref"]
        if not _non_empty_string(checkpoint_ref) or checkpoint_ref not in checkpoints:
            _fixture_error(f"cases[{index}].checkpoint_ref")
        referenced_checkpoints.add(checkpoint_ref)

        variant_ref = case.get("variant_ref")
        if variant_ref is not None:
            if not _non_empty_string(variant_ref) or variant_ref not in variants:
                _fixture_error(f"cases[{index}].variant_ref")
            referenced_variants.add(variant_ref)

        expected = case["expected"]
        if not _exact_dict(expected, _EXPECTED_FIELDS):
            _fixture_error(f"cases[{index}].expected fields")
        boolean_fields = _EXPECTED_FIELDS - {"reason_codes"}
        if not all(isinstance(expected[field], bool) for field in boolean_fields):
            _fixture_error(f"cases[{index}].expected booleans")
        reason_codes = expected["reason_codes"]
        if (
            not isinstance(reason_codes, list)
            or not all(_non_empty_string(reason) for reason in reason_codes)
            or len(set(reason_codes)) != len(reason_codes)
        ):
            _fixture_error(f"cases[{index}].expected reason_codes")

        variant = variants.get(variant_ref) if variant_ref is not None else None
        documents = {
            "snapshot_mutations": _apply_variant(base_snapshot, variant),
            "bootstrap_mutations": copy.deepcopy(fixture["bootstrap_authority"]),
            "checkpoint_mutations": copy.deepcopy(checkpoints[checkpoint_ref]),
        }
        for group_name, document in documents.items():
            mutations = case.get(group_name, [])
            if not isinstance(mutations, list):
                _fixture_error(f"cases[{index}].{group_name}")
            for mutation_index, mutation in enumerate(mutations):
                if not _exact_dict(mutation, _MUTATION_FIELDS):
                    _fixture_error(
                        f"cases[{index}].{group_name}[{mutation_index}] fields"
                    )
                _set_path(document, mutation["path"], mutation["value"])

    if referenced_variants != set(variants):
        _fixture_error("unused snapshot_variants")
    if referenced_checkpoints != set(checkpoints):
        _fixture_error("unused checkpoints")


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        _fixture_error("fixture root")
    try:
        fixture = copy.deepcopy(dict(fixture))
    except Exception:
        _fixture_error("fixture snapshot")
    _validate_fixture_shape(fixture)

    results: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        variant = (
            fixture["snapshot_variants"][case["variant_ref"]]
            if "variant_ref" in case
            else None
        )
        snapshot = _apply_variant(fixture["base_snapshot"], variant)
        authority = copy.deepcopy(fixture["bootstrap_authority"])
        checkpoint = copy.deepcopy(fixture["checkpoints"][case["checkpoint_ref"]])

        for mutation in case.get("snapshot_mutations", []):
            _set_path(snapshot, mutation["path"], mutation["value"])
        for mutation in case.get("bootstrap_mutations", []):
            _set_path(authority, mutation["path"], mutation["value"])
        for mutation in case.get("checkpoint_mutations", []):
            _set_path(checkpoint, mutation["path"], mutation["value"])

        result = verify_canonical_trust_snapshot(
            snapshot,
            authority,
            checkpoint,
            now_ms=fixture["base_now_ms"],
        )
        actual = {
            "valid": result.valid,
            "snapshot_integrity_valid": result.snapshot_integrity_valid,
            "canonical_profile_valid": result.canonical_profile_valid,
            "bootstrap_signature_valid": result.bootstrap_signature_valid,
            "bootstrap_authority_valid": result.bootstrap_authority_valid,
            "freshness_valid": result.freshness_valid,
            "continuity_valid": result.continuity_valid,
            "reason_codes": list(result.reason_codes),
        }
        results.append(
            {
                "id": case["id"],
                "actual": actual,
                "expected": case["expected"],
                "passed": actual == case["expected"],
            }
        )

    fresh = copy.deepcopy(fixture["base_snapshot"])
    base_result = verify_canonical_trust_snapshot(
        fresh,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    parity = {
        "signed_payload_base64": base_result.signed_payload_base64,
        "signed_payload_matches_expected": (
            base_result.signed_payload_base64
            == fixture["expected_fresh_signed_payload_base64"]
        ),
        "signature_base64": fresh["signature"],
        "signature_matches_expected": (
            fresh["signature"] == fixture["expected_fresh_signature_base64"]
        ),
        "snapshot_digest": base_result.snapshot_digest,
        "snapshot_digest_matches_expected": (
            base_result.snapshot_digest == fixture["expected_fresh_snapshot_digest"]
        ),
    }
    passed = sum(1 for result in results if result["passed"])
    all_passed = (
        base_result.valid
        and passed == len(results)
        and parity["signed_payload_matches_expected"]
        and parity["signature_matches_expected"]
        and parity["snapshot_digest_matches_expected"]
    )
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "parity": parity,
        "cases": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            "all_passed": all_passed,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run VTL v0.12 canonical trust-root snapshot conformance"
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)

    fixture = strict_loads(args.fixture.read_text(encoding="utf-8"))
    result = run_fixture(fixture)
    serialized_public_evidence = json.dumps(
        result, indent=2, sort_keys=True, ensure_ascii=False
    )
    # Deterministic public conformance evidence; no private-key material is loaded.
    sys.stdout.buffer.write(serialized_public_evidence.encode("utf-8") + b"\n")
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
