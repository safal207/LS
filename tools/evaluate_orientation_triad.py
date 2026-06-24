#!/usr/bin/env python3
"""Deterministic evaluator for LS Orientation Triad v0.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SEVERITY = {
    "COORDINATED_ACTION_CANDIDATE": 0,
    "ABSTAIN": 1,
    "WAIT": 2,
    "REVALIDATE": 3,
    "REJECT": 4,
}

REASON_ORDER = {
    "REJECT": [
        "UPSTREAM_AUTHORIZATION_INVARIANT_VIOLATION",
        "UNSUPPORTED_CENTER_VERSION",
        "WORKSPACE_BINDING_MISMATCH",
        "TRAJECTORY_BINDING_MISMATCH",
        "CONTINUATION_BINDING_MISMATCH",
        "RELATIONSHIP_BINDING_MISMATCH",
        "ACTOR_BINDING_MISMATCH",
        "ACTION_BINDING_MISMATCH",
        "TOC_REJECTED",
        "RTOC_REJECTED",
        "PATOC_REJECTED",
    ],
    "REVALIDATE": [
        "TOC_REVALIDATION_REQUIRED",
        "RTOC_REVALIDATION_REQUIRED",
        "PATOC_REVALIDATION_REQUIRED",
    ],
    "WAIT": ["PATOC_WAIT_REQUIRED"],
    "ABSTAIN": [
        "MISSING_CENTER_RESULT",
        "TOC_ABSTAINED",
        "RTOC_ABSTAINED",
        "PATOC_ABSTAINED",
    ],
}

EXPECTED_VERSIONS = {
    "toc": "temporal-orientation-v0.1",
    "rtoc": "relational-temporal-orientation-v0.1",
    "patoc": "precise-action-temporal-orientation-v0.1",
}

VERDICT_MAPPING = {
    "toc": {
        "RESUME": None,
        "REVALIDATE": ("REVALIDATE", "TOC_REVALIDATION_REQUIRED"),
        "ABSTAIN": ("ABSTAIN", "TOC_ABSTAINED"),
        "REJECT": ("REJECT", "TOC_REJECTED"),
    },
    "rtoc": {
        "RESUME": None,
        "REVALIDATE": ("REVALIDATE", "RTOC_REVALIDATION_REQUIRED"),
        "ABSTAIN": ("ABSTAIN", "RTOC_ABSTAINED"),
        "REJECT": ("REJECT", "RTOC_REJECTED"),
    },
    "patoc": {
        "EXECUTE_CANDIDATE": None,
        "WAIT": ("WAIT", "PATOC_WAIT_REQUIRED"),
        "REVALIDATE": ("REVALIDATE", "PATOC_REVALIDATION_REQUIRED"),
        "ABSTAIN": ("ABSTAIN", "PATOC_ABSTAINED"),
        "REJECT": ("REJECT", "PATOC_REJECTED"),
    },
}


def _result(
    fixture_id: str,
    verdict: str,
    reason_code: str,
    checks: list[dict[str, Any]],
    coordinated_action_digest: str | None = None,
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "triad_version": "orientation-triad-v0.1",
        "verdict": verdict,
        "reason_code": reason_code,
        "coordinated_action_digest": coordinated_action_digest,
        "execution_authorized": False,
        "downstream_gates_required": True,
        "checks": checks,
    }


def _choose_fault(faults: list[tuple[str, str]]) -> tuple[str, str]:
    if not faults:
        return "COORDINATED_ACTION_CANDIDATE", "TRIAD_ORIENTATION_VALID"

    highest = max(SEVERITY[verdict] for verdict, _ in faults)
    verdict = next(name for name, value in SEVERITY.items() if value == highest)
    reasons = {reason for candidate, reason in faults if candidate == verdict}
    for reason in REASON_ORDER[verdict]:
        if reason in reasons:
            return verdict, reason
    return verdict, sorted(reasons)[0]


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    fixture_id = case.get("fixture_id", "unknown")
    checks: list[dict[str, Any]] = []
    faults: list[tuple[str, str]] = []

    def fault(check: str, verdict: str, reason: str, **details: Any) -> None:
        checks.append({"check": check, "status": "failed", **details})
        faults.append((verdict, reason))

    def passed(check: str, **details: Any) -> None:
        checks.append({"check": check, "status": "passed", **details})

    center_names = ("toc", "rtoc", "patoc")
    missing_centers = [
        name for name in center_names if not isinstance(case.get(name), dict)
    ]
    if missing_centers:
        fault(
            "center_presence",
            "ABSTAIN",
            "MISSING_CENTER_RESULT",
            missing=missing_centers,
        )
        verdict, reason_code = _choose_fault(faults)
        return _result(fixture_id, verdict, reason_code, checks)
    passed("center_presence")

    for name, expected_version in EXPECTED_VERSIONS.items():
        observed_version = case[name].get("center_version")
        if observed_version != expected_version:
            fault(
                f"{name}_version",
                "REJECT",
                "UNSUPPORTED_CENTER_VERSION",
                observed=observed_version,
                expected=expected_version,
            )
        else:
            passed(f"{name}_version")

    for name in center_names:
        center = case[name]
        if (
            center.get("execution_authorized") is not False
            or center.get("downstream_gates_required") is not True
        ):
            fault(
                f"{name}_authorization_invariant",
                "REJECT",
                "UPSTREAM_AUTHORIZATION_INVARIANT_VIOLATION",
                execution_authorized=center.get("execution_authorized"),
                downstream_gates_required=center.get("downstream_gates_required"),
            )
        else:
            passed(f"{name}_authorization_invariant")

    toc = case["toc"]
    rtoc = case["rtoc"]
    patoc = case["patoc"]
    toc_bindings = toc.get("bindings", {})
    rtoc_bindings = rtoc.get("bindings", {})
    patoc_bindings = patoc.get("bindings", {})

    required_bindings = [
        ("toc.workspace_id", toc_bindings.get("workspace_id")),
        ("toc.trajectory_id", toc_bindings.get("trajectory_id")),
        ("toc.continuation_id", toc_bindings.get("continuation_id")),
        ("toc.action_digest", toc_bindings.get("action_digest")),
        ("rtoc.relationship_id", rtoc_bindings.get("relationship_id")),
        ("rtoc.actor_id", rtoc_bindings.get("actor_id")),
        ("rtoc.action_digest", rtoc_bindings.get("action_digest")),
        ("patoc.workspace_id", patoc_bindings.get("workspace_id")),
        ("patoc.trajectory_id", patoc_bindings.get("trajectory_id")),
        ("patoc.continuation_id", patoc_bindings.get("continuation_id")),
        ("patoc.relationship_id", patoc_bindings.get("relationship_id")),
        ("patoc.actor_id", patoc_bindings.get("actor_id")),
        ("patoc.action_digest", patoc_bindings.get("action_digest")),
    ]
    missing_bindings = [
        path for path, value in required_bindings if value in (None, "")
    ]
    if missing_bindings:
        fault(
            "binding_presence",
            "ABSTAIN",
            "MISSING_CENTER_RESULT",
            missing=missing_bindings,
        )
    else:
        passed("binding_presence")

    binding_checks = [
        (
            "workspace_binding",
            toc_bindings.get("workspace_id"),
            patoc_bindings.get("workspace_id"),
            "WORKSPACE_BINDING_MISMATCH",
        ),
        (
            "trajectory_binding",
            toc_bindings.get("trajectory_id"),
            patoc_bindings.get("trajectory_id"),
            "TRAJECTORY_BINDING_MISMATCH",
        ),
        (
            "continuation_binding",
            toc_bindings.get("continuation_id"),
            patoc_bindings.get("continuation_id"),
            "CONTINUATION_BINDING_MISMATCH",
        ),
        (
            "relationship_binding",
            rtoc_bindings.get("relationship_id"),
            patoc_bindings.get("relationship_id"),
            "RELATIONSHIP_BINDING_MISMATCH",
        ),
        (
            "actor_binding",
            rtoc_bindings.get("actor_id"),
            patoc_bindings.get("actor_id"),
            "ACTOR_BINDING_MISMATCH",
        ),
        (
            "toc_action_binding",
            toc_bindings.get("action_digest"),
            patoc_bindings.get("action_digest"),
            "ACTION_BINDING_MISMATCH",
        ),
        (
            "rtoc_action_binding",
            rtoc_bindings.get("action_digest"),
            patoc_bindings.get("action_digest"),
            "ACTION_BINDING_MISMATCH",
        ),
    ]
    for check_name, observed, expected, reason in binding_checks:
        if (
            observed not in (None, "")
            and expected not in (None, "")
            and observed != expected
        ):
            fault(
                check_name,
                "REJECT",
                reason,
                observed=observed,
                expected=expected,
            )
        else:
            passed(check_name)

    for name in center_names:
        center = case[name]
        verdict = center.get("verdict")
        mapping = VERDICT_MAPPING[name]
        if verdict not in mapping:
            fault(
                f"{name}_verdict",
                "ABSTAIN",
                "MISSING_CENTER_RESULT",
                observed=verdict,
            )
            continue

        mapped = mapping[verdict]
        if mapped is None:
            passed(f"{name}_verdict", observed=verdict)
        else:
            mapped_verdict, mapped_reason = mapped
            fault(
                f"{name}_verdict",
                mapped_verdict,
                mapped_reason,
                source_reason_code=center.get("reason_code"),
            )

    verdict, reason_code = _choose_fault(faults)
    coordinated_action_digest = (
        patoc_bindings.get("action_digest")
        if verdict == "COORDINATED_ACTION_CANDIDATE"
        else None
    )
    return _result(
        fixture_id,
        verdict,
        reason_code,
        checks,
        coordinated_action_digest,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Fixture JSON file or suite")
    parser.add_argument(
        "--check-expected",
        action="store_true",
        help="Exit non-zero when expected output differs",
    )
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    cases = payload.get("cases", [payload])
    results = []
    failures = []

    for case in cases:
        result = evaluate(case)
        results.append(result)
        expected = case.get("expected", {})
        if args.check_expected and (
            result["verdict"] != expected.get("verdict")
            or result["reason_code"] != expected.get("reason_code")
        ):
            failures.append({
                "fixture_id": case.get("fixture_id"),
                "expected": expected,
                "actual": {
                    "verdict": result["verdict"],
                    "reason_code": result["reason_code"],
                },
            })

    print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
