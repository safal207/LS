from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ls.coordination_benchmark import (
    ContractViolation,
    canonical_sha256,
    classify_dependency_release,
    validate_lifecycle_receipt,
    validate_scenario,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "multi-session-coordination"


def _load(relative_path: str) -> dict:
    return json.loads((EXPERIMENT / relative_path).read_text(encoding="utf-8"))


def test_canonical_scenario_is_valid_and_hash_is_stable() -> None:
    scenario = _load("canonical-five-session-scenario.json")

    validate_scenario(scenario)
    reordered = {key: scenario[key] for key in reversed(list(scenario))}

    assert canonical_sha256(scenario) == canonical_sha256(reordered)


def test_duplicate_event_ids_fail_closed() -> None:
    scenario = _load("canonical-five-session-scenario.json")
    duplicate = copy.deepcopy(scenario["events"][0])
    duplicate["sequence"] = 4
    scenario["events"].append(duplicate)

    with pytest.raises(ContractViolation, match="event_id"):
        validate_scenario(scenario)


def test_receipt_producer_must_match_scenario_event() -> None:
    scenario = _load("canonical-five-session-scenario.json")
    receipt = _load("fixtures/valid-endpoint-receipt.json")
    receipt["producer_session"] = "dashboard"

    with pytest.raises(ContractViolation, match="producer"):
        validate_lifecycle_receipt(receipt, scenario=scenario)


def test_verified_receipt_requires_verifier_evidence() -> None:
    receipt = _load("fixtures/valid-endpoint-receipt.json")
    del receipt["verification"]["evidence_ref"]

    with pytest.raises(ContractViolation, match="evidence_ref"):
        validate_lifecycle_receipt(receipt)


def test_done_without_verification_cannot_release_dependency() -> None:
    receipt = _load("fixtures/done-without-verification.json")

    assert classify_dependency_release(
        receipt,
        expected_producer_session="migration",
        expected_generation=2,
    ) == "BLOCKED_UNVERIFIED"


def test_stale_generation_is_blocked_by_provenance_gate() -> None:
    receipt = _load("fixtures/valid-endpoint-receipt.json")

    assert classify_dependency_release(
        receipt,
        expected_producer_session="migration",
        expected_generation=3,
    ) == "BLOCKED_PROVENANCE"


def test_missing_receipt_is_inconclusive_not_success() -> None:
    assert classify_dependency_release(
        None,
        expected_producer_session="migration",
        expected_generation=2,
    ) == "INCONCLUSIVE_MISSING_EVIDENCE"
