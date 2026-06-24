#!/usr/bin/env python3
"""Validate LS Evidence Gate v0.1 fixtures."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures" / "evidence-gate" / "manifest-v0.1.json"
OUTPUT = ROOT / "artifacts" / "evidence-gate-v0.1-result.json"
VERSION = "ls-evidence-gate-v0.1"
DECISIONS = {"ALLOW", "HOLD", "BLOCK", "ESCALATE"}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON object required")
    return value


def present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def verdict(case: dict[str, Any], decision: str, reason: str, eligible: bool = False) -> dict[str, Any]:
    handoff = case["handoff"]
    request = case["request"]
    refs = request.get("evidence_refs")
    if not isinstance(refs, list):
        refs = []
    return {
        "decision": decision,
        "reason_code": reason,
        "authorization_bundle_eligible": eligible,
        "execution_authorized": False,
        "candidate_digest": handoff.get("candidate_digest"),
        "intent_digest": handoff.get("intent_digest"),
        "target_state_digest": handoff.get("target_state_digest"),
        "recognition_result_ref": handoff.get("recognition_result_ref"),
        "evidence_refs": refs,
        "policy_id": request.get("policy_id"),
        "policy_version": request.get("policy_version"),
    }


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    handoff = case.get("handoff")
    request = case.get("request")
    policy = case.get("policy_context")
    if not all(isinstance(item, dict) for item in (handoff, request, policy)):
        raise ValueError("handoff, request, and policy_context must be objects")

    if handoff.get("execution_authorized") is not False:
        return verdict(case, "BLOCK", "UPSTREAM_EXECUTION_AUTHORITY_INVALID")
    if handoff.get("handoff_outcome") != "FORWARD_TO_EVIDENCE_GATE":
        return verdict(case, "BLOCK", "HANDOFF_NOT_ELIGIBLE")
    if not present(handoff.get("recognition_result_ref")):
        return verdict(case, "BLOCK", "RECOGNITION_RESULT_REF_MISSING")
    if request.get("candidate_digest") != handoff.get("candidate_digest"):
        return verdict(case, "BLOCK", "CANDIDATE_BINDING_MISMATCH")
    if (
        request.get("intent_digest") != handoff.get("intent_digest")
        or request.get("target_state_digest") != handoff.get("target_state_digest")
    ):
        return verdict(case, "BLOCK", "CONTEXT_BINDING_MISMATCH")
    if (
        request.get("policy_id") != policy.get("policy_id")
        or request.get("policy_version") != policy.get("policy_version")
    ):
        return verdict(case, "BLOCK", "POLICY_BINDING_MISMATCH")
    if request.get("causal_status") != "VALID":
        return verdict(case, "BLOCK", "CAUSAL_LINEAGE_INVALID")

    verifier = request.get("verifier_status")
    if verifier == "FAILED":
        return verdict(case, "BLOCK", "EVIDENCE_VERIFICATION_FAILED")
    if verifier != "VERIFIED":
        return verdict(case, "HOLD", "VERIFICATION_PENDING")

    refs = request.get("evidence_refs")
    if (
        not isinstance(refs, list)
        or not refs
        or any(not present(item) for item in refs)
        or not present(request.get("evidence_snapshot_digest"))
    ):
        return verdict(case, "HOLD", "EVIDENCE_MISSING")

    scope = request.get("scope")
    if not isinstance(scope, list) or not scope or any(not present(item) for item in scope):
        return verdict(case, "HOLD", "SCOPE_INCOMPLETE")
    if request.get("reversibility") not in {"REVERSIBLE", "IRREVERSIBLE"}:
        return verdict(case, "HOLD", "REVERSIBILITY_UNKNOWN")
    if request.get("approval_required") is True and not present(request.get("approval_ref")):
        return verdict(case, "ESCALATE", "HUMAN_APPROVAL_REQUIRED")
    return verdict(case, "ALLOW", "EVIDENCE_SUFFICIENT", eligible=True)


def validate(manifest_path: Path) -> dict[str, Any]:
    manifest = load(manifest_path)
    if manifest.get("contract_version") != VERSION:
        raise ValueError("manifest version mismatch")
    names = manifest.get("cases")
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise ValueError("manifest cases must be a non-empty unique list")

    results = []
    decisions: set[str] = set()
    reasons: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not name.endswith(".json"):
            raise ValueError(f"invalid case filename: {name!r}")
        case = load(manifest_path.parent / name)
        if case.get("contract_version") != VERSION:
            raise ValueError(f"{name}: version mismatch")
        expected = case.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(f"{name}: expected object required")

        observed = evaluate(case)
        errors = []
        if observed != expected:
            errors.append("observed result differs from expected")
        if observed["execution_authorized"] is not False:
            errors.append("gate authorized execution")
        if observed["decision"] != "ALLOW" and observed["authorization_bundle_eligible"]:
            errors.append("non-ALLOW became bundle eligible")
        if observed["decision"] == "ALLOW" and not observed["authorization_bundle_eligible"]:
            errors.append("ALLOW not bundle eligible")

        decisions.add(observed["decision"])
        reasons.add(observed["reason_code"])
        results.append({
            "case": case.get("case"),
            "file": name,
            "passed": not errors,
            "errors": errors,
            "observed": observed,
            "expected": expected,
        })

    required = {
        "EVIDENCE_SUFFICIENT",
        "EVIDENCE_MISSING",
        "VERIFICATION_PENDING",
        "CAUSAL_LINEAGE_INVALID",
        "HANDOFF_NOT_ELIGIBLE",
        "CANDIDATE_BINDING_MISMATCH",
        "POLICY_BINDING_MISMATCH",
        "HUMAN_APPROVAL_REQUIRED",
    }
    report = {
        "contract_version": VERSION,
        "cases_total": len(results),
        "cases_passed": sum(bool(item["passed"]) for item in results),
        "decisions_covered": sorted(decisions),
        "reason_codes_covered": sorted(reasons),
        "boundary": {
            "recognition_allow_is_evidence_allow": False,
            "evidence_allow_is_execution_authority": False,
            "non_allow_can_create_authorization_bundle": False,
            "caller_eligibility_is_trusted": False,
        },
        "results": results,
    }
    report["passed"] = (
        report["cases_passed"] == report["cases_total"]
        and decisions == DECISIONS
        and required.issubset(reasons)
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = validate(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
