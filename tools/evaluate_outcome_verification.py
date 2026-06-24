#!/usr/bin/env python3
"""Deterministic evaluator for LS Outcome Verification Center v0.1."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SEVERITY = {
    "VERIFIED": 0,
    "ABSTAIN": 1,
    "REOBSERVE": 2,
    "INVESTIGATE": 3,
    "REJECT": 4,
}

REASON_ORDER = {
    "REJECT": [
        "EXECUTION_IDENTITY_MISMATCH",
        "RECEIPT_IDENTITY_MISMATCH",
        "UNTRUSTED_RECEIPT_ISSUER",
        "RECEIPT_REPLAY",
        "EVIDENCE_REPLAY",
        "INVALID_EVIDENCE_TIME",
        "OBSERVER_SCOPE_MISMATCH",
    ],
    "INVESTIGATE": [
        "EXPECTED_OUTCOME_CONTRACT_DRIFT",
        "RECEIPT_OBSERVATION_CONFLICT",
        "CONTRADICTORY_EVIDENCE",
        "PARTIAL_OUTCOME",
    ],
    "REOBSERVE": [
        "REQUIRED_EVIDENCE_NOT_YET_AVAILABLE",
        "INDEPENDENT_OBSERVER_PENDING",
        "CONSISTENCY_WINDOW_OPEN",
    ],
    "ABSTAIN": [
        "MISSING_VERIFICATION_EVIDENCE",
        "INSUFFICIENT_EVIDENCE_AFTER_DEADLINE",
        "AMBIGUOUS_OBSERVED_STATE",
    ],
    "VERIFIED": [
        "EXPECTED_OUTCOME_VERIFIED",
        "FAILURE_OUTCOME_VERIFIED",
        "UNEXPECTED_OUTCOME_VERIFIED",
    ],
}


def _parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _choose_fault(faults: list[tuple[str, str]]) -> tuple[str, str]:
    if not faults:
        return "ABSTAIN", "AMBIGUOUS_OBSERVED_STATE"

    highest = max(SEVERITY[verdict] for verdict, _ in faults)
    verdict = next(name for name, value in SEVERITY.items() if value == highest)
    reasons = {reason for candidate, reason in faults if candidate == verdict}
    for reason in REASON_ORDER[verdict]:
        if reason in reasons:
            return verdict, reason
    return verdict, sorted(reasons)[0]


def _result(
    fixture_id: str,
    verdict: str,
    reason_code: str,
    checks: list[dict[str, Any]],
    *,
    outcome_class: str = "unknown",
    verified_state_digest: str | None = None,
) -> dict[str, Any]:
    verified = verdict == "VERIFIED"
    return {
        "fixture_id": fixture_id,
        "verification_version": "outcome-verification-v0.1",
        "verdict": verdict,
        "reason_code": reason_code,
        "outcome_class": outcome_class,
        "verified_state_digest": verified_state_digest if verified else None,
        "new_orientation_state_digest_candidate": (
            verified_state_digest if verified else None
        ),
        "experience_eligible": verified,
        "execution_authorized": False,
        "retroactive_authorization_created": False,
        "downstream_learning_gate_required": True,
        "checks": checks,
    }


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    fixture_id = case.get("fixture_id", "unknown")
    verification = case.get("verification", {})
    authoritative = case.get("authoritative_state", {})
    checks: list[dict[str, Any]] = []
    faults: list[tuple[str, str]] = []

    identity = verification.get("execution_identity", {})
    expected = verification.get("expected_outcome", {})
    contract = verification.get("evidence_contract", {})
    receipt = verification.get("execution_receipt", {})
    observations = verification.get("observations", [])

    def fault(check: str, verdict: str, reason: str, **details: Any) -> None:
        checks.append({"check": check, "status": "failed", **details})
        faults.append((verdict, reason))

    def passed(check: str, **details: Any) -> None:
        checks.append({"check": check, "status": "passed", **details})

    required_values = {
        "execution_identity.execution_id": identity.get("execution_id"),
        "execution_identity.action_id": identity.get("action_id"),
        "execution_identity.action_digest": identity.get("action_digest"),
        "execution_identity.side_effect_key": identity.get("side_effect_key"),
        "expected_outcome.expected_state_digest": expected.get("expected_state_digest"),
        "expected_outcome.pre_state_digest": expected.get("pre_state_digest"),
        "execution_receipt.receipt_id": receipt.get("receipt_id"),
        "execution_receipt.receipt_digest": receipt.get("receipt_digest"),
        "provenance.causal_trace_id": verification.get("provenance", {}).get(
            "causal_trace_id"
        ),
    }
    missing = [path for path, value in required_values.items() if value in (None, "")]
    if missing:
        fault(
            "required_verification_evidence",
            "ABSTAIN",
            "MISSING_VERIFICATION_EVIDENCE",
            missing=missing,
        )
    else:
        passed("required_verification_evidence")

    identity_pairs = [
        (
            "execution_id",
            identity.get("execution_id"),
            authoritative.get("expected_execution_id"),
        ),
        ("action_id", identity.get("action_id"), authoritative.get("expected_action_id")),
        (
            "action_digest",
            identity.get("action_digest"),
            authoritative.get("expected_action_digest"),
        ),
        (
            "side_effect_key",
            identity.get("side_effect_key"),
            authoritative.get("expected_side_effect_key"),
        ),
    ]
    for field, observed, expected_value in identity_pairs:
        if expected_value is not None and observed != expected_value:
            fault(
                f"execution_identity_{field}",
                "REJECT",
                "EXECUTION_IDENTITY_MISMATCH",
                field=field,
                observed=observed,
                expected=expected_value,
            )
        else:
            passed(f"execution_identity_{field}")

    receipt_pairs = [
        ("execution_id", receipt.get("execution_id"), identity.get("execution_id")),
        ("action_id", receipt.get("action_id"), identity.get("action_id")),
        ("action_digest", receipt.get("action_digest"), identity.get("action_digest")),
        (
            "side_effect_key",
            receipt.get("side_effect_key"),
            identity.get("side_effect_key"),
        ),
    ]
    for field, observed, expected_value in receipt_pairs:
        if observed != expected_value:
            fault(
                f"receipt_identity_{field}",
                "REJECT",
                "RECEIPT_IDENTITY_MISMATCH",
                field=field,
                observed=observed,
                expected=expected_value,
            )
        else:
            passed(f"receipt_identity_{field}")

    trusted_issuers = set(authoritative.get("trusted_receipt_issuers", []))
    if receipt.get("issuer_id") not in trusted_issuers:
        fault(
            "receipt_issuer",
            "REJECT",
            "UNTRUSTED_RECEIPT_ISSUER",
            observed=receipt.get("issuer_id"),
        )
    else:
        passed("receipt_issuer")

    if receipt.get("receipt_id") in set(authoritative.get("seen_receipt_ids", [])):
        fault(
            "receipt_replay",
            "REJECT",
            "RECEIPT_REPLAY",
            receipt_id=receipt.get("receipt_id"),
        )
    else:
        passed("receipt_replay")

    current_expected = authoritative.get("expected_state_digest")
    if (
        current_expected is not None
        and expected.get("expected_state_digest") != current_expected
    ):
        fault(
            "expected_outcome_contract",
            "INVESTIGATE",
            "EXPECTED_OUTCOME_CONTRACT_DRIFT",
            observed=expected.get("expected_state_digest"),
            expected=current_expected,
        )
    else:
        passed("expected_outcome_contract")

    try:
        current_time = _parse_timestamp(authoritative["current_time"])
        receipt_time = _parse_timestamp(receipt["issued_at"])
        consistency_until = _parse_timestamp(expected["consistency_window_until"])
        deadline_at = _parse_timestamp(expected["verification_deadline_at"])
    except (KeyError, TypeError, ValueError):
        fault(
            "time_evidence",
            "ABSTAIN",
            "MISSING_VERIFICATION_EVIDENCE",
        )
        verdict, reason_code = _choose_fault(faults)
        return _result(fixture_id, verdict, reason_code, checks)

    if receipt_time > current_time:
        fault(
            "receipt_time",
            "REJECT",
            "INVALID_EVIDENCE_TIME",
            receipt_time=receipt.get("issued_at"),
            current_time=authoritative.get("current_time"),
        )
    else:
        passed("receipt_time")

    seen_evidence = set(authoritative.get("seen_evidence_digests", []))
    valid_observations: list[dict[str, Any]] = []
    observed_kinds: set[str] = set()
    independent_observers: set[str] = set()
    complete_state_digests: list[str] = []
    partial_present = False
    absent_present = False

    required_scope = authoritative.get(
        "required_observer_scope_digest",
        contract.get("required_observer_scope_digest"),
    )

    for observation in observations:
        evidence_digest = observation.get("evidence_digest")
        if evidence_digest in seen_evidence:
            fault(
                "evidence_replay",
                "REJECT",
                "EVIDENCE_REPLAY",
                evidence_digest=evidence_digest,
            )
            continue

        try:
            observed_at = _parse_timestamp(observation["observed_at"])
        except (KeyError, TypeError, ValueError):
            fault(
                "observation_time",
                "REJECT",
                "INVALID_EVIDENCE_TIME",
                observation_id=observation.get("observation_id"),
            )
            continue

        if observed_at < receipt_time or observed_at > current_time:
            fault(
                "observation_time",
                "REJECT",
                "INVALID_EVIDENCE_TIME",
                observation_id=observation.get("observation_id"),
                observed_at=observation.get("observed_at"),
            )
            continue
        passed(
            "observation_time",
            observation_id=observation.get("observation_id"),
        )

        if observation.get("authority_scope_digest") != required_scope:
            fault(
                "observer_scope",
                "REJECT",
                "OBSERVER_SCOPE_MISMATCH",
                observation_id=observation.get("observation_id"),
                observed=observation.get("authority_scope_digest"),
                expected=required_scope,
            )
            continue
        passed(
            "observer_scope",
            observation_id=observation.get("observation_id"),
        )

        valid_observations.append(observation)
        observed_kinds.add(observation.get("evidence_kind"))
        if observation.get("independent") is True:
            independent_observers.add(observation.get("observer_id"))

        status = observation.get("outcome_status")
        if status == "complete":
            state_digest = observation.get("state_digest")
            if state_digest:
                complete_state_digests.append(state_digest)
            else:
                fault(
                    "complete_observation_state",
                    "ABSTAIN",
                    "AMBIGUOUS_OBSERVED_STATE",
                    observation_id=observation.get("observation_id"),
                )
        elif status == "partial":
            partial_present = True
        elif status == "absent":
            absent_present = True

    required_kinds = set(
        authoritative.get(
            "required_evidence_kinds",
            contract.get("required_evidence_kinds", []),
        )
    )
    missing_kinds = sorted(required_kinds - observed_kinds)
    if missing_kinds:
        if current_time <= consistency_until:
            fault(
                "required_evidence_kinds",
                "REOBSERVE",
                "REQUIRED_EVIDENCE_NOT_YET_AVAILABLE",
                missing=missing_kinds,
            )
        else:
            fault(
                "required_evidence_kinds",
                "ABSTAIN",
                "INSUFFICIENT_EVIDENCE_AFTER_DEADLINE",
                missing=missing_kinds,
            )
    else:
        passed("required_evidence_kinds")

    minimum_independent = authoritative.get(
        "min_independent_observers",
        contract.get("min_independent_observers", 1),
    )
    if len(independent_observers) < minimum_independent:
        if current_time <= consistency_until:
            fault(
                "independent_observers",
                "REOBSERVE",
                "INDEPENDENT_OBSERVER_PENDING",
                observed=len(independent_observers),
                required=minimum_independent,
            )
        else:
            fault(
                "independent_observers",
                "ABSTAIN",
                "INSUFFICIENT_EVIDENCE_AFTER_DEADLINE",
                observed=len(independent_observers),
                required=minimum_independent,
            )
    else:
        passed("independent_observers")

    if partial_present:
        fault("partial_outcome", "INVESTIGATE", "PARTIAL_OUTCOME")
    else:
        passed("partial_outcome")

    unique_complete_digests = sorted(set(complete_state_digests))
    if len(unique_complete_digests) > 1:
        fault(
            "evidence_consistency",
            "INVESTIGATE",
            "CONTRADICTORY_EVIDENCE",
            observed_state_digests=unique_complete_digests,
        )
    elif len(unique_complete_digests) == 1:
        passed(
            "evidence_consistency",
            observed_state_digest=unique_complete_digests[0],
        )
    elif valid_observations:
        if absent_present and current_time <= consistency_until:
            fault(
                "observed_state_availability",
                "REOBSERVE",
                "CONSISTENCY_WINDOW_OPEN",
            )
        elif current_time > deadline_at:
            fault(
                "observed_state_availability",
                "ABSTAIN",
                "INSUFFICIENT_EVIDENCE_AFTER_DEADLINE",
            )
        else:
            fault(
                "observed_state_availability",
                "REOBSERVE",
                "REQUIRED_EVIDENCE_NOT_YET_AVAILABLE",
            )
    else:
        if contract.get("allow_receipt_only") is True:
            if receipt.get("status") == "failed":
                faults.append(("VERIFIED", "FAILURE_OUTCOME_VERIFIED"))
                checks.append(
                    {
                        "check": "receipt_only_contract",
                        "status": "passed",
                        "receipt_status": "failed",
                    }
                )
            elif current_time <= consistency_until:
                fault(
                    "receipt_only_contract",
                    "REOBSERVE",
                    "CONSISTENCY_WINDOW_OPEN",
                )
            else:
                fault(
                    "receipt_only_contract",
                    "ABSTAIN",
                    "INSUFFICIENT_EVIDENCE_AFTER_DEADLINE",
                )
        elif current_time <= consistency_until:
            fault(
                "observation_presence",
                "REOBSERVE",
                "REQUIRED_EVIDENCE_NOT_YET_AVAILABLE",
            )
        else:
            fault(
                "observation_presence",
                "ABSTAIN",
                "INSUFFICIENT_EVIDENCE_AFTER_DEADLINE",
            )

    outcome_class = "unknown"
    verified_state_digest: str | None = None

    if len(unique_complete_digests) == 1 and not partial_present:
        observed_digest = unique_complete_digests[0]
        verified_state_digest = observed_digest

        if (
            receipt.get("status") == "failed"
            and observed_digest == expected.get("expected_state_digest")
        ):
            fault(
                "receipt_observation_consistency",
                "INVESTIGATE",
                "RECEIPT_OBSERVATION_CONFLICT",
                receipt_status=receipt.get("status"),
                observed_state_digest=observed_digest,
            )
        else:
            passed("receipt_observation_consistency")

        if not any(
            SEVERITY[verdict] > SEVERITY["VERIFIED"]
            for verdict, _ in faults
        ):
            if observed_digest == expected.get("expected_state_digest"):
                faults.append(("VERIFIED", "EXPECTED_OUTCOME_VERIFIED"))
                outcome_class = "expected"
            elif (
                receipt.get("status") == "failed"
                and observed_digest == expected.get("pre_state_digest")
            ):
                faults.append(("VERIFIED", "FAILURE_OUTCOME_VERIFIED"))
                outcome_class = "failed"
            else:
                faults.append(("VERIFIED", "UNEXPECTED_OUTCOME_VERIFIED"))
                outcome_class = "unexpected"

    verdict, reason_code = _choose_fault(faults)
    if verdict != "VERIFIED":
        outcome_class = "partial" if reason_code == "PARTIAL_OUTCOME" else "unknown"
        verified_state_digest = None

    return _result(
        fixture_id,
        verdict,
        reason_code,
        checks,
        outcome_class=outcome_class,
        verified_state_digest=verified_state_digest,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--check-expected", action="store_true")
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
            failures.append(
                {
                    "fixture_id": case.get("fixture_id"),
                    "expected": expected,
                    "actual": {
                        "verdict": result["verdict"],
                        "reason_code": result["reason_code"],
                    },
                }
            )

    print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
