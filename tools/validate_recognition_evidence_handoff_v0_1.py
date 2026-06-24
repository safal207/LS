#!/usr/bin/env python3
"""Validate the LS Recognition-to-Evidence handoff contract v0.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT / "fixtures" / "recognition-evidence-handoff" / "manifest-v0.1.json"
)
DEFAULT_OUTPUT = (
    ROOT / "artifacts" / "recognition-evidence-handoff-v0.1-result.json"
)
CONTRACT_VERSION = "ls-recognition-evidence-handoff-v0.1"
OUTCOMES = {
    "FORWARD_TO_EVIDENCE_GATE",
    "WITHHOLD",
    "ESCALATION_ONLY",
    "NO_ACTION_GATE_REQUIRED",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _withhold(reason: str) -> dict[str, Any]:
    return {
        "handoff_outcome": "WITHHOLD",
        "reason_code": reason,
        "evidence_gate_request_created": False,
        "candidate_emission_authorized": False,
        "clarification_authorized": False,
        "execution_authorized": False,
    }


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    context = case.get("context")
    result = case.get("recognition_result")
    candidate = case.get("candidate")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if not isinstance(result, dict):
        raise ValueError("recognition_result must be an object")
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")

    if _text(result.get("result_ref")) is None:
        return _withhold("RECOGNITION_RESULT_REF_MISSING")

    if result.get("execution_authorized") is not False:
        return _withhold("UPSTREAM_EXECUTION_AUTHORITY_INVALID")

    if result.get("candidate_digest") != candidate.get("candidate_digest"):
        return _withhold("CANDIDATE_BINDING_MISMATCH")

    if (
        result.get("intent_digest") != context.get("intent_digest")
        or result.get("target_state_digest") != context.get("target_state_digest")
    ):
        return _withhold("CONTEXT_BINDING_MISMATCH")

    decision = _text(result.get("decision"))
    claimed_eligible = case.get("claimed_downstream_eligible") is True

    if decision == "DEFER":
        if claimed_eligible:
            return _withhold("BLOCKED_RESULT_CANNOT_FORWARD")
        return _withhold("RECOGNITION_DEFERRED")

    if decision == "ESCALATE":
        if (
            candidate.get("candidate_type") == "clarification_request"
            and candidate.get("effectful") is False
            and result.get("terminal_disposition") == "EMIT_CLARIFICATION"
        ):
            return {
                "handoff_outcome": "ESCALATION_ONLY",
                "reason_code": "HUMAN_INPUT_REQUIRED",
                "evidence_gate_request_created": False,
                "candidate_emission_authorized": False,
                "clarification_authorized": True,
                "execution_authorized": False,
            }
        return _withhold("ESCALATION_CANDIDATE_INVALID")

    if decision != "ALLOW":
        return _withhold("UNSUPPORTED_RECOGNITION_DECISION")

    if result.get("recognition_gate_passed") is not True:
        return _withhold("INCONSISTENT_ALLOW_RESULT")

    effectful = candidate.get("effectful") is True
    if effectful:
        if result.get("terminal_disposition") != "FORWARD_TO_ACTION_GATE":
            return _withhold("TERMINAL_DISPOSITION_MISMATCH")
        return {
            "handoff_outcome": "FORWARD_TO_EVIDENCE_GATE",
            "reason_code": "CURRENT_ALLOW_FORWARDED",
            "evidence_gate_request_created": True,
            "candidate_emission_authorized": False,
            "clarification_authorized": False,
            "execution_authorized": False,
        }

    if result.get("terminal_disposition") != "EMIT_CANDIDATE":
        return _withhold("TERMINAL_DISPOSITION_MISMATCH")
    return {
        "handoff_outcome": "NO_ACTION_GATE_REQUIRED",
        "reason_code": "NON_EFFECTFUL_CANDIDATE",
        "evidence_gate_request_created": False,
        "candidate_emission_authorized": True,
        "clarification_authorized": False,
        "execution_authorized": False,
    }


def validate(manifest_path: Path) -> dict[str, Any]:
    manifest = _load(manifest_path)
    if manifest.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("manifest contract_version mismatch")
    names = manifest.get("cases")
    if not isinstance(names, list) or not names:
        raise ValueError("manifest cases must be a non-empty list")
    if len(names) != len(set(names)):
        raise ValueError("manifest case filenames must be unique")

    results = []
    outcomes: set[str] = set()
    reasons: set[str] = set()
    for filename in names:
        if not isinstance(filename, str) or not filename.endswith(".json"):
            raise ValueError(f"invalid case filename: {filename!r}")
        path = manifest_path.parent / filename
        case = _load(path)
        if case.get("contract_version") != CONTRACT_VERSION:
            raise ValueError(f"{filename}: contract_version mismatch")
        expected = case.get("expected")
        if not isinstance(expected, dict):
            raise ValueError(f"{filename}: expected must be an object")
        observed = evaluate(case)
        errors = []
        if observed != expected:
            errors.append("observed handoff differs from expected")
        if observed["execution_authorized"] is not False:
            errors.append("handoff authorized execution")
        if observed["handoff_outcome"] not in OUTCOMES:
            errors.append("unsupported handoff outcome")
        if (
            observed["handoff_outcome"] != "FORWARD_TO_EVIDENCE_GATE"
            and observed["evidence_gate_request_created"]
        ):
            errors.append("blocked outcome created evidence-gate request")
        if (
            observed["handoff_outcome"] == "ESCALATION_ONLY"
            and not observed["clarification_authorized"]
        ):
            errors.append("escalation did not authorize clarification")
        outcomes.add(observed["handoff_outcome"])
        reasons.add(observed["reason_code"])
        results.append(
            {
                "case": case.get("case"),
                "file": filename,
                "passed": not errors,
                "errors": errors,
                "observed": observed,
                "expected": expected,
            }
        )

    required_reasons = {
        "CURRENT_ALLOW_FORWARDED",
        "NON_EFFECTFUL_CANDIDATE",
        "RECOGNITION_DEFERRED",
        "HUMAN_INPUT_REQUIRED",
        "CANDIDATE_BINDING_MISMATCH",
        "CONTEXT_BINDING_MISMATCH",
        "RECOGNITION_RESULT_REF_MISSING",
        "BLOCKED_RESULT_CANNOT_FORWARD",
    }
    report = {
        "contract_version": CONTRACT_VERSION,
        "cases_total": len(results),
        "cases_passed": sum(bool(item["passed"]) for item in results),
        "outcomes_covered": sorted(outcomes),
        "reason_codes_covered": sorted(reasons),
        "boundary": {
            "recognition_allow_is_execution_authority": False,
            "blocked_result_can_create_evidence_request": False,
            "downstream_eligibility_claim_is_trusted": False,
        },
        "results": results,
    }
    report["passed"] = (
        report["cases_passed"] == report["cases_total"]
        and outcomes == OUTCOMES
        and required_reasons.issubset(reasons)
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = validate(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
