#!/usr/bin/env python3
"""Negative controls for LS durable approval conformance v0.2."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools" / "validate_durable_approval_v0_2.py"
FIXTURE_DIR = ROOT / "fixtures" / "trusted-runtime" / "durable-approval"
ENVELOPE_SCHEMA_PATH = FIXTURE_DIR / "envelope.schema.json"
EVENT_SCHEMA_PATH = FIXTURE_DIR / "event.schema.json"
FIXTURE_PATHS = {
    "configured_policy_expiry": FIXTURE_DIR / "configured_policy_expiry_v0.2.json",
    "verified_context_invalidation": FIXTURE_DIR / "verified_context_invalidation_v0.2.json",
    "durable_state_loss": FIXTURE_DIR / "durable_state_loss_v0.2.json",
    "reconcile_in_doubt_committed": FIXTURE_DIR / "reconcile_in_doubt_committed_v0.2.json",
    "reconcile_in_doubt_failed": FIXTURE_DIR / "reconcile_in_doubt_failed_v0.2.json",
}

_spec = importlib.util.spec_from_file_location("durable_approval_v0_2", VALIDATOR_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import validator from {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = validator
_spec.loader.exec_module(validator)


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class DurableApprovalV02Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixtures = {name: load(path) for name, path in FIXTURE_PATHS.items()}
        cls.envelope_schema = load(ENVELOPE_SCHEMA_PATH)
        cls.event_schema = load(EVENT_SCHEMA_PATH)

    def evaluate_one(self, fixture):
        return validator.validate_fixture(
            fixture,
            copy.deepcopy(self.envelope_schema),
            copy.deepcopy(self.event_schema),
        )

    def assert_rejected_with(self, fixture, fragment: str) -> None:
        result = self.evaluate_one(fixture)
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any(fragment in error for error in result["errors"]),
            f"expected error containing {fragment!r}, got {result['errors']}",
        )

    def test_baseline_suite_passes(self) -> None:
        result = validator.validate_suite(
            [copy.deepcopy(value) for value in self.fixtures.values()],
            copy.deepcopy(self.envelope_schema),
            copy.deepcopy(self.event_schema),
        )
        self.assertTrue(result["passed"], result)

    def test_expiry_actor_must_match_policy_id(self) -> None:
        fixture = copy.deepcopy(self.fixtures["configured_policy_expiry"])
        fixture["events"][-1]["actor"]["id"] = "different-policy"
        self.assert_rejected_with(fixture, "actor id must match expiry policy id")

    def test_expiry_cannot_precede_policy_deadline(self) -> None:
        fixture = copy.deepcopy(self.fixtures["configured_policy_expiry"])
        fixture["events"][-1]["occurred_at"] = "2026-07-06T18:54:59Z"
        self.assert_rejected_with(fixture, "expiry event cannot precede expires_at")

    def test_invalidation_requires_evidence(self) -> None:
        fixture = copy.deepcopy(self.fixtures["verified_context_invalidation"])
        fixture["events"][-1].pop("evidence_ref")
        self.assert_rejected_with(fixture, "invalidation evidence_ref is required")

    def test_lost_state_requires_evidence(self) -> None:
        fixture = copy.deepcopy(self.fixtures["durable_state_loss"])
        fixture["events"][-1].pop("evidence_ref")
        self.assert_rejected_with(fixture, "lost-state evidence_ref is required")

    def test_reconciliation_requires_evidence(self) -> None:
        fixture = copy.deepcopy(self.fixtures["reconcile_in_doubt_committed"])
        fixture["events"][-1].pop("evidence_ref")
        self.assert_rejected_with(fixture, "reconciliation evidence_ref is required")

    def test_effect_observation_requires_claim(self) -> None:
        fixture = copy.deepcopy(self.fixtures["reconcile_in_doubt_committed"])
        fixture["events"] = [
            event for event in fixture["events"] if event["event_type"] != "ExecutionClaimed"
        ]
        for index, event in enumerate(fixture["events"], start=1):
            event["sequence"] = index
        self.assert_rejected_with(fixture, "effect observation requires CLAIMED or IN_DOUBT")

    def test_duplicate_execution_claim_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixtures["reconcile_in_doubt_committed"])
        claim = copy.deepcopy(next(event for event in fixture["events"] if event["event_type"] == "ExecutionClaimed"))
        claim["event_id"] = "evt-executionclaimed-duplicate-05"
        claim["sequence"] = 5
        fixture["events"].insert(4, claim)
        for index, event in enumerate(fixture["events"], start=1):
            event["sequence"] = index
        self.assert_rejected_with(fixture, "execution approval is single-use")

    def test_claim_cannot_replay_after_committed_effect(self) -> None:
        fixture = copy.deepcopy(self.fixtures["reconcile_in_doubt_committed"])
        claim = copy.deepcopy(next(event for event in fixture["events"] if event["event_type"] == "ExecutionClaimed"))
        claim["event_id"] = "evt-executionclaimed-replay-07"
        claim["sequence"] = 7
        claim["occurred_at"] = "2026-07-06T18:47:01Z"
        fixture["events"].append(claim)
        self.assert_rejected_with(fixture, "execution approval is single-use")


if __name__ == "__main__":
    unittest.main()
