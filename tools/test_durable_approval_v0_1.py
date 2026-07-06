#!/usr/bin/env python3
"""Negative controls for LS durable approval conformance v0.1."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "tools" / "validate_durable_approval_v0_1.py"
FIXTURE_PATH = ROOT / "fixtures" / "trusted-runtime" / "durable-approval" / "pending_approval_not_missing_authority_v0.1.json"
ENVELOPE_SCHEMA_PATH = ROOT / "fixtures" / "trusted-runtime" / "durable-approval" / "envelope.schema.json"
EVENT_SCHEMA_PATH = ROOT / "fixtures" / "trusted-runtime" / "durable-approval" / "event.schema.json"

spec = importlib.util.spec_from_file_location("durable_approval_validator", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot import validator from {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = validator
spec.loader.exec_module(validator)


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class DurableApprovalConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load(FIXTURE_PATH)
        cls.envelope_schema = load(ENVELOPE_SCHEMA_PATH)
        cls.event_schema = load(EVENT_SCHEMA_PATH)

    def evaluate(self, fixture):
        return validator.validate(
            fixture,
            copy.deepcopy(self.envelope_schema),
            copy.deepcopy(self.event_schema),
        )

    def assert_rejected_with(self, fixture, fragment: str) -> None:
        result = self.evaluate(fixture)
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any(fragment in error for error in result["errors"]),
            f"expected error containing {fragment!r}, got {result['errors']}",
        )

    def test_baseline_fixture_passes(self) -> None:
        result = self.evaluate(copy.deepcopy(self.fixture))
        self.assertTrue(result["passed"], result)

    def test_agent_cannot_emit_user_rejection(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        case = next(case for case in fixture["cases"] if case["case_id"] == "agent_cancels_requester")
        case["events"][2]["event_type"] = "UserRejected"
        self.assert_rejected_with(fixture, "actor 'AGENT' cannot emit UserRejected")

    def test_expiry_without_expiry_policy_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        case = next(case for case in fixture["cases"] if case["case_id"] == "elapsed_wait_without_expiry")
        event = case["events"][2]
        event["event_type"] = "ApprovalExpired"
        event["actor"] = {"type": "POLICY", "id": "implicit-timeout"}
        event["reason"] = "implicit timeout"
        event["evidence_ref"] = "policy:none"
        self.assert_rejected_with(fixture, "expiry requires configured expiry_policy")

    def test_changed_action_digest_cannot_claim_execution(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        case = next(case for case in fixture["cases"] if case["case_id"] == "restart_after_execution_claim")
        claim = next(event for event in case["events"] if event["event_type"] == "ExecutionClaimed")
        claim["bindings"]["action_digest"] = "sha256:CHANGED_ACTION"
        self.assert_rejected_with(fixture, "binding mismatch for action_digest")

    def test_duplicate_event_id_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        case = next(case for case in fixture["cases"] if case["case_id"] == "transport_disconnects")
        case["events"][2]["event_id"] = case["events"][1]["event_id"]
        self.assert_rejected_with(fixture, "duplicate event_id")

    def test_reordered_sequence_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        case = next(case for case in fixture["cases"] if case["case_id"] == "explicit_user_rejection")
        case["events"][2]["sequence"] = 2
        self.assert_rejected_with(fixture, "sequence must equal 3")


if __name__ == "__main__":
    unittest.main()
