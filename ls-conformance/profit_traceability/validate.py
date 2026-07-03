#!/usr/bin/env python3
"""Validate Profit Traceability V0 bundles."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: jsonschema with date-time format support. "
        "Install requirements.txt before validation."
    ) from exc


class ProfitTraceValidationError(ValueError):
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
        raise ProfitTraceValidationError(message)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_semantics(bundle: dict[str, Any]) -> None:
    product = bundle["product"]
    signal = bundle["economicSignal"]
    candidate = bundle["candidate"]
    decision = bundle["decision"]
    evidence = bundle["businessEvidence"]
    outcome = bundle.get("businessOutcome")
    economics = bundle.get("unitEconomics")
    record = bundle.get("record")
    snapshot = bundle["snapshot"]

    require(
        product["productId"] in candidate["sourceProductRefs"],
        "candidate.sourceProductRefs must include product.productId",
    )
    require(
        signal["id"] in candidate["signalRefs"],
        "candidate.signalRefs must include economicSignal.id",
    )
    require(
        candidate["contentDigest"] == canonical_digest(candidate),
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

    baseline = candidate["baseline"]
    if baseline["status"] == "UNKNOWN":
        require(
            baseline["value"] is None,
            "UNKNOWN baseline must not contain a measured value",
        )
    else:
        require(
            baseline["value"] is not None,
            "MEASURED baseline requires a numeric value",
        )

    if decision["verdict"] == "APPROVE_EXPERIMENT":
        require(
            decision["independence"]["isIndependent"] is True,
            "approved economic experiments require an independent decision",
        )
        require(
            baseline["status"] == "MEASURED",
            "approved economic experiments require a measured baseline",
        )
    elif decision["verdict"] == "REQUEST_MORE_EVIDENCE":
        require(record is None, "REQUEST_MORE_EVIDENCE must not create a record")
        require(
            outcome is None,
            "REQUEST_MORE_EVIDENCE must not create a businessOutcome",
        )
        require(
            economics is None,
            "REQUEST_MORE_EVIDENCE must not create unitEconomics",
        )
    elif decision["verdict"] == "REJECT":
        require(
            record is not None,
            "REJECT decision requires a durable REJECTED record",
        )

    evidence_by_id = {item["id"]: item for item in evidence}
    require(
        len(evidence_by_id) == len(evidence),
        "business evidence IDs must be unique",
    )

    if outcome is not None:
        require(
            outcome["candidateRef"] == candidate["id"],
            "businessOutcome.candidateRef does not reference candidate.id",
        )
        missing = set(outcome["evidenceRefs"]) - set(evidence_by_id)
        require(
            not missing,
            f"businessOutcome references missing evidence: {sorted(missing)}",
        )
        require(
            outcome["currency"] == candidate["currency"],
            "businessOutcome currency must match candidate currency",
        )
        require(
            parse_datetime(outcome["windowStart"])
            < parse_datetime(outcome["windowEnd"]),
            "businessOutcome windowStart must be before windowEnd",
        )
        if outcome["status"] == "CONFIRMED":
            require(
                bool(outcome["evidenceRefs"]),
                "CONFIRMED businessOutcome requires evidence",
            )
            outcome_kinds = {
                evidence_by_id[evidence_id]["kind"]
                for evidence_id in outcome["evidenceRefs"]
            }
            require(
                bool(outcome_kinds & {"analytics", "manual_count"}),
                "CONFIRMED businessOutcome requires attribution evidence",
            )
            require(
                bool(outcome_kinds & {"pos", "receipt"}),
                "CONFIRMED businessOutcome requires revenue evidence",
            )

    if economics is not None:
        require(outcome is not None, "unitEconomics requires businessOutcome")
        require(
            economics["outcomeRef"] == outcome["id"],
            "unitEconomics.outcomeRef does not match businessOutcome.id",
        )
        missing = set(economics["evidenceRefs"]) - set(evidence_by_id)
        require(
            not missing,
            f"unitEconomics references missing evidence: {sorted(missing)}",
        )
        require(
            economics["currency"] == candidate["currency"] == outcome["currency"],
            "candidate, businessOutcome, and unitEconomics currencies must match",
        )
        monetary_fields = (
            "attributableRevenue",
            "variableCosts",
            "acquisitionCosts",
            "experimentCosts",
            "netContribution",
        )
        for field in monetary_fields:
            require(
                math.isfinite(economics[field]),
                f"unitEconomics.{field} must be finite",
            )
        require(
            math.isclose(
                economics["attributableRevenue"],
                outcome["attributableRevenue"],
                abs_tol=0.01,
            ),
            "unitEconomics attributableRevenue must match businessOutcome",
        )
        expected_contribution = (
            economics["attributableRevenue"]
            - economics["variableCosts"]
            - economics["acquisitionCosts"]
            - economics["experimentCosts"]
        )
        require(
            math.isclose(
                economics["netContribution"], expected_contribution, abs_tol=0.01
            ),
            "unitEconomics netContribution does not match net-contribution.v0",
        )
        if economics["status"] == "CONFIRMED":
            require(
                outcome["status"] == "CONFIRMED",
                "CONFIRMED unitEconomics requires CONFIRMED businessOutcome",
            )
            require(
                bool(economics["evidenceRefs"]),
                "CONFIRMED unitEconomics requires cost evidence",
            )
            economics_kinds = {
                evidence_by_id[evidence_id]["kind"]
                for evidence_id in economics["evidenceRefs"]
            }
            cost_requirements = (
                ("includeVariableCosts", "variableCosts", "variable_cost"),
                ("includeAcquisitionCosts", "acquisitionCosts", "acquisition_cost"),
                ("includeExperimentCosts", "experimentCosts", "experiment_cost"),
            )
            for include_flag, value_field, evidence_kind in cost_requirements:
                if candidate["costModel"][include_flag]:
                    require(
                        evidence_kind in economics_kinds,
                        f"CONFIRMED unitEconomics requires {evidence_kind} evidence",
                    )
                else:
                    require(
                        math.isclose(economics[value_field], 0, abs_tol=0.01),
                        f"unitEconomics.{value_field} must be zero when excluded",
                    )

    if record is not None:
        require(
            record["decisionRef"] == decision["id"],
            "record.decisionRef does not reference decision.id",
        )

        experiment_statuses = {
            "EXPERIMENT_APPROVED",
            "MEASURING",
            "SCALE",
            "STOP",
            "PIVOT",
        }
        if record["status"] in experiment_statuses:
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

        if "businessOutcomeRef" in record:
            require(outcome is not None, "record references missing businessOutcome")
            require(
                record["businessOutcomeRef"] == outcome["id"],
                "record.businessOutcomeRef does not match businessOutcome.id",
            )
        if "unitEconomicsRef" in record:
            require(economics is not None, "record references missing unitEconomics")
            require(
                record["unitEconomicsRef"] == economics["id"],
                "record.unitEconomicsRef does not match unitEconomics.id",
            )

        if record["status"] == "SCALE":
            require(outcome is not None, "SCALE requires businessOutcome")
            require(economics is not None, "SCALE requires unitEconomics")
            require(
                "businessOutcomeRef" in record,
                "SCALE requires businessOutcomeRef",
            )
            require(
                "unitEconomicsRef" in record,
                "SCALE requires unitEconomicsRef",
            )
            require(
                record["businessOutcomeRef"] == outcome["id"],
                "SCALE must bind the exact businessOutcome",
            )
            require(
                record["unitEconomicsRef"] == economics["id"],
                "SCALE must bind the exact unitEconomics",
            )
            require(
                outcome["status"] == "CONFIRMED",
                "SCALE requires CONFIRMED businessOutcome",
            )
            require(
                economics["status"] == "CONFIRMED",
                "SCALE requires CONFIRMED unitEconomics",
            )
            require(
                economics["netContribution"] > 0,
                "SCALE requires positive confirmed netContribution",
            )

    record_ids = {record["id"]} if record else set()
    source_refs = set(snapshot["sourceRecordRefs"])
    active_refs = set(snapshot["activeRecordRefs"])
    unresolved_refs = set(snapshot["unresolvedCandidateRefs"])

    require(
        not (source_refs - record_ids),
        "snapshot references unknown source records",
    )
    require(
        not (active_refs - record_ids),
        "snapshot references unknown active records",
    )

    if record is not None:
        require(
            record["id"] in source_refs,
            "snapshot.sourceRecordRefs must include record.id",
        )
        is_active = record["status"] in {"MEASURING", "SCALE"}
        require(
            (record["id"] in active_refs) == is_active,
            "snapshot.activeRecordRefs must exactly reflect active record status",
        )
        is_unresolved = record["status"] in {"EXPERIMENT_APPROVED", "MEASURING"}
        require(
            (candidate["id"] in unresolved_refs) == is_unresolved,
            "snapshot.unresolvedCandidateRefs must exactly reflect candidate resolution",
        )
    else:
        require(
            not source_refs and not active_refs,
            "snapshot cannot reference profit records when record is absent",
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
    errors = sorted(validator.iter_errors(bundle), key=lambda item: list(item.path))
    if errors:
        details = "\n".join(
            f"- {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ProfitTraceValidationError(
            f"JSON Schema validation failed:\n{details}"
        )
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
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        ProfitTraceValidationError,
    ) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
