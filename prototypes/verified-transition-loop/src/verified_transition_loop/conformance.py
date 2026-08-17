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


def _require_exact_keys(
    value: dict[str, Any],
    required: tuple[str, ...],
    *,
    where: str,
    optional: tuple[str, ...] = (),
) -> None:
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - set(value))
    unknown = sorted(set(value) - allowed)
    if missing:
        raise ValueError(f"{where} missing keys: {', '.join(missing)}")
    if unknown:
        raise ValueError(f"{where} unknown keys: {', '.join(unknown)}")


def _require_non_empty_string(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where} must be a non-empty string")
    return value


def _require_string(value: Any, *, where: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{where} must be a string")
    return value


def _require_non_negative_int(value: Any, *, where: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{where} must be a non-negative integer")
    return value


def _validate_intent(raw: Any, *, where: str) -> dict[str, Any]:
    value = _require_mapping(raw, where=where)
    _require_exact_keys(
        value,
        ("intent_id", "actor", "action", "purpose"),
        where=where,
    )
    for key in ("intent_id", "actor", "action", "purpose"):
        _require_non_empty_string(value[key], where=f"{where}.{key}")
    return value


def _validate_proposal(raw: Any, *, where: str) -> dict[str, Any]:
    value = _require_mapping(raw, where=where)
    _require_exact_keys(
        value,
        (
            "transition_id",
            "intent_id",
            "pre_state",
            "action",
            "expected_post_state",
            "invariants",
        ),
        where=where,
    )
    for key in ("transition_id", "intent_id", "action"):
        _require_non_empty_string(value[key], where=f"{where}.{key}")
    _require_string(value["pre_state"], where=f"{where}.pre_state")
    _require_string(value["expected_post_state"], where=f"{where}.expected_post_state")
    invariants = value["invariants"]
    if not isinstance(invariants, list):
        raise ValueError(f"{where}.invariants must be an array")
    if any(not isinstance(item, str) or not item for item in invariants):
        raise ValueError(f"{where}.invariants must contain non-empty strings")
    if len(set(invariants)) != len(invariants):
        raise ValueError(f"{where}.invariants must contain unique items")
    return value


def _validate_evidence(raw: Any, *, where: str) -> dict[str, Any]:
    value = _require_mapping(raw, where=where)
    _require_exact_keys(
        value,
        (
            "mission_aligned",
            "exact_source_bound",
            "tests_passed",
            "approval_current",
            "approval_valid_until_ms",
            "evidence_refs",
            "source_ref",
            "policy_ref",
            "approval_ref",
        ),
        where=where,
    )
    for key in (
        "mission_aligned",
        "exact_source_bound",
        "tests_passed",
        "approval_current",
    ):
        if value[key] is not None and not isinstance(value[key], bool):
            raise ValueError(f"{where}.{key} must be boolean or null")
    expiry = value["approval_valid_until_ms"]
    if expiry is not None:
        _require_non_negative_int(expiry, where=f"{where}.approval_valid_until_ms")
    refs = value["evidence_refs"]
    if not isinstance(refs, list) or any(not isinstance(item, str) for item in refs):
        raise ValueError(f"{where}.evidence_refs must be an array of strings")
    for key in ("source_ref", "policy_ref", "approval_ref"):
        if value[key] is not None and not isinstance(value[key], str):
            raise ValueError(f"{where}.{key} must be string or null")
    return value


def _validate_expected(raw: Any, *, where: str) -> dict[str, Any]:
    value = _require_mapping(raw, where=where)
    _require_exact_keys(
        value,
        ("verdict", "reason_codes", "consume_results"),
        where=where,
    )
    if value["verdict"] not in {"EXECUTE", "HOLD", "BLOCK"}:
        raise ValueError(f"{where}.verdict is invalid")
    reasons = value["reason_codes"]
    if not isinstance(reasons, list) or any(not isinstance(item, str) for item in reasons):
        raise ValueError(f"{where}.reason_codes must be an array of strings")
    consume_results = value["consume_results"]
    if not isinstance(consume_results, list) or not consume_results:
        raise ValueError(f"{where}.consume_results must be a non-empty array")
    if any(not isinstance(item, bool) for item in consume_results):
        raise ValueError(f"{where}.consume_results must contain booleans")
    return value


def validate_fixture_shape(fixture: dict[str, Any]) -> None:
    _require_exact_keys(
        fixture,
        ("schema_version", "profile", "base", "cases"),
        where="fixture",
    )
    if fixture["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {fixture['schema_version']!r}")

    profile = _require_mapping(fixture["profile"], where="profile")
    _require_exact_keys(
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
    if profile["reason_code_order"] not in {"normative", "non-normative"}:
        raise ValueError("reason_code_order must be normative or non-normative")
    _require_non_empty_string(profile["comparison_rule"], where="profile.comparison_rule")
    if profile["authorization_is_execution_authority"] is not False:
        raise ValueError("AUTHORIZE must not be execution authority")
    if profile["execute_receipt_single_use"] is not True:
        raise ValueError("EXECUTE receipts must be single-use")

    base = _require_mapping(fixture["base"], where="base")
    _require_exact_keys(
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
    _validate_intent(base["intent"], where="base.intent")
    _validate_proposal(base["proposal"], where="base.proposal")
    _validate_evidence(base["authorization_evidence"], where="base.authorization_evidence")
    _require_non_empty_string(
        base["authorization_verifier_id"],
        where="base.authorization_verifier_id",
    )
    _require_non_empty_string(base["executor_id"], where="base.executor_id")
    _require_non_negative_int(base["authorized_at_ms"], where="base.authorized_at_ms")

    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a non-empty array")

    seen: set[str] = set()
    for index, raw_case in enumerate(cases):
        where = f"cases[{index}]"
        case = _require_mapping(raw_case, where=where)
        _require_exact_keys(
            case,
            (
                "id",
                "current_evidence",
                "executor_id",
                "checked_at_ms",
                "execution_nonce",
                "expected",
            ),
            optional=("proposal",),
            where=where,
        )
        case_id = _require_non_empty_string(case["id"], where=f"{where}.id")
        if case_id in seen:
            raise ValueError(f"duplicate case id: {case_id}")
        seen.add(case_id)
        _validate_evidence(case["current_evidence"], where=f"{where}.current_evidence")
        if "proposal" in case:
            _validate_proposal(case["proposal"], where=f"{where}.proposal")
        _require_non_empty_string(case["executor_id"], where=f"{where}.executor_id")
        _require_non_negative_int(case["checked_at_ms"], where=f"{where}.checked_at_ms")
        _require_string(case["execution_nonce"], where=f"{where}.execution_nonce")
        _validate_expected(case["expected"], where=f"{where}.expected")


def load_fixture(path: str | Path) -> dict[str, Any]:
    fixture_path = Path(path)
    with fixture_path.open("r", encoding="utf-8") as handle:
        fixture = json.load(handle)
    fixture = _require_mapping(fixture, where="fixture")
    validate_fixture_shape(fixture)
    return fixture


def _intent(raw: dict[str, Any]) -> TransitionIntent:
    return TransitionIntent(
        intent_id=raw["intent_id"],
        actor=raw["actor"],
        action=raw["action"],
        purpose=raw["purpose"],
    )


def _proposal(raw: dict[str, Any]) -> TransitionProposal:
    return TransitionProposal(
        transition_id=raw["transition_id"],
        intent_id=raw["intent_id"],
        pre_state=raw["pre_state"],
        action=raw["action"],
        expected_post_state=raw["expected_post_state"],
        invariants=tuple(raw["invariants"]),
    )


def _evidence(raw: dict[str, Any]) -> EvidenceBundle:
    return EvidenceBundle(
        mission_aligned=raw["mission_aligned"],
        exact_source_bound=raw["exact_source_bound"],
        tests_passed=raw["tests_passed"],
        approval_current=raw["approval_current"],
        approval_valid_until_ms=raw["approval_valid_until_ms"],
        evidence_refs=tuple(raw["evidence_refs"]),
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
        verifier_id=base["authorization_verifier_id"],
        executor_id=base["executor_id"],
        now_ms=base["authorized_at_ms"],
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
        case_proposal = _proposal(raw_case.get("proposal", base["proposal"]))
        current_evidence = _evidence(raw_case["current_evidence"])
        use_receipt = revalidate_authorization_for_use(
            proposal=case_proposal,
            authorization=authorization,
            current_evidence=current_evidence,
            executor_id=raw_case["executor_id"],
            now_ms=raw_case["checked_at_ms"],
            execution_nonce=raw_case["execution_nonce"],
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
