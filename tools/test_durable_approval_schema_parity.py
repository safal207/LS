#!/usr/bin/env python3
"""Regression controls for schema/runtime parity in durable approval validators."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "trusted-runtime" / "durable-approval"
VALIDATOR_PATH = ROOT / "tools" / "validate_durable_approval_v0_2.py"

_spec = importlib.util.spec_from_file_location("durable_approval_v0_2_parity", VALIDATOR_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import validator from {VALIDATOR_PATH}")
validator = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = validator
_spec.loader.exec_module(validator)


def load(name: str):
    with (FIXTURE_DIR / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


class DurableApprovalSchemaParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load("reconcile_in_doubt_committed_v0.2.json")
        cls.expiry_fixture = load("configured_policy_expiry_v0.2.json")
        cls.envelope_schema = load("envelope.schema.json")
        cls.event_schema = load("event.schema.json")

    def evaluate(self, fixture):
        return validator.validate_fixture(
            fixture,
            copy.deepcopy(self.envelope_schema),
            copy.deepcopy(self.event_schema),
        )

    def assert_rejected_with(self, fixture, fragment: str) -> None:
        result = self.evaluate(fixture)
        self.assertFalse(result["passed"], result)
        self.assertTrue(
            any(fragment in error for error in result["errors"]),
            f"expected {fragment!r}, got {result['errors']}",
        )

    def test_closed_objects_reject_unknown_properties(self) -> None:
        mutations = []

        fixture = copy.deepcopy(self.fixture)
        fixture["envelope"]["unexpected"] = True
        mutations.append((fixture, "fixture.envelope: unexpected properties"))

        fixture = copy.deepcopy(self.expiry_fixture)
        fixture["envelope"]["expiry_policy"]["unexpected"] = True
        mutations.append(
            (fixture, "fixture.envelope.expiry_policy: unexpected properties")
        )

        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["unexpected"] = True
        mutations.append((fixture, "events[0]: unexpected properties"))

        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["actor"]["unexpected"] = True
        mutations.append((fixture, "actor: unexpected properties"))

        fixture = copy.deepcopy(self.fixture)
        claim = next(
            event
            for event in fixture["events"]
            if event["event_type"] == "ExecutionClaimed"
        )
        claim["bindings"]["unexpected"] = True
        mutations.append((fixture, "bindings: unexpected properties"))

        for fixture, fragment in mutations:
            with self.subTest(fragment=fragment):
                self.assert_rejected_with(fixture, fragment)

    def test_schema_invalid_scalar_types_are_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["sequence"] = True
        self.assert_rejected_with(fixture, "sequence must be an integer")

        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["actor"]["id"] = 1
        self.assert_rejected_with(fixture, "actor.id must be a string")

    def test_malformed_scalar_values_fail_closed(self) -> None:
        cases = []

        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["event_id"] = []
        cases.append((fixture, "event_id must be a string"))

        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["event_type"] = []
        cases.append((fixture, "event_type must be a string"))

        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["actor"]["type"] = []
        cases.append((fixture, "actor.type must be a string"))

        fixture = copy.deepcopy(self.fixture)
        effect = next(
            event
            for event in fixture["events"]
            if event["event_type"] == "EffectObserved"
        )
        effect["outcome"] = []
        cases.append((fixture, "outcome must be a string"))

        fixture = copy.deepcopy(self.fixture)
        approval = next(
            event
            for event in fixture["events"]
            if event["event_type"] == "UserApproved"
        )
        approval["actor"] = []
        cases.append((fixture, "actor: must be an object"))

        for fixture, fragment in cases:
            with self.subTest(fragment=fragment):
                self.assert_rejected_with(fixture, fragment)

    def test_non_rfc3339_space_separator_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["events"][0]["occurred_at"] = "2026-07-06 18:45:00Z"
        self.assert_rejected_with(fixture, "invalid RFC 3339 timestamp")


if __name__ == "__main__":
    unittest.main()
