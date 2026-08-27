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
        "Missing dependency: jsonschema with format support. "
        "Install with: pip install 'jsonschema[format]'"
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
    elif decision["verdict"] == "REQUEST_MORE_EVIDENCE":
        require(
            record is None,
            "REQUEST_MORE_EVIDENCE must not fabricate a durable product record",
        )
        require(
            implementation is None,
            "REQUEST_MORE_EVIDENCE must not fabricate an implementation",
        )
        require(
            outcome is None,
            "REQUEST_MORE_EVIDENCE must not fabricate a product outcome",
        )
    elif decision["verdict"] == "REJECT":
        require(
            record is not None,
            "REJECT decision requires a durable REJECTED record",
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

        approved_statuses = {
            "EXPERIMENT_APPROVED",
            "EXPERIMENT_ACTIVE",
            "ADOPTED",
        }
        if record["status"] in approved_statuses:
            require(
                decision["verdict"] == "APPROVE_EXPERIMENT",
                f"{record['status']} requires APPROVE_EXPERIMENT decision",
            )
        if decision["verdict"] == "REJECT":
            require(
                record["status"] == "REJECTED",
                "REJECT decision requires a REJECTED record",
            )
        if record["status"] == "REJECTED":
            require(
                decision["verdict"] == "REJECT",
                "REJECTED record requires a REJECT decision",
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
                "implementationRef" in record,
                "ADOPTED requires implementationRef",
            )
            require(
                record["implementationRef"] == implementation["id"],
                "ADOPTED implementationRef must match implementation.id",
            )
            require(
                implementation["status"] == "VERIFIED",
                "ADOPTED requires VERIFIED implementation",
            )
            require(outcome is not None, "ADOPTED requires outcome")
            require("outcomeRef" in record, "ADOPTED requires outcomeRef")
            require(
                record["outcomeRef"] == outcome["id"],
                "ADOPTED outcomeRef must match outcome.id",
            )
            require(
                outcome["status"] == "CONFIRMED",
                "ADOPTED requires CONFIRMED outcome",
            )
            require(bool(outcome["evidenceRefs"]), "ADOPTED requires outcome evidence")

    record_ids = {record["id"]} if record else set()
    source_refs = set(snapshot["sourceRecordRefs"])
    active_refs = set(snapshot["activeRecordRefs"])
    unresolved_refs = set(snapshot["unresolvedCandidateRefs"])

    unknown_sources = source_refs - record_ids
    require(
        not unknown_sources,
        f"snapshot references missing source records: {sorted(unknown_sources)}",
    )
    unknown_active = active_refs - record_ids
    require(
        not unknown_active,
        f"snapshot references missing active records: {sorted(unknown_active)}",
    )

    if record is not None:
        require(
            record["id"] in source_refs,
            "snapshot.sourceRecordRefs must include record.id",
        )

        is_active = record["status"] in {"EXPERIMENT_ACTIVE", "ADOPTED"}
        require(
            (record["id"] in active_refs) == is_active,
            "snapshot.activeRecordRefs must exactly reflect active record status",
        )

        is_unresolved = record["status"] in {
            "EXPERIMENT_APPROVED",
            "EXPERIMENT_ACTIVE",
        }
        require(
            (candidate["id"] in unresolved_refs) == is_unresolved,
            "snapshot.unresolvedCandidateRefs must exactly reflect candidate resolution",
        )
    else:
        require(
            not source_refs and not active_refs,
            "snapshot cannot reference product records when record is absent",
        )

    if decision["verdict"] == "REQUEST_MORE_EVIDENCE":
        require(
            candidate["id"] in unresolved_refs,
            "REQUEST_MORE_EVIDENCE candidate must remain unresolved",
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
