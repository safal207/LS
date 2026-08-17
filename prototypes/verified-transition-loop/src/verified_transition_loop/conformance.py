from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .core import (
    EvidenceBundle,
    TransitionIntent,
    TransitionProposal,
    TransitionVerdict,
    UseTokenRegistry,
    evaluate_transition,
    revalidate_authorization_for_use,
    verify_authorization_receipt,
    verify_use_time_receipt,
)

SCHEMA_VERSION = "vtl.use-time-conformance/v0.4"
PROFILE_ID = "vtl-use-time-v0.4"


def _require_mapping(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{where} must be an object")
    return value


def _require_keys(value: dict[str, Any], keys: tuple[str, ...], *, where: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise ValueError(f"{where} missing keys: {', '.join(missing)}")


def validate_fixture_shape(fixture: dict[str, Any]) -> None:
    _require_keys(fixture, ("schema_version", "profile", "base", "cases"), where="fixture")
    if fixture["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {fixture['schema_version']!r}")

    profile = _require_mapping(fixture["profile"], where="profile")
    _require_keys(
        profile,
        (
            "profile_id",
            "receipt_ids",
            "reason_code_order",
            "comparison_rule",
            "authorization_is_execution_authority",
            "execute_receipt_single_use",
        ),
        where="profile",
    )
    if profile["profile_id"] != PROFILE_ID:
        raise ValueError(f"unsupported profile_id: {profile['profile_id']!r}")
    if profile["receipt_ids"] != "implementation-local":
        raise ValueError("receipt_ids must remain implementation-local in v0.4")
    if profile["authorization_is_execution_authority"] is not False:
        raise ValueError("AUTHORIZE must not be execution authority")
    if profile["execute_receipt_single_use"] is not True:
        raise ValueError("EXECUTE receipts must be single-use")

    base = _require_mapping(fixture["base"], where="base")
    _require_keys(
        base,
        (
            "intent",
            "proposal",
            "authorization_evidence",
            "authorization_verifier_id",
            "executor_id",
            "authorized_at_ms",
        ),
        where="base",
    )

    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty array")

    seen: set[str] = set()
    for index, raw_case in enumerate(cases):
        case = _require_mapping(raw_case, where=f"cases[{index}]")
        _require_keys(
            case,
            (
                "id",
                "current_evidence",
                "executor_id",
                "checked_at_ms",
                "execution_nonce",
                "expected",
            ),
            where=f"cases[{index}]",
        )
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"cases[{index}].id must be a non-empty string")
        if case_id in seen:
            raise ValueError(f"duplicate case id: {case_id}")
        seen.add(case_id)

        expected = _require_mapping(case["expected"], where=f"cases[{index}].expected")
        _require_keys(
            expected,
            ("verdict", "reason_codes", "consume_results"),
            where=f"cases[{index}].expected",
        )
        if expected["verdict"] not in {"EXECUTE", "HOLD", "BLOCK"}:
            raise ValueError(f"invalid expected verdict for {case_id}")
        if not isinstance(expected["reason_codes"], list):
            raise ValueError(f"reason_codes must be an array for {case_id}")
        consume_results = expected["consume_results"]
        if not isinstance(consume_results, list) or not consume_results:
            raise ValueError(f"consume_results must be a non-empty array for {case_id}")
        if any(not isinstance(item, bool) for item in consume_results):
            raise ValueError(f"consume_results must contain booleans for {case_id}")


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path)
    with fixture_path.open("r", encoding="utf-8") as handle:
        fixture = json.load(handle)
    fixture = _require_mapping(fixture, where="fixture")
    validate_fixture_shape(fixture)
    return fixture


def _intent(raw: dict[str, Any]) -> TransitionIntent:
    return TransitionIntent(
        intent_id=str(raw["intent_id"]),
        actor=str(raw["actor"]),
        action=str(raw["action"]),
        purpose=str(raw["purpose"]),
    )


def _proposal(raw: dict[str, Any]) -> TransitionProposal:
    return TransitionProposal(
        transition_id=str(raw["transition_id"]),
        intent_id=str(raw["intent_id"]),
        pre_state=str(raw["pre_state"]),
        action=str(raw["action"]),
        expected_post_state=str(raw["expected_post_state"]),
        invariants=tuple(str(item) for item in raw["invariants"]),
    )


def _evidence(raw: dict[str, Any]) -> EvidenceBundle:
    return EvidenceBundle(
        mission_aligned=raw["mission_aligned"],
        exact_source_bound=raw["exact_source_bound"],
        tests_passed=raw["tests_passed"],
        approval_current=raw["approval_current"],
        approval_valid_until_ms=raw["approval_valid_until_ms"],
        evidence_refs=tuple(str(item) for item in raw["evidence_refs"]),
        source_ref=raw["source_ref"],
        policy_ref=raw["policy_ref"],
        approval_ref=raw["approval_ref"],
    )


def run_fixture(fixture: dict[str, Any]) -> dict[str, Any]:
    validate_fixture_shape(fixture)
    base = fixture["base"]
    intent = _intent(base["intent"])
    proposal = _proposal(base["proposal"])
    authorization_evidence = _evidence(base["authorization_evidence"])

    authorization = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=authorization_evidence,
        verifier_id=str(base["authorization_verifier_id"]),
        executor_id=str(base["executor_id"]),
        now_ms=int(base["authorized_at_ms"]),
    )

    if authorization.verdict is not TransitionVerdict.AUTHORIZE:
        raise ValueError(
            "base authorization must yield AUTHORIZE, got "
            f"{authorization.verdict.value}: {authorization.reason_codes}"
        )
    if not verify_authorization_receipt(authorization):
        raise ValueError("base authorization receipt failed integrity verification")

    case_results: list[dict[str, Any]] = []
    all_passed = True

    for raw_case in fixture["cases"]:
        current_evidence = _evidence(raw_case["current_evidence"])
        use_receipt = revalidate_authorization_for_use(
            proposal=proposal,
            authorization=authorization,
            current_evidence=current_evidence,
            executor_id=str(raw_case["executor_id"]),
            now_ms=int(raw_case["checked_at_ms"]),
            execution_nonce=str(raw_case["execution_nonce"]),
        )
        registry = UseTokenRegistry()
        expected = raw_case["expected"]
        consume_results = [
            registry.consume(use_receipt)
            for _ in expected["consume_results"]
        ]

        actual = {
            "verdict": use_receipt.verdict.value,
            "reason_codes": list(use_receipt.reason_codes),
            "consume_results": consume_results,
            "receipt_integrity_valid": verify_use_time_receipt(use_receipt),
        }
        semantic_match = (
            actual["verdict"] == expected["verdict"]
            and actual["reason_codes"] == expected["reason_codes"]
            and actual["consume_results"] == expected["consume_results"]
            and actual["receipt_integrity_valid"] is True
        )
        all_passed = all_passed and semantic_match
        case_results.append(
            {
                "id": raw_case["id"],
                "passed": semantic_match,
                "expected": expected,
                "actual": actual,
            }
        )

    return {
        "schema_version": fixture["schema_version"],
        "profile_id": fixture["profile"]["profile_id"],
        "authorization": {
            "verdict": authorization.verdict.value,
            "integrity_valid": verify_authorization_receipt(authorization),
            "decision_id": authorization.decision_id,
        },
        "cases": case_results,
        "summary": {
            "total": len(case_results),
            "passed": sum(1 for item in case_results if item["passed"]),
            "failed": sum(1 for item in case_results if not item["passed"]),
            "all_passed": all_passed,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run VTL vendor-neutral use-time conformance vectors."
    )
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    result = run_fixture(load_fixture(args.fixture))
    if args.compact:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["summary"]["all_passed"] else 1)


if __name__ == "__main__":
    main()
