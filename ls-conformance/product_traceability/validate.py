#!/usr/bin/env python3
"""Validate Product Traceability V0 bundles.

JSON Schema checks structure. This module additionally verifies graph
references and governance invariants that JSON Schema alone cannot express.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: jsonschema. Install with: pip install jsonschema"
    ) from exc


class TraceValidationError(ValueError):
    pass


def canonical_digest(candidate: dict[str, Any]) -> str:
    content = dict(candidate)
    content.pop("contentDigest", None)
    encoded = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TraceValidationError(message)


def validate_semantics(bundle: dict[str, Any]) -> None:
    signal = bundle["signal"]
    candidate = bundle["candidate"]
    decision = bundle["decision"]
    implementation = bundle.get("implementation")
    evidence = bundle["evidence"]
    outcome = bundle.get("outcome")
    record = bundle.get("record")
    snapshot = bundle["snapshot"]

    require(
        signal["id"] in candidate["signalRefs"],
        "candidate.signalRefs must include the bundle signal",
    )

    expected_digest = canonical_digest(candidate)
    require(
        candidate["contentDigest"] == expected_digest,
        "candidate.contentDigest does not match canonical candidate content",
    )
    require(
        decision["candidateRef"] == candidate["id"],
        "decision.candidateRef does not reference candidate.id",
    )
    require(
        decision["candidateDigest"] == candidate["contentDigest"],
        "decision.candidateDigest does not bind the exact candidate content",
    )

    if decision["verdict"] == "APPROVE_EXPERIMENT":
        require(
            decision["independence"]["isIndependent"] is True,
            "approved experiments require an independent decision",
        )

    evidence_by_id = {item["id"]: item for item in evidence}
    require(len(evidence_by_id) == len(evidence), "evidence IDs must be unique")

    if outcome is not None:
        require(
            outcome["candidateRef"] == candidate["id"],
            "outcome.candidateRef does not reference candidate.id",
        )
        missing = set(outcome["evidenceRefs"]) - set(evidence_by_id)
        require(not missing, f"outcome references missing evidence: {sorted(missing)}")

    if implementation is not None:
        require(
            len(implementation["headSha"]) == 40,
            "implementation must bind an exact 40-character head SHA",
        )

    if record is not None:
        require(
            record["decisionRef"] == decision["id"],
            "record.decisionRef does not reference decision.id",
        )

        if "implementationRef" in record:
            require(implementation is not None, "record references missing implementation")
            require(
                record["implementationRef"] == implementation["id"],
                "record.implementationRef does not match implementation.id",
            )

        if "outcomeRef" in record:
            require(outcome is not None, "record references missing outcome")
            require(
                record["outcomeRef"] == outcome["id"],
                "record.outcomeRef does not match outcome.id",
            )

        if record["status"] == "ADOPTED":
            require(implementation is not None, "ADOPTED requires implementation")
            require(
                implementation["status"] == "VERIFIED",
                "ADOPTED requires VERIFIED implementation",
            )
            require(outcome is not None, "ADOPTED requires outcome")
            require(
                outcome["status"] == "CONFIRMED",
                "ADOPTED requires CONFIRMED outcome",
            )
            require(bool(outcome["evidenceRefs"]), "ADOPTED requires outcome evidence")

    record_ids = {record["id"]} if record else set()
    unknown_sources = set(snapshot["sourceRecordRefs"]) - record_ids
    require(
        not unknown_sources,
        f"snapshot references missing source records: {sorted(unknown_sources)}",
    )
    unknown_active = set(snapshot["activeRecordRefs"]) - record_ids
    require(
        not unknown_active,
        f"snapshot references missing active records: {sorted(unknown_active)}",
    )

    if snapshot["activeRecordRefs"]:
        require(record is not None, "active snapshot requires a record")
        require(
            record["status"] in {"EXPERIMENT_ACTIVE", "ADOPTED"},
            "only EXPERIMENT_ACTIVE or ADOPTED records may be active",
        )

    unresolved = set(snapshot["unresolvedCandidateRefs"])
    if candidate["id"] in unresolved:
        require(
            record is None
            or record["status"] not in {"ADOPTED", "REJECTED", "ROLLED_BACK"},
            "resolved candidate cannot remain unresolved in snapshot",
        )

    if decision["verdict"] == "REQUEST_MORE_EVIDENCE":
        require(
            record is None,
            "REQUEST_MORE_EVIDENCE must not fabricate a durable product record",
        )


def validate_file(bundle_path: Path, schema_path: Path) -> None:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(bundle), key=lambda err: list(err.path))
    if errors:
        details = "\n".join(
            f"- {'/'.join(map(str, err.path)) or '<root>'}: {err.message}"
            for err in errors
        )
        raise TraceValidationError(f"JSON Schema validation failed:\n{details}")

    validate_semantics(bundle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--schema", type=Path, default=Path(__file__).with_name("schema.json")
    )
    args = parser.parse_args()

    try:
        validate_file(args.bundle, args.schema)
    except (OSError, json.JSONDecodeError, TraceValidationError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1

    print(f"VALID: {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
