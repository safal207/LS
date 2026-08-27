from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
from pathlib import Path
from typing import Any

PROFILE_ID = "vtl-canonical-proof-v0.10"
SCHEMA_VERSION = "vtl.canonical-proof/v0.10"
CANONICAL_PROFILE = "rfc8785-safe-integer/v0.10"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
_FIXTURE_FIELDS = frozenset(
    (
        "profile_id",
        "schema_version",
        "canonical_profile",
        "cases",
        "negative_cases",
        "mutation_cases",
    )
)
_CASE_FIELDS = frozenset(
    ("id", "raw_json", "canonical_utf8_base64", "sha256")
)
_NEGATIVE_CASE_FIELDS = frozenset(("id", "raw_json", "error_code"))
_MUTATION_CASE_FIELDS = frozenset(
    (
        "id",
        "base_raw_json",
        "mutated_raw_json",
        "base_sha256",
        "mutated_sha256",
        "digests_differ",
    )
)
_NEGATIVE_ERROR_CODES = frozenset(
    (
        "UNSUPPORTED_NUMBER",
        "INTEGER_OUT_OF_RANGE",
        "DUPLICATE_KEY",
        "INVALID_UNICODE_SCALAR",
        "INVALID_JSON",
    )
)


class CanonicalizationError(ValueError):
    def __init__(self, code: str, detail: str | None = None) -> None:
        self.code = code
        super().__init__(detail or code)


def _validate_unicode_scalar_string(value: str) -> None:
    for ch in value:
        codepoint = ord(ch)
        if 0xD800 <= codepoint <= 0xDFFF:
            raise CanonicalizationError("INVALID_UNICODE_SCALAR")


def _escape_string(value: str) -> str:
    _validate_unicode_scalar_string(value)
    short_escapes = {
        0x08: "\\b",
        0x09: "\\t",
        0x0A: "\\n",
        0x0C: "\\f",
        0x0D: "\\r",
    }
    parts = ['"']
    for ch in value:
        codepoint = ord(ch)
        if ch == '"':
            parts.append('\\"')
        elif ch == "\\":
            parts.append("\\\\")
        elif codepoint in short_escapes:
            parts.append(short_escapes[codepoint])
        elif codepoint <= 0x1F:
            parts.append(f"\\u{codepoint:04x}")
        else:
            parts.append(ch)
    parts.append('"')
    return "".join(parts)


def _utf16_sort_key(value: str) -> bytes:
    _validate_unicode_scalar_string(value)
    return value.encode("utf-16-be")


def canonical_text(value: Any) -> str:
    """Canonicalize the RFC 8785-compatible VTL safe subset."""

    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise CanonicalizationError("INTEGER_OUT_OF_RANGE")
        return str(value)
    if isinstance(value, float):
        raise CanonicalizationError("UNSUPPORTED_NUMBER")
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, list):
        return "[" + ",".join(canonical_text(item) for item in value) + "]"
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise CanonicalizationError("OBJECT_KEY_NOT_STRING")
            _validate_unicode_scalar_string(key)
        ordered = sorted(value, key=_utf16_sort_key)
        return "{" + ",".join(
            _escape_string(key) + ":" + canonical_text(value[key])
            for key in ordered
        ) + "}"
    raise CanonicalizationError("UNSUPPORTED_TYPE")


def canonical_bytes(value: Any) -> bytes:
    return canonical_text(value).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _reject_float(_: str) -> Any:
    raise CanonicalizationError("UNSUPPORTED_NUMBER")


def _reject_constant(_: str) -> Any:
    raise CanonicalizationError("INVALID_JSON")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _validate_unicode_scalar_string(key)
        if key in result:
            raise CanonicalizationError("DUPLICATE_KEY", key)
        result[key] = value
    return result


def strict_loads(raw: str) -> Any:
    """Parse raw JSON without silently accepting duplicate names or floats."""

    try:
        value = json.loads(
            raw,
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except CanonicalizationError:
        raise
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CanonicalizationError("INVALID_JSON", str(exc)) from exc

    canonical_bytes(value)
    return value


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _is_hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _is_canonical_base64(value: Any) -> bool:
    if not _is_non_empty_string(value):
        return False
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return False
    return base64.b64encode(decoded).decode("ascii") == value


def _has_exact_fields(value: Any, fields: frozenset[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _validate_fixture_shape(fixture: Any) -> None:
    if not isinstance(fixture, dict):
        raise CanonicalizationError("FIXTURE_ROOT_INVALID")
    if set(fixture) != _FIXTURE_FIELDS:
        raise CanonicalizationError("FIXTURE_SCHEMA_INVALID", "fixture fields")

    case_groups = (
        ("cases", _CASE_FIELDS),
        ("negative_cases", _NEGATIVE_CASE_FIELDS),
        ("mutation_cases", _MUTATION_CASE_FIELDS),
    )
    identifiers: set[str] = set()
    for group_name, fields in case_groups:
        group = fixture[group_name]
        if not isinstance(group, list) or not group:
            raise CanonicalizationError(
                "FIXTURE_SCHEMA_INVALID", f"{group_name} must be non-empty"
            )
        for index, case in enumerate(group):
            if not _has_exact_fields(case, fields):
                raise CanonicalizationError(
                    "FIXTURE_SCHEMA_INVALID", f"{group_name}[{index}] fields"
                )
            case_id = case["id"]
            if not _is_non_empty_string(case_id):
                raise CanonicalizationError(
                    "FIXTURE_SCHEMA_INVALID", f"{group_name}[{index}].id"
                )
            if case_id in identifiers:
                raise CanonicalizationError("FIXTURE_CASE_ID_DUPLICATE", case_id)
            identifiers.add(case_id)

    for index, case in enumerate(fixture["cases"]):
        if (
            not isinstance(case["raw_json"], str)
            or not _is_canonical_base64(case["canonical_utf8_base64"])
            or not _is_hex64(case["sha256"])
        ):
            raise CanonicalizationError(
                "FIXTURE_SCHEMA_INVALID", f"cases[{index}] values"
            )

    for index, case in enumerate(fixture["negative_cases"]):
        if (
            not isinstance(case["raw_json"], str)
            or not isinstance(case["error_code"], str)
            or case["error_code"] not in _NEGATIVE_ERROR_CODES
        ):
            raise CanonicalizationError(
                "FIXTURE_SCHEMA_INVALID", f"negative_cases[{index}] values"
            )

    for index, case in enumerate(fixture["mutation_cases"]):
        if (
            not isinstance(case["base_raw_json"], str)
            or not isinstance(case["mutated_raw_json"], str)
            or not _is_hex64(case["base_sha256"])
            or not _is_hex64(case["mutated_sha256"])
            or case["digests_differ"] is not True
        ):
            raise CanonicalizationError(
                "FIXTURE_SCHEMA_INVALID", f"mutation_cases[{index}] values"
            )


def _result_for_case(case: dict[str, Any]) -> dict[str, Any]:
    value = strict_loads(case["raw_json"])
    actual_bytes = canonical_bytes(value)
    actual_b64 = base64.b64encode(actual_bytes).decode("ascii")
    actual_sha256 = hashlib.sha256(actual_bytes).hexdigest()
    passed = (
        actual_b64 == case["canonical_utf8_base64"]
        and actual_sha256 == case["sha256"]
    )
    return {
        "id": case["id"],
        "canonical_utf8_base64": actual_b64,
        "sha256": actual_sha256,
        "passed": passed,
    }


def _result_for_negative(case: dict[str, Any]) -> dict[str, Any]:
    actual_error: str | None = None
    try:
        value = strict_loads(case["raw_json"])
        canonical_bytes(value)
    except CanonicalizationError as exc:
        actual_error = exc.code
    return {
        "id": case["id"],
        "error_code": actual_error,
        "passed": actual_error == case["error_code"],
    }


def _result_for_mutation(case: dict[str, Any]) -> dict[str, Any]:
    base = strict_loads(case["base_raw_json"])
    mutated = strict_loads(case["mutated_raw_json"])
    base_digest = canonical_sha256(base)
    mutated_digest = canonical_sha256(mutated)
    passed = (
        base_digest == case["base_sha256"]
        and mutated_digest == case["mutated_sha256"]
        and (base_digest != mutated_digest) == case["digests_differ"]
    )
    return {
        "id": case["id"],
        "base_sha256": base_digest,
        "mutated_sha256": mutated_digest,
        "digests_differ": base_digest != mutated_digest,
        "passed": passed,
    }


def verify_fixture(fixture: Any) -> dict[str, Any]:
    _validate_fixture_shape(fixture)
    if fixture["profile_id"] != PROFILE_ID:
        raise CanonicalizationError("PROFILE_ID_MISMATCH")
    if fixture["schema_version"] != SCHEMA_VERSION:
        raise CanonicalizationError("SCHEMA_VERSION_MISMATCH")
    if fixture["canonical_profile"] != CANONICAL_PROFILE:
        raise CanonicalizationError("CANONICAL_PROFILE_MISMATCH")

    cases = [_result_for_case(case) for case in fixture["cases"]]
    negative_cases = [
        _result_for_negative(case) for case in fixture["negative_cases"]
    ]
    mutation_cases = [
        _result_for_mutation(case) for case in fixture["mutation_cases"]
    ]
    all_results = [*cases, *negative_cases, *mutation_cases]
    passed = sum(1 for result in all_results if result["passed"])
    summary = {
        "total": len(all_results),
        "passed": passed,
        "failed": len(all_results) - passed,
        "all_passed": passed == len(all_results),
    }
    return {
        "profile_id": PROFILE_ID,
        "schema_version": SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "cases": cases,
        "negative_cases": negative_cases,
        "mutation_cases": mutation_cases,
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify VTL v0.10 canonical-byte proof vectors"
    )
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args(argv)

    fixture = strict_loads(args.fixture.read_text(encoding="utf-8"))
    result = verify_fixture(fixture)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
