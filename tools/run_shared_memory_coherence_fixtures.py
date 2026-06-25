#!/usr/bin/env python3
"""Run engine-neutral shared-memory coherence conformance fixtures."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "shared-memory-coherence"
VECTOR_PATH = FIXTURE_DIR / "vectors-v0.1.json"
PIN_PATH = FIXTURE_DIR / "vectors-v0.1.sha256"
OUTPUT_PATH = ROOT / "artifacts" / "shared-memory-coherence-conformance.json"

PROFILE = "shared-memory-coherence-v0.1"
SCHEMA_VERSION = "shared-memory-coherence-fixtures-v0.1"
SCOPE_RANK = {"agent": 0, "group": 1, "global": 2}
AUTHORITY_DEFAULTS = {
    "may_authorize_execution": False,
    "may_establish_consensus": False,
    "may_establish_human_approval": False,
    "may_establish_truth": False,
    "may_grant_permissions": False,
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _verify_pin() -> str:
    parts = PIN_PATH.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2 or parts[1] != VECTOR_PATH.name:
        raise ValueError("malformed vector digest pin")
    actual = hashlib.sha256(VECTOR_PATH.read_bytes()).hexdigest()
    if actual != parts[0]:
        raise ValueError(f"vector digest mismatch: actual={actual} pinned={parts[0]}")
    return actual


def _validate_document(document: dict[str, Any]) -> None:
    if document.get("profile") != PROFILE:
        raise ValueError("unsupported profile")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema version")
    if document.get("authority_defaults") != AUTHORITY_DEFAULTS:
        raise ValueError("authority defaults must remain all false")
    vectors = document.get("vectors")
    if not isinstance(vectors, list) or not vectors:
        raise ValueError("vectors must be a non-empty list")
    ids: set[str] = set()
    for vector in vectors:
        fixture_id = vector.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id or fixture_id in ids:
            raise ValueError("fixture ids must be unique non-empty strings")
        ids.add(fixture_id)
        query = vector.get("query")
        entries = vector.get("entries")
        expected = vector.get("expected")
        if not isinstance(query, dict) or not isinstance(entries, list) or not entries:
            raise ValueError(f"{fixture_id}: invalid query or entries")
        if not isinstance(expected, dict):
            raise ValueError(f"{fixture_id}: invalid expected result")
        precedence = query.get("scope_precedence")
        if not isinstance(precedence, list) or not precedence:
            raise ValueError(f"{fixture_id}: missing scope precedence")
        if len(precedence) != len(set(precedence)) or any(s not in SCOPE_RANK for s in precedence):
            raise ValueError(f"{fixture_id}: invalid scope precedence")
        memory_ids: set[str] = set()
        for entry in entries:
            memory_id = entry.get("memory_id")
            if not isinstance(memory_id, str) or not memory_id or memory_id in memory_ids:
                raise ValueError(f"{fixture_id}: invalid or duplicate memory id")
            memory_ids.add(memory_id)
            if entry.get("scope") not in SCOPE_RANK or entry.get("source_scope") not in SCOPE_RANK:
                raise ValueError(f"{fixture_id}: invalid scope")
            if entry.get("status") not in {"CLAIMED", "RATIFIED", "SUPERSEDED", "EXPIRED"}:
                raise ValueError(f"{fixture_id}: invalid status")


def _is_current(entry: dict[str, Any], now: datetime) -> bool:
    if entry["status"] in {"SUPERSEDED", "EXPIRED"}:
        return False
    valid_until = entry.get("valid_until")
    return valid_until is None or _parse_time(valid_until) > now


def _evaluate(vector: dict[str, Any]) -> dict[str, Any]:
    query = vector["query"]
    now = _parse_time(query["now"])
    matching = [
        entry
        for entry in vector["entries"]
        if entry["subject_id"] == query["subject_id"] and entry["key"] == query["key"]
    ]

    unauthorized = [
        entry
        for entry in matching
        if SCOPE_RANK[entry["scope"]] > SCOPE_RANK[entry["source_scope"]]
        and not entry.get("promotion_authorization_ref")
    ]
    if unauthorized:
        return _result(
            "REJECT", [], [entry["memory_id"] for entry in unauthorized], None,
            ["SCOPE_PROMOTION_UNAUTHORIZED"],
        )

    current = [entry for entry in matching if _is_current(entry, now)]
    inactive_ids = sorted(entry["memory_id"] for entry in matching if entry not in current)

    winning_scope = next(
        (scope for scope in query["scope_precedence"] if any(e["scope"] == scope for e in current)),
        None,
    )
    if winning_scope is None:
        return _result("ABSTAIN", [], inactive_ids, None, ["NO_CURRENT_MEMORY"])

    winners = [entry for entry in current if entry["scope"] == winning_scope]
    nonwinning_ids = sorted(entry["memory_id"] for entry in current if entry["scope"] != winning_scope)
    suppressed = sorted(set(inactive_ids + nonwinning_ids))

    missing_approval = [
        entry for entry in winners
        if entry["claim_type"] == "human_approval" and not entry.get("approval_ref")
    ]
    if missing_approval:
        return _result(
            "ABSTAIN", [], sorted(set(suppressed + [e["memory_id"] for e in missing_approval])),
            winning_scope, ["APPROVAL_REF_MISSING"],
        )

    canonical_values = {json.dumps(entry["value"], sort_keys=True) for entry in winners}
    if len(canonical_values) > 1:
        return _result(
            "CONFLICTED", [], suppressed, winning_scope,
            ["UNRESOLVED_CURRENT_CONTRADICTION"],
        )

    selected = sorted(entry["memory_id"] for entry in winners)
    ratified = all(entry["status"] == "RATIFIED" for entry in winners)

    if inactive_ids:
        reasons = ["SUPERSEDED_HISTORY_RETAINED"]
    elif nonwinning_ids:
        reasons = ["DECLARED_SCOPE_PRECEDENCE"]
    elif ratified:
        reasons = ["RATIFIED_CONTEXT_ONLY"]
    else:
        reasons = ["UNRATIFIED_SINGLE_WRITER"]

    return _result(
        "RETURN_RATIFIED" if ratified else "RETURN_CLAIM",
        selected,
        suppressed,
        winning_scope,
        reasons,
    )


def _result(
    decision: str,
    selected: list[str],
    suppressed: list[str],
    winning_scope: Optional[str],
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "authority_effects": dict(AUTHORITY_DEFAULTS),
        "decision": decision,
        "reason_codes": reasons,
        "selected_memory_ids": selected,
        "suppressed_memory_ids": suppressed,
        "winning_scope": winning_scope,
    }


def main() -> int:
    digest = _verify_pin()
    document = _load_json(VECTOR_PATH)
    _validate_document(document)

    results = []
    for vector in document["vectors"]:
        observed = _evaluate(vector)
        expected = {
            **vector["expected"],
            "authority_effects": dict(AUTHORITY_DEFAULTS),
        }
        results.append({
            "fixture_id": vector["fixture_id"],
            "observed": observed,
            "expected": expected,
            "passed": observed == expected,
        })

    report = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "vector_sha256": digest,
        "boundary": (
            "Shared memory returns provenance-bound context. It does not create truth, "
            "consensus, approval, permission, or execution authority."
        ),
        "results": results,
        "passed": all(result["passed"] for result in results),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
