#!/usr/bin/env python3
"""Validate Profit Measurement Readiness V0 bundles."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    raise SystemExit(
        "Missing dependency: jsonschema with date-time format support. "
        "Install the parent profit_traceability requirements."
    ) from exc


class MeasurementReadinessValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MeasurementReadinessValidationError(message)


def validate_semantics(bundle: dict[str, Any]) -> None:
    candidate_ref = bundle["economicCandidateRef"]
    binding = bundle["decisionBinding"]
    plan = bundle["measurementPlan"]
    implementation = bundle.get("implementation")
    evidence = bundle["evidence"]
    readiness = bundle["readinessDecision"]
    snapshot = bundle["snapshot"]

    require(
        binding["candidateRef"] == candidate_ref,
        "decisionBinding.candidateRef must match economicCandidateRef",
    )
    require(
        binding["verdict"] == "REQUEST_MORE_EVIDENCE",
        "measurement readiness must be governed by REQUEST_MORE_EVIDENCE",
    )
    require(
        plan["tokenContract"]["collectsPII"] is False,
        "measurement token must not collect PII",
    )
    require(
        plan["tokenContract"]["ttlHours"] == plan["attributionWindowHours"],
        "token TTL must equal the attribution window",
    )
    require(
        "visit_intent_created" in plan["webContract"]["requiredEvents"],
        "web contract must include visit_intent_created",
    )

    required_pos_fields = {
        "order_id",
        "ordered_at",
        "campaign_token",
        "gross_revenue",
        "currency",
        "variable_cost",
    }
    missing_pos_fields = required_pos_fields - set(plan["posContract"]["requiredFields"])
    require(
        not missing_pos_fields,
        f"POS contract is missing required fields: {sorted(missing_pos_fields)}",
    )
    require(
        plan["posContract"]["joinKey"] == plan["tokenContract"]["joinKey"],
        "web token and POS contracts must use the same join key",
    )

    require(
        readiness["planRef"] == plan["id"],
        "readinessDecision.planRef must match measurementPlan.id",
    )

    evidence_by_id = {item["id"]: item for item in evidence}
    require(len(evidence_by_id) == len(evidence), "evidence IDs must be unique")
    missing_evidence = set(readiness["evidenceRefs"]) - set(evidence_by_id)
    require(
        not missing_evidence,
        f"readinessDecision references missing evidence: {sorted(missing_evidence)}",
    )
    evidence_kinds = {
        evidence_by_id[evidence_id]["kind"] for evidence_id in readiness["evidenceRefs"]
    }

    if evidence:
        require(implementation is not None, "evidence requires an implementation")
        for item in evidence:
            require(
                item["implementationRef"] == implementation["id"],
                "evidence.implementationRef must match implementation.id",
            )
            require(
                item["headSha"] == implementation["headSha"],
                "evidence.headSha must match the exact implementation headSha",
            )

    if plan["status"] == "INSTRUMENTATION_REQUIRED":
        require(
            readiness["status"] == "BLOCKED",
            "INSTRUMENTATION_REQUIRED plan must be BLOCKED",
        )
        require(bool(plan["blockers"]), "blocked plan requires explicit blockers")
        require(
            implementation is None or implementation["status"] != "VERIFIED",
            "INSTRUMENTATION_REQUIRED cannot have a VERIFIED implementation",
        )
    else:
        require(
            implementation is not None,
            f"{plan['status']} requires an implementation",
        )
        require(
            implementation["status"] == "VERIFIED",
            f"{plan['status']} requires VERIFIED implementation",
        )
        require(
            readiness.get("implementationRef") == implementation["id"],
            f"{plan['status']} requires readinessDecision.implementationRef",
        )
        require(
            not plan["blockers"],
            f"{plan['status']} requires an empty blockers list",
        )
        require(
            {"instrumentation_test", "join_integrity"}.issubset(evidence_kinds),
            f"{plan['status']} requires instrumentation_test and join_integrity evidence",
        )

    if plan["status"] == "READY_FOR_BASELINE":
        require(
            readiness["status"] == "READY_FOR_BASELINE",
            "READY_FOR_BASELINE plan requires matching readiness decision",
        )
    elif plan["status"] == "BASELINE_COLLECTING":
        require(
            readiness["status"] == "READY_FOR_BASELINE",
            "BASELINE_COLLECTING must remain readiness READY_FOR_BASELINE",
        )
    elif plan["status"] == "BASELINE_COMPLETE":
        require(
            readiness["status"] == "BASELINE_COMPLETE",
            "BASELINE_COMPLETE plan requires matching readiness decision",
        )
        require(
            {"baseline_export", "cost_source"}.issubset(evidence_kinds),
            "BASELINE_COMPLETE requires baseline_export and cost_source evidence",
        )

    plan_id = plan["id"]
    source_refs = set(snapshot["sourcePlanRefs"])
    active_refs = set(snapshot["activePlanRefs"])
    blocked_refs = set(snapshot["blockedPlanRefs"])

    known_plan_refs = {plan_id}
    require(
        not (source_refs - known_plan_refs),
        "snapshot.sourcePlanRefs contains unknown plans",
    )
    require(
        not (active_refs - known_plan_refs),
        "snapshot.activePlanRefs contains unknown plans",
    )
    require(
        not (blocked_refs - known_plan_refs),
        "snapshot.blockedPlanRefs contains unknown plans",
    )
    require(plan_id in source_refs, "snapshot.sourcePlanRefs must include plan.id")
    is_active = plan["status"] in {
        "READY_FOR_BASELINE",
        "BASELINE_COLLECTING",
        "BASELINE_COMPLETE",
    }
    require(
        (plan_id in active_refs) == is_active,
        "snapshot.activePlanRefs must exactly reflect plan status",
    )
    is_blocked = readiness["status"] == "BLOCKED"
    require(
        (plan_id in blocked_refs) == is_blocked,
        "snapshot.blockedPlanRefs must exactly reflect readiness status",
    )


def validate_parent_binding(bundle: dict[str, Any], parent: dict[str, Any]) -> None:
    source = bundle["sourceProfitBundle"]
    binding = bundle["decisionBinding"]
    require(
        source["locator"]
        == "ls-conformance/profit_traceability/fixtures/robys_menu_to_visit.blocked.json",
        "sourceProfitBundle.locator must be the safe repo-relative parent fixture path",
    )
    require(
        source["bundleId"] == parent["bundleId"],
        "sourceProfitBundle.bundleId must match the parent profit bundle",
    )
    require(
        bundle["productRef"] == parent["product"]["productId"],
        "productRef must match the parent profit bundle product",
    )
    require(
        bundle["economicCandidateRef"] == parent["candidate"]["id"],
        "economicCandidateRef must match the parent candidate",
    )
    require(
        binding["decisionRef"] == parent["decision"]["id"],
        "decisionBinding.decisionRef must match the parent decision",
    )
    require(
        binding["candidateRef"]
        == parent["decision"]["candidateRef"]
        == parent["candidate"]["id"],
        "decisionBinding.candidateRef must match the parent candidate binding",
    )
    require(
        binding["candidateDigest"]
        == parent["decision"]["candidateDigest"]
        == parent["candidate"]["contentDigest"],
        "decisionBinding.candidateDigest must match the parent candidate digest",
    )
    require(
        binding["verdict"] == parent["decision"]["verdict"],
        "decisionBinding.verdict must match the parent decision verdict",
    )


def validate_file(
    bundle_path: Path,
    schema_path: Path,
    profit_bundle_path: Path | None = None,
) -> None:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if profit_bundle_path is None:
        profit_bundle_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "robys_menu_to_visit.blocked.json"
        )
    parent = json.loads(profit_bundle_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(bundle), key=lambda item: list(item.path))
    if errors:
        details = "\n".join(
            f"- {'/'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise MeasurementReadinessValidationError(
            f"JSON Schema validation failed:\n{details}"
        )
    validate_parent_binding(bundle, parent)
    validate_semantics(bundle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--schema", type=Path, default=Path(__file__).with_name("schema.json")
    )
    parser.add_argument(
        "--profit-bundle",
        type=Path,
        default=(
            Path(__file__).parent.parent
            / "fixtures"
            / "robys_menu_to_visit.blocked.json"
        ),
    )
    args = parser.parse_args()
    try:
        validate_file(args.bundle, args.schema, args.profit_bundle)
    except (OSError, json.JSONDecodeError, MeasurementReadinessValidationError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: {args.bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
