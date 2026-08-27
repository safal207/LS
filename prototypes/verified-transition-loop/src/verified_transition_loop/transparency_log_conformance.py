from __future__ import annotations

import argparse
import base64
import copy
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .canonical import (
    CANONICAL_PROFILE,
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    canonical_bytes,
    strict_loads,
)
from .transparency_log import (
    CHECKPOINT_PROFILE_ID,
    ED25519,
    ENTRY_PROFILE_ID,
    FIXTURE_SCHEMA_VERSION,
    LOG_AUTHORITY_PROFILE_ID,
    MAX_PROOF_NODES,
    PROFILE_ID,
    PUBLIC_KEY_BYTES,
    SCHEMA_VERSION,
    SIGNATURE_BYTES,
    VERIFIER_CHECKPOINT_PROFILE_ID,
    _AUTHORITY_FIELDS,
    _BUNDLE_FIELDS,
    _CHECKPOINT_FIELDS,
    _ENTRY_FIELDS,
    _KEY_FIELDS,
    _TARGET_FIELDS,
    _VERIFIER_CHECKPOINT_FIELDS,
    _authority_shape_reasons,
    _checkpoint_shape_reasons,
    _decode_base64,
    _entry_valid,
    _target_valid,
    _verify_checkpoint,
    checkpoint_digest,
    compute_checkpoint_id,
    merkle_leaf_hash,
    signed_checkpoint_payload,
)
from .transparency_log_strict import verify_transparency_log

_FIXTURE_FIELDS = {
    "profile_id",
    "schema_version",
    "canonical_profile",
    "base_now_ms",
    "base_bundle",
    "checkpoint_variants",
    "verifier_checkpoint_variants",
    "inclusion_path_variants",
    "consistency_path_variants",
    "expected_base_entry_canonical_base64",
    "expected_base_leaf_hash",
    "expected_base_checkpoint_signed_payload_base64",
    "expected_base_checkpoint_signature_base64",
    "expected_base_checkpoint_digest",
    "expected_base_root_hash",
    "cases",
}
_CASE_REQUIRED_FIELDS = {"id", "expected"}
_CASE_OPTIONAL_FIELDS = {
    "checkpoint_ref",
    "verifier_checkpoint_ref",
    "inclusion_path_ref",
    "consistency_path_ref",
    "peer_checkpoint_refs",
    "mutations",
}
_EXPECTED_FIELDS = {
    "valid",
    "local_witnessed_freshness_valid",
    "entry_integrity_valid",
    "log_checkpoint_integrity_valid",
    "log_checkpoint_signature_valid",
    "log_checkpoint_authority_valid",
    "log_checkpoint_freshness_valid",
    "inclusion_valid",
    "consistency_valid",
    "view_consistency_valid",
    "log_equivocation_detected",
    "accepted_tree_size",
    "accepted_root_hash",
    "reason_codes",
}
_MUTATION_FIELDS = {"path", "value"}
_DANGEROUS_PATH_PARTS = {"__proto__", "prototype", "constructor"}
_PATH_PART_RE = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_-]*|0|[1-9][0-9]*)\Z"
)


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


def _integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and abs(value) <= MAX_SAFE_INTEGER
    )


def _timestamp(value: Any) -> bool:
    return _integer(value) and value >= 0


def _positive_integer(value: Any) -> bool:
    return _integer(value) and value >= 1


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _canonical_base64(value: Any, length: int | None = None) -> bool:
    decoded = _decode_base64(value)
    return decoded is not None and (
        length is None or len(decoded) == length
    )


def _hash_path(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= MAX_PROOF_NODES
        and all(_hex64(item) for item in value)
    )


def _checkpoint_fixture_shape(checkpoint: Any) -> bool:
    if not _exact_dict(checkpoint, _CHECKPOINT_FIELDS):
        return False
    specs = {
        "checkpoint_id": _non_empty_string,
        "profile_id": _non_empty_string,
        "schema_version": _non_empty_string,
        "canonical_profile": _non_empty_string,
        "log_id": _non_empty_string,
        "tree_size": _positive_integer,
        "root_hash": _hex64,
        "issued_at_ms": _timestamp,
        "not_before_ms": _timestamp,
        "not_after_ms": _timestamp,
        "issuer_id": _non_empty_string,
        "log_authority_id": _non_empty_string,
        "log_key_id": _non_empty_string,
        "signature_algorithm": _non_empty_string,
        "signature": lambda value: _canonical_base64(
            value, SIGNATURE_BYTES
        ),
    }
    if not all(predicate(checkpoint.get(field)) for field, predicate in specs.items()):
        return False
    try:
        return checkpoint["checkpoint_id"] == compute_checkpoint_id(checkpoint)
    except CanonicalizationError:
        return False


def _verifier_checkpoint_shape(checkpoint: Any) -> bool:
    return (
        _exact_dict(checkpoint, _VERIFIER_CHECKPOINT_FIELDS)
        and checkpoint["profile_id"] == VERIFIER_CHECKPOINT_PROFILE_ID
        and _non_empty_string(checkpoint["log_id"])
        and _positive_integer(checkpoint["known_tree_size"])
        and _hex64(checkpoint["known_root_hash"])
        and _positive_integer(checkpoint["minimum_tree_size"])
        and _timestamp(checkpoint["checkpointed_at_ms"])
    )


def _set_path(document: Any, path: str, value: Any) -> None:
    if not _non_empty_string(path):
        _fixture_error("mutation path")
    parts = path.split(".")
    if any(
        part in _DANGEROUS_PATH_PARTS
        or not _PATH_PART_RE.fullmatch(part)
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
        no_op = canonical_bytes(previous) == canonical_bytes(value)
    except CanonicalizationError as exc:
        _fixture_error(f"invalid mutation value: {exc.code}")
    if no_op:
        _fixture_error(f"no-op mutation path: {path}")

    if isinstance(cursor, list):
        cursor[int(last)] = copy.deepcopy(value)
    else:
        cursor[last] = copy.deepcopy(value)


def _case_bundle(
    fixture: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    bundle = copy.deepcopy(fixture["base_bundle"])
    checkpoint_ref = case.get("checkpoint_ref")
    if checkpoint_ref is not None:
        bundle["checkpoint"] = copy.deepcopy(
            fixture["checkpoint_variants"][checkpoint_ref]
        )
    verifier_ref = case.get("verifier_checkpoint_ref")
    if verifier_ref is not None:
        bundle["verifier_checkpoint"] = copy.deepcopy(
            fixture["verifier_checkpoint_variants"][verifier_ref]
        )
    inclusion_ref = case.get("inclusion_path_ref")
    if inclusion_ref is not None:
        bundle["inclusion_path"] = copy.deepcopy(
            fixture["inclusion_path_variants"][inclusion_ref]
        )
    consistency_ref = case.get("consistency_path_ref")
    if consistency_ref is not None:
        bundle["consistency_path"] = copy.deepcopy(
            fixture["consistency_path_variants"][consistency_ref]
        )
    peer_refs = case.get("peer_checkpoint_refs")
    if peer_refs is not None:
        bundle["peer_checkpoints"] = [
            copy.deepcopy(fixture["checkpoint_variants"][ref])
            for ref in peer_refs
        ]
    for mutation in case.get("mutations", []):
        _set_path(
            bundle,
            mutation["path"],
            mutation["value"],
        )
    return bundle


def _validate_expected(expected: Any, case_index: int) -> None:
    if not _exact_dict(expected, _EXPECTED_FIELDS):
        _fixture_error(f"cases[{case_index}].expected fields")
    bool_fields = _EXPECTED_FIELDS - {
        "accepted_tree_size",
        "accepted_root_hash",
        "reason_codes",
    }
    if not all(isinstance(expected[field], bool) for field in bool_fields):
        _fixture_error(f"cases[{case_index}].expected booleans")
    tree_size = expected["accepted_tree_size"]
    if tree_size is not None and not _positive_integer(tree_size):
        _fixture_error(f"cases[{case_index}].accepted_tree_size")
    root_hash = expected["accepted_root_hash"]
    if root_hash is not None and not _hex64(root_hash):
        _fixture_error(f"cases[{case_index}].accepted_root_hash")
    reasons = expected["reason_codes"]
    if (
        not isinstance(reasons, list)
        or not all(_non_empty_string(reason) for reason in reasons)
        or len(set(reasons)) != len(reasons)
    ):
        _fixture_error(f"cases[{case_index}].reason_codes")


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

    bundle = fixture["base_bundle"]
    if not _exact_dict(bundle, _BUNDLE_FIELDS):
        _fixture_error("base_bundle")
    if not isinstance(bundle["local_witnessed_freshness_valid"], bool):
        _fixture_error("base local witness claim")
    if not _target_valid(bundle["target"]):
        _fixture_error("base target")
    if not _entry_valid(bundle["entry"]):
        _fixture_error("base entry")
    for field in _TARGET_FIELDS:
        if bundle["target"][field] != bundle["entry"][field]:
            _fixture_error(f"base target mismatch: {field}")
    if (
        not _integer(bundle["leaf_index"])
        or bundle["leaf_index"] < 0
        or not _hash_path(bundle["inclusion_path"])
        or not _hash_path(bundle["consistency_path"])
        or not isinstance(bundle["peer_checkpoints"], list)
    ):
        _fixture_error("base proof fields")

    if _checkpoint_shape_reasons(bundle["checkpoint"]):
        _fixture_error("base checkpoint")
    if _authority_shape_reasons(bundle["log_authority"]):
        _fixture_error("base log authority")
    authority = bundle["log_authority"]
    if authority["allowed_algorithms"] != [ED25519]:
        _fixture_error("base log algorithms")
    for key_index, key in enumerate(authority["keys"]):
        public_key = _decode_base64(key["public_key_base64"])
        if (
            set(key) != _KEY_FIELDS
            or key["algorithm"] != ED25519
            or public_key is None
            or len(public_key) != PUBLIC_KEY_BYTES
            or key["not_after_ms"] < key["not_before_ms"]
        ):
            _fixture_error(f"base log key: {key_index}")
    checkpoint_claims = _verify_checkpoint(
        bundle["checkpoint"],
        authority,
        now_ms=fixture["base_now_ms"],
    )
    if not all(checkpoint_claims[:4]):
        _fixture_error("base checkpoint claims")
    if not _verifier_checkpoint_shape(bundle["verifier_checkpoint"]):
        _fixture_error("base verifier checkpoint")
    for peer in bundle["peer_checkpoints"]:
        if not _checkpoint_fixture_shape(peer):
            _fixture_error("base peer checkpoint")

    group_specs = (
        ("checkpoint_variants", _checkpoint_fixture_shape),
        ("verifier_checkpoint_variants", _verifier_checkpoint_shape),
        ("inclusion_path_variants", _hash_path),
        ("consistency_path_variants", _hash_path),
    )
    for group_name, predicate in group_specs:
        group = fixture[group_name]
        if not isinstance(group, dict) or not group:
            _fixture_error(group_name)
        for name, value in group.items():
            if not _non_empty_string(name) or not predicate(value):
                _fixture_error(f"{group_name}[{name!r}]")

    base_pairs = (
        ("checkpoint_variants", "checkpoint"),
        ("verifier_checkpoint_variants", "verifier_checkpoint"),
        ("inclusion_path_variants", "inclusion_path"),
        ("consistency_path_variants", "consistency_path"),
    )
    for group_name, bundle_field in base_pairs:
        if (
            "base" not in fixture[group_name]
            or canonical_bytes(fixture[group_name]["base"])
            != canonical_bytes(bundle[bundle_field])
        ):
            _fixture_error(f"{group_name}.base")

    anchor_specs = {
        "expected_base_entry_canonical_base64": lambda value: (
            _canonical_base64(value)
        ),
        "expected_base_leaf_hash": _hex64,
        "expected_base_checkpoint_signed_payload_base64": lambda value: (
            _canonical_base64(value)
        ),
        "expected_base_checkpoint_signature_base64": lambda value: (
            _canonical_base64(value, SIGNATURE_BYTES)
        ),
        "expected_base_checkpoint_digest": _hex64,
        "expected_base_root_hash": _hex64,
    }
    for field, predicate in anchor_specs.items():
        if not predicate(fixture[field]):
            _fixture_error(field)

    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        _fixture_error("cases")
    case_ids: set[str] = set()
    verification_inputs: set[bytes] = set()
    referenced = {
        "checkpoint_variants": {"base"},
        "verifier_checkpoint_variants": {"base"},
        "inclusion_path_variants": {"base"},
        "consistency_path_variants": {"base"},
    }
    ref_fields = {
        "checkpoint_ref": "checkpoint_variants",
        "verifier_checkpoint_ref": "verifier_checkpoint_variants",
        "inclusion_path_ref": "inclusion_path_variants",
        "consistency_path_ref": "consistency_path_variants",
    }
    allowed_case_fields = _CASE_REQUIRED_FIELDS | _CASE_OPTIONAL_FIELDS
    for case_index, case in enumerate(cases):
        if (
            not isinstance(case, dict)
            or not _CASE_REQUIRED_FIELDS.issubset(case)
            or not set(case).issubset(allowed_case_fields)
        ):
            _fixture_error(f"cases[{case_index}] fields")
        case_id = case["id"]
        if not _non_empty_string(case_id) or case_id in case_ids:
            _fixture_error(f"cases[{case_index}].id")
        case_ids.add(case_id)
        _validate_expected(case["expected"], case_index)

        for ref_field, group_name in ref_fields.items():
            if ref_field not in case:
                continue
            ref = case[ref_field]
            if (
                not _non_empty_string(ref)
                or ref not in fixture[group_name]
            ):
                _fixture_error(f"cases[{case_index}].{ref_field}")
            referenced[group_name].add(ref)

        peer_refs = case.get("peer_checkpoint_refs")
        if peer_refs is not None:
            if (
                not isinstance(peer_refs, list)
                or not peer_refs
                or not all(
                    _non_empty_string(ref)
                    and ref in fixture["checkpoint_variants"]
                    for ref in peer_refs
                )
                or len(set(peer_refs)) != len(peer_refs)
            ):
                _fixture_error(
                    f"cases[{case_index}].peer_checkpoint_refs"
                )
            referenced["checkpoint_variants"].update(peer_refs)

        mutations = case.get("mutations", [])
        if not isinstance(mutations, list):
            _fixture_error(f"cases[{case_index}].mutations")
        mutation_paths: set[str] = set()
        candidate = _case_bundle(
            fixture,
            {key: value for key, value in case.items() if key != "mutations"},
        )
        for mutation_index, mutation in enumerate(mutations):
            if not _exact_dict(mutation, _MUTATION_FIELDS):
                _fixture_error(
                    f"cases[{case_index}].mutations[{mutation_index}]"
                )
            path = mutation["path"]
            if path in mutation_paths:
                _fixture_error(f"cases[{case_index}] duplicate mutation path")
            mutation_paths.add(path)
            _set_path(candidate, path, mutation["value"])

        verification_input = canonical_bytes(
            {
                "bundle": candidate,
                "now_ms": fixture["base_now_ms"],
            }
        )
        if verification_input in verification_inputs:
            _fixture_error(f"cases[{case_index}] duplicate verification input")
        verification_inputs.add(verification_input)

    for group_name, names in referenced.items():
        if names != set(fixture[group_name]):
            _fixture_error(f"unused {group_name}")


def load_fixture(path: str | Path) -> dict[str, Any]:
    value = strict_loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _fixture_error("fixture root")
    return value


def _result_dict(result: Any) -> dict[str, Any]:
    value = asdict(result)
    value["reason_codes"] = list(value["reason_codes"])
    return value


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
        bundle = _case_bundle(fixture, case)
        actual = _result_dict(
            verify_transparency_log(
                bundle,
                now_ms=fixture["base_now_ms"],
            )
        )
        expected = case["expected"]
        cases.append(
            {
                "id": case["id"],
                "actual": actual,
                "expected": expected,
                "passed": actual == expected,
            }
        )

    base = fixture["base_bundle"]
    entry_bytes = canonical_bytes(base["entry"])
    checkpoint_payload = signed_checkpoint_payload(base["checkpoint"])
    parity = {
        "entry_canonical_base64": base64.b64encode(entry_bytes).decode("ascii"),
        "entry_canonical_matches_expected": (
            base64.b64encode(entry_bytes).decode("ascii")
            == fixture["expected_base_entry_canonical_base64"]
        ),
        "leaf_hash": merkle_leaf_hash(base["entry"]),
        "leaf_hash_matches_expected": (
            merkle_leaf_hash(base["entry"])
            == fixture["expected_base_leaf_hash"]
        ),
        "checkpoint_signed_payload_base64": base64.b64encode(
            checkpoint_payload
        ).decode("ascii"),
        "checkpoint_signed_payload_matches_expected": (
            base64.b64encode(checkpoint_payload).decode("ascii")
            == fixture[
                "expected_base_checkpoint_signed_payload_base64"
            ]
        ),
        "checkpoint_signature_matches_expected": (
            base["checkpoint"]["signature"]
            == fixture["expected_base_checkpoint_signature_base64"]
        ),
        "checkpoint_digest": checkpoint_digest(base["checkpoint"]),
        "checkpoint_digest_matches_expected": (
            checkpoint_digest(base["checkpoint"])
            == fixture["expected_base_checkpoint_digest"]
        ),
        "root_hash_matches_expected": (
            base["checkpoint"]["root_hash"]
            == fixture["expected_base_root_hash"]
        ),
    }

    passed = sum(1 for case in cases if case["passed"])
    parity_passed = all(
        value is True
        for key, value in parity.items()
        if key.endswith("_matches_expected")
    )
    all_passed = (
        passed == len(cases)
        and parity_passed
        and any(case["actual"]["valid"] for case in cases)
    )
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "canonical_profile": CANONICAL_PROFILE,
        "cases": cases,
        "parity": parity,
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "all_passed": all_passed,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify VTL v0.14 transparency-log proof vectors"
    )
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)

    result = run_fixture(load_fixture(args.fixture))
    if args.compact:
        serialized_public_evidence = json.dumps(
            result,
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
        )
    else:
        serialized_public_evidence = json.dumps(
            result,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
    # Public conformance evidence only; no private log signing key is loaded.
    sys.stdout.buffer.write(serialized_public_evidence.encode("utf-8") + b"\n")
    return 0 if result["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
