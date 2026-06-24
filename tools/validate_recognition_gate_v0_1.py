#!/usr/bin/env python3
"""Deterministic conformance runner for LS Recognition Gate v0.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "fixtures" / "recognition-gate" / "v0.1.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "recognition-gate-v0.1-result.json"
GATE_VERSION = "ls-recognition-gate-v0.1"
DECISIONS = {"ALLOW", "DEFER", "ESCALATE"}
OUTPUT_TYPES = {"answer", "tool_call", "clarification_request", "provisional_summary"}


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return value


def _valid_resolution(
    recognition_id: str,
    evidence: list[dict[str, Any]],
    context: dict[str, Any],
) -> tuple[bool, bool]:
    """Return (resolved, binding_mismatch_seen)."""
    mismatch = False
    for item in evidence:
        resolves = item.get("resolves")
        if not isinstance(resolves, list) or recognition_id not in resolves:
            continue
        if item.get("status") != "verified":
            continue
        if (
            item.get("intent_digest") == context.get("intent_digest")
            and item.get("target_state_digest") == context.get("target_state_digest")
        ):
            return True, mismatch
        mismatch = True
    return False, mismatch


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    context = case.get("context")
    candidate = case.get("candidate")
    recognitions = case.get("recognitions")
    evidence = case.get("evidence")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")
    if not isinstance(recognitions, list):
        raise ValueError("recognitions must be a list")
    if not isinstance(evidence, list):
        raise ValueError("evidence must be a list")

    output_type = _text(candidate.get("output_type"))
    if output_type not in OUTPUT_TYPES:
        raise ValueError(f"unsupported output_type: {output_type}")
    dependencies = candidate.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError("candidate dependencies must be a list")
    dependencies = {_text(value) for value in dependencies}
    dependencies.discard(None)

    relevant = []
    for recognition in recognitions:
        if not isinstance(recognition, dict):
            raise ValueError("recognition must be an object")
        if recognition.get("blocking") is not True:
            continue
        dependency_id = _text(recognition.get("dependency_id"))
        if dependency_id in dependencies:
            relevant.append(recognition)

    unresolved = []
    resolved_count = 0
    mismatch_seen = False
    for recognition in relevant:
        recognition_id = _text(recognition.get("recognition_id"))
        if recognition_id is None:
            raise ValueError("recognition_id is required")
        resolved, mismatch = _valid_resolution(recognition_id, evidence, context)
        mismatch_seen = mismatch_seen or mismatch
        if resolved:
            resolved_count += 1
        else:
            unresolved.append(recognition)

    if unresolved:
        user_required = any(
            (item.get("resolution") or {}).get("source") == "user"
            for item in unresolved
            if isinstance(item.get("resolution"), dict)
        )
        if user_required and output_type == "clarification_request":
            decision = "ESCALATE"
            reasons = ["USER_INPUT_REQUIRED"]
            disposition = "EMIT_CLARIFICATION"
            dependent_output_authorized = False
            clarification_authorized = True
        else:
            decision = "DEFER"
            clarification_authorized = False
            dependent_output_authorized = False
            disposition = "WITHHOLD"
            if mismatch_seen:
                reasons = ["EVIDENCE_BINDING_MISMATCH"]
            elif any(item.get("kind") == "prerequisite_missing" for item in unresolved):
                reasons = ["PREREQUISITE_UNSATISFIED"]
            elif candidate.get("caveat_repeated") is True:
                reasons = ["CAVEAT_IS_NOT_RESOLUTION"]
            elif any(
                isinstance(item.get("resolution"), dict)
                and item["resolution"].get("source") == "tool"
                and item["resolution"].get("available") is True
                for item in unresolved
            ):
                reasons = ["RESOLUTION_TOOL_NOT_RUN"]
            else:
                reasons = ["BLOCKING_GAP_UNRESOLVED"]
    else:
        decision = "ALLOW"
        clarification_authorized = False
        dependent_output_authorized = output_type != "tool_call"
        disposition = "FORWARD_TO_ACTION_GATE" if output_type == "tool_call" else "EMIT_CANDIDATE"
        if relevant and resolved_count == len(relevant):
            reasons = ["BLOCKING_GAP_RESOLVED"]
        elif any(
            isinstance(item, dict) and item.get("blocking") is False
            for item in recognitions
        ) and candidate.get("provisional") is True:
            reasons = ["NON_BLOCKING_PROVISIONAL"]
        else:
            reasons = ["NO_BLOCKING_DEPENDENCY"]

    return {
        "decision": decision,
        "reason_codes": reasons,
        "terminal_disposition": disposition,
        "dependent_output_authorized": dependent_output_authorized,
        "clarification_authorized": clarification_authorized,
        "recognition_gate_passed": decision == "ALLOW",
        "execution_authorized": False,
    }


def validate(fixture: dict[str, Any]) -> dict[str, Any]:
    meta = fixture.get("_meta")
    if not isinstance(meta, dict):
        raise ValueError("_meta must be an object")
    if meta.get("gate_version") != GATE_VERSION:
        raise ValueError("gate_version mismatch")
    if meta.get("independent_contract") is not True:
        raise ValueError("fixture must declare independent_contract=true")

    raw_cases = fixture.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("cases must be a non-empty list")

    results = []
    seen: set[str] = set()
    decisions_seen: set[str] = set()
    reasons_seen: set[str] = set()
    for raw in raw_cases:
        if not isinstance(raw, dict):
            raise ValueError("case must be an object")
        name = _text(raw.get("case"))
        expected = raw.get("expected")
        if name is None or name in seen:
            raise ValueError("case names must be non-empty and unique")
        if not isinstance(expected, dict):
            raise ValueError(f"{name}: expected must be an object")
        seen.add(name)
        observed = evaluate(raw)
        errors = []
        if observed != expected:
            errors.append("observed decision differs from expected")
        if observed["execution_authorized"] is not False:
            errors.append("Recognition Gate authorized execution")
        if observed["decision"] not in DECISIONS:
            errors.append("unsupported decision")
        if observed["decision"] != "ALLOW" and observed["dependent_output_authorized"]:
            errors.append("blocked decision authorized dependent output")
        if observed["decision"] == "ESCALATE":
            if not observed["clarification_authorized"]:
                errors.append("escalation did not authorize clarification")
            if observed["dependent_output_authorized"]:
                errors.append("escalation authorized dependent output")
        decisions_seen.add(observed["decision"])
        reasons_seen.update(observed["reason_codes"])
        results.append({
            "case": name,
            "passed": not errors,
            "errors": errors,
            "observed": observed,
            "expected": expected,
        })

    required = {
        "missing_premise_dependent_answer",
        "resolution_tool_available_not_run",
        "resolved_current_context",
        "user_input_clarification",
        "nonblocking_provisional_output",
        "prerequisite_rule_unsatisfied",
        "wrong_intent_evidence_does_not_resolve",
        "unbound_blocking_gap_does_not_block_independent_output",
    }
    missing = sorted(required - seen)
    if missing:
        raise ValueError(f"missing required cases: {missing}")

    report = {
        "gate_version": GATE_VERSION,
        "inspiration": meta.get("inspiration"),
        "independent_contract": True,
        "cases_total": len(results),
        "cases_passed": sum(bool(item["passed"]) for item in results),
        "decisions_covered": sorted(decisions_seen),
        "reason_codes_covered": sorted(reasons_seen),
        "boundary": {
            "structured_recognition_is_authority": False,
            "free_form_caveat_is_resolution": False,
            "recognition_gate_authorizes_execution": False,
        },
        "results": results,
    }
    report["passed"] = (
        report["cases_passed"] == report["cases_total"]
        and decisions_seen == {"ALLOW", "DEFER", "ESCALATE"}
        and {
            "CAVEAT_IS_NOT_RESOLUTION",
            "RESOLUTION_TOOL_NOT_RUN",
            "BLOCKING_GAP_RESOLVED",
            "USER_INPUT_REQUIRED",
            "NON_BLOCKING_PROVISIONAL",
            "PREREQUISITE_UNSATISFIED",
            "EVIDENCE_BINDING_MISMATCH",
            "NO_BLOCKING_DEPENDENCY",
        }.issubset(reasons_seen)
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", nargs="?", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    report = validate(_load(args.fixture))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
