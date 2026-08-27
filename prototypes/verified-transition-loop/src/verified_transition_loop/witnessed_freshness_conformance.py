from __future__ import annotations

import argparse
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
from .witnessed_freshness import (
    ED25519,
    PUBLIC_KEY_BYTES,
    PROFILE_ID,
    STATEMENT_PROFILE_ID,
    STATEMENT_SCHEMA_VERSION,
    _decode_base64,
    _utf16_sort_key,
    _validate_authority,
    _validate_statement,
    compute_witness_statement_id,
    verify_witnessed_freshness,
)

FIXTURE_PROFILE_ID = "vtl-witnessed-freshness-fixture/v0.13"
FIXTURE_SCHEMA_VERSION = "vtl.witnessed-freshness-fixture/v0.13"

_FIXTURE_FIELDS = {
    "profile_id",
    "schema_version",
    "canonical_profile",
    "base_now_ms",
    "snapshot_view",
    "local_snapshot_valid",
    "witness_authority",
    "statements",
    "cases",
}
_VIEW_FIELDS = {"trust_root_id", "generation", "snapshot_digest"}
_CASE_REQUIRED_FIELDS = {"id", "statement_refs", "expected"}
_CASE_OPTIONAL_FIELDS = {
    "local_snapshot_valid",
    "authority_mutations",
    "statement_mutations",
}
_EXPECTED_FIELDS = {
    "valid",
    "local_snapshot_valid",
    "witness_statement_integrity_valid",
    "witness_signature_valid",
    "witness_authority_valid",
    "witness_freshness_valid",
    "witness_quorum_valid",
    "view_consistency_valid",
    "equivocation_detected",
    "accepted_witness_ids",
    "reason_codes",
}
_MUTATION_FIELDS = {"path", "value"}
_STATEMENT_MUTATION_FIELDS = {"index", "path", "value"}
_DANGEROUS_PATH_PARTS = {"__proto__", "prototype", "constructor"}
_PATH_PART_RE = re.compile(r"(?:[A-Za-z_][A-Za-z0-9_-]*|0|[1-9][0-9]*)\Z")


def _fixture_error(detail: str) -> None:
    raise CanonicalizationError("FIXTURE_SCHEMA_INVALID", detail)


def _exact_dict(value: Any, fields: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _non_empty_string(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        canonical_bytes(value)
    except CanonicalizationError:
        return False
    return True


def _timestamp(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 <= value <= MAX_SAFE_INTEGER
    )


def _positive_integer(value: Any) -> bool:
    return _timestamp(value) and value >= 1


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _set_path(document: Any, path: str, value: Any) -> None:
    if not _non_empty_string(path):
        _fixture_error("mutation path must be non-empty")
    parts = path.split(".")
    if any(
        part in _DANGEROUS_PATH_PARTS or not _PATH_PART_RE.fullmatch(part)
        for part in parts
    ):
        _fixture_error(f"unsafe mutation path: {path}")

    cursor = document
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


def _validate_fixture_shape(fixture: Any) -> None:
    if not _exact_dict(fixture, _FIXTURE_FIELDS):
        _fixture_error("fixture fields")
    if fixture["profile_id"] != FIXTURE_PROFILE_ID:
        _fixture_error("profile_id")
    if fixture["schema_version"] != FIXTURE_SCHEMA_VERSION:
        _fixture_error("schema_version")
    if fixture["canonical_profile"] != CANONICAL_PROFILE:
        _fixture_error("canonical_profile")
    if not _timestamp(fixture["base_now_ms"]):
        _fixture_error("base_now_ms")
    if not isinstance(fixture["local_snapshot_valid"], bool):
        _fixture_error("local_snapshot_valid")

    view = fixture["snapshot_view"]
    if (
        not _exact_dict(view, _VIEW_FIELDS)
        or not _non_empty_string(view["trust_root_id"])
        or not _positive_integer(view["generation"])
        or not _hex64(view["snapshot_digest"])
    ):
        _fixture_error("snapshot_view")

    authority = fixture["witness_authority"]
    authority_reasons = _validate_authority(authority)
    if authority_reasons:
        _fixture_error(f"witness_authority: {authority_reasons[0]}")
    if authority["allowed_algorithms"] != [ED25519]:
        _fixture_error("witness_authority.allowed_algorithms")
    for key_index, key in enumerate(authority["keys"]):
        public_key = _decode_base64(key["public_key_base64"])
        if (
            key["algorithm"] != ED25519
            or public_key is None
            or len(public_key) != PUBLIC_KEY_BYTES
            or key["not_after_ms"] < key["not_before_ms"]
        ):
            _fixture_error(f"witness_authority.keys[{key_index}]")

    statements = fixture["statements"]
    if not isinstance(statements, dict) or not statements:
        _fixture_error("statements")
    for name, statement in statements.items():
        if not _non_empty_string(name):
            _fixture_error("statement name")
        statement_reasons = _validate_statement(statement)
        if statement_reasons:
            _fixture_error(f"statements[{name!r}]: {statement_reasons[0]}")
        try:
            identity_valid = (
                statement["statement_id"]
                == compute_witness_statement_id(statement)
            )
        except CanonicalizationError:
            identity_valid = False
        if (
            statement["profile_id"] != STATEMENT_PROFILE_ID
            or statement["schema_version"] != STATEMENT_SCHEMA_VERSION
            or statement["canonical_profile"] != CANONICAL_PROFILE
            or statement["signature_algorithm"] != ED25519
            or not identity_valid
        ):
            _fixture_error(f"statements[{name!r}] identity")

    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        _fixture_error("cases must be non-empty")
    identifiers: set[str] = set()
    referenced_statements: set[str] = set()
    verification_inputs: set[bytes] = set()
    allowed_case_fields = _CASE_REQUIRED_FIELDS | _CASE_OPTIONAL_FIELDS
    for case_index, case in enumerate(cases):
        if (
            not isinstance(case, dict)
            or not _CASE_REQUIRED_FIELDS.issubset(case)
            or not set(case).issubset(allowed_case_fields)
        ):
            _fixture_error(f"cases[{case_index}] fields")
        case_id = case["id"]
        if not _non_empty_string(case_id) or case_id in identifiers:
            _fixture_error(f"cases[{case_index}].id")
        identifiers.add(case_id)

        refs = case["statement_refs"]
        if (
            not isinstance(refs, list)
            or not refs
            or not all(_non_empty_string(ref) and ref in statements for ref in refs)
        ):
            _fixture_error(f"cases[{case_index}].statement_refs")
        referenced_statements.update(refs)
        if "local_snapshot_valid" in case and not isinstance(
            case["local_snapshot_valid"], bool
        ):
            _fixture_error(f"cases[{case_index}].local_snapshot_valid")

        expected = case["expected"]
        if not _exact_dict(expected, _EXPECTED_FIELDS):
            _fixture_error(f"cases[{case_index}].expected fields")
        boolean_fields = _EXPECTED_FIELDS - {"accepted_witness_ids", "reason_codes"}
        if not all(isinstance(expected[field], bool) for field in boolean_fields):
            _fixture_error(f"cases[{case_index}].expected booleans")
        accepted = expected["accepted_witness_ids"]
        if (
            not isinstance(accepted, list)
            or not all(_non_empty_string(witness_id) for witness_id in accepted)
            or len(set(accepted)) != len(accepted)
            or accepted != sorted(accepted, key=_utf16_sort_key)
        ):
            _fixture_error(f"cases[{case_index}].expected accepted_witness_ids")
        reason_codes = expected["reason_codes"]
        if (
            not isinstance(reason_codes, list)
            or not all(_non_empty_string(reason) for reason in reason_codes)
            or len(set(reason_codes)) != len(reason_codes)
        ):
            _fixture_error(f"cases[{case_index}].expected reason_codes")

        authority_copy = copy.deepcopy(fixture["witness_authority"])
        authority_mutations = case.get("authority_mutations", [])
        if not isinstance(authority_mutations, list):
            _fixture_error(f"cases[{case_index}].authority_mutations")
        authority_paths: set[str] = set()
        for mutation_index, mutation in enumerate(authority_mutations):
            if not _exact_dict(mutation, _MUTATION_FIELDS):
                _fixture_error(
                    f"cases[{case_index}].authority_mutations[{mutation_index}]"
                )
            if mutation["path"] in authority_paths:
                _fixture_error(
                    f"cases[{case_index}].authority_mutations duplicate path"
                )
            authority_paths.add(mutation["path"])
            _set_path(authority_copy, mutation["path"], mutation["value"])

        statement_copies = [copy.deepcopy(statements[ref]) for ref in refs]
        statement_mutations = case.get("statement_mutations", [])
        if not isinstance(statement_mutations, list):
            _fixture_error(f"cases[{case_index}].statement_mutations")
        statement_targets: set[tuple[int, str]] = set()
        for mutation_index, mutation in enumerate(statement_mutations):
            if not _exact_dict(mutation, _STATEMENT_MUTATION_FIELDS):
                _fixture_error(
                    f"cases[{case_index}].statement_mutations[{mutation_index}]"
                )
            index = mutation["index"]
            if (
                not isinstance(index, int)
                or isinstance(index, bool)
                or not 0 <= index < len(statement_copies)
            ):
                _fixture_error(
                    f"cases[{case_index}].statement_mutations[{mutation_index}].index"
                )
            target = (index, mutation["path"])
            if target in statement_targets:
                _fixture_error(
                    f"cases[{case_index}].statement_mutations duplicate target"
                )
            statement_targets.add(target)
            _set_path(
                statement_copies[index], mutation["path"], mutation["value"]
            )

        verification_input = canonical_bytes(
            {
                "snapshot_view": view,
                "local_snapshot_valid": case.get(
                    "local_snapshot_valid", fixture["local_snapshot_valid"]
                ),
                "witness_statements": statement_copies,
                "witness_authority": authority_copy,
                "now_ms": fixture["base_now_ms"],
            }
        )
        if verification_input in verification_inputs:
            _fixture_error(f"cases[{case_index}] duplicate verification input")
        verification_inputs.add(verification_input)

    if referenced_statements != set(statements):
        _fixture_error("unused statements")


def load_fixture(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_text(encoding="utf-8")
    data = strict_loads(raw)
    if not isinstance(data, dict):
        raise ValueError("fixture root must be an object")
    return data


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fixture, Mapping):
        _fixture_error("fixture root")
    try:
        fixture = copy.deepcopy(dict(fixture))
    except Exception:
        _fixture_error("fixture snapshot")
    _validate_fixture_shape(fixture)

    cases: list[dict[str, Any]] = []
    for case in fixture["cases"]:
        authority = copy.deepcopy(fixture["witness_authority"])
        statements = [
            copy.deepcopy(fixture["statements"][ref])
            for ref in case["statement_refs"]
        ]
        for mutation in case.get("authority_mutations", []):
            _set_path(authority, mutation["path"], mutation["value"])
        for mutation in case.get("statement_mutations", []):
            _set_path(
                statements[mutation["index"]], mutation["path"], mutation["value"]
            )
        result = verify_witnessed_freshness(
            snapshot_view=fixture["snapshot_view"],
            local_snapshot_valid=case.get(
                "local_snapshot_valid", fixture["local_snapshot_valid"]
            ),
            witness_statements=statements,
            witness_authority=authority,
            now_ms=fixture["base_now_ms"],
        )
        actual = {
            "valid": result.valid,
            "local_snapshot_valid": result.local_snapshot_valid,
            "witness_statement_integrity_valid": (
                result.witness_statement_integrity_valid
            ),
            "witness_signature_valid": result.witness_signature_valid,
            "witness_authority_valid": result.witness_authority_valid,
            "witness_freshness_valid": result.witness_freshness_valid,
            "witness_quorum_valid": result.witness_quorum_valid,
            "view_consistency_valid": result.view_consistency_valid,
            "equivocation_detected": result.equivocation_detected,
            "accepted_witness_ids": list(result.accepted_witness_ids),
            "reason_codes": list(result.reason_codes),
        }
        expected = case["expected"]
        cases.append(
            {
                "id": case["id"],
                "actual": actual,
                "expected": expected,
                "passed": actual == expected,
            }
        )
    passed = sum(1 for case in cases if case["passed"])
    all_passed = (
        passed == len(cases)
        and any(case["actual"]["valid"] for case in cases)
    )
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "cases": cases,
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "all_passed": all_passed,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify VTL v0.13 witnessed freshness vectors"
    )
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    result = run_fixture(load_fixture(args.fixture))
    if args.compact:
        serialized_public_evidence = json.dumps(
            result, separators=(",", ":"), sort_keys=True
        )
    else:
        serialized_public_evidence = json.dumps(result, indent=2, sort_keys=True)
    # Public conformance evidence only; no private witness key material is loaded.
    sys.stdout.buffer.write(serialized_public_evidence.encode("utf-8") + b"\n")
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
