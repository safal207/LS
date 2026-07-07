#!/usr/bin/env python3
"""Negative controls for the LS ReviewDecision adapter v0.1."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "tools" / "review_decision_adapter_v0_1.py"
FIXTURE_PATH = (
    ROOT
    / "fixtures"
    / "trusted-runtime"
    / "durable-approval"
    / "review_decision_adapter_cases_v0.1.json"
)

_spec = importlib.util.spec_from_file_location("review_decision_adapter_v0_1", ADAPTER_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import adapter from {ADAPTER_PATH}")
adapter = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = adapter
_spec.loader.exec_module(adapter)


def load(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class ReviewDecisionAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load(FIXTURE_PATH)

    def case_input(self, case_id: str):
        case = next(case for case in self.fixture["cases"] if case["case_id"] == case_id)
        return copy.deepcopy(case["input"])

    def assert_invalid_with(self, value, fragment: str) -> None:
        result = adapter.project_signal(value)
        self.assertFalse(result["valid"], result)
        self.assertEqual("ADAPTER_ERROR", result["projection"]["outward_status"])
        self.assertEqual("PENDING", result["projection"]["authority_state"])
        self.assertEqual("UNUSED", result["projection"]["execution_state"])
        self.assertTrue(result["projection"]["execution_blocked"])
        self.assertTrue(
            any(fragment in error for error in result["errors"]),
            f"expected error containing {fragment!r}, got {result['errors']}",
        )

    def test_baseline_fixture_passes(self) -> None:
        report = adapter.validate_fixture(copy.deepcopy(self.fixture))
        self.assertTrue(report["passed"], report)
        self.assertTrue(report["invariants"]["adapter_never_invents_user_rejection"])
        self.assertTrue(report["invariants"]["lifecycle_loss_preserves_pending"])
        self.assertTrue(report["invariants"]["safe_projection_is_deterministic"])

    def test_requester_cancellation_is_not_rejection(self) -> None:
        result = adapter.project_signal(self.case_input("requester_cancelled"))
        projection = result["projection"]
        self.assertTrue(result["valid"], result)
        self.assertEqual("RequesterCancelled", projection["durable_event_type"])
        self.assertEqual("PENDING", projection["authority_state"])
        self.assertEqual("CANCELLED", projection["requester_state"])
        self.assertNotEqual("UserRejected", projection["durable_event_type"])
        self.assertTrue(projection["execution_blocked"])

    def test_transport_and_ui_change_presentation_only(self) -> None:
        transport = adapter.project_signal(self.case_input("transport_disconnected"))["projection"]
        dismissed = adapter.project_signal(self.case_input("ui_dismissed"))["projection"]
        self.assertEqual("PENDING", transport["authority_state"])
        self.assertEqual("DISCONNECTED", transport["presentation_state"])
        self.assertEqual("PENDING", dismissed["authority_state"])
        self.assertEqual("NOT_PRESENTED", dismissed["presentation_state"])

    def test_agent_cannot_emit_user_rejection(self) -> None:
        value = self.case_input("explicit_user_rejection")
        value["actor"] = {"type": "AGENT", "id": "agent-root"}
        self.assert_invalid_with(value, "cannot emit USER_REJECTED")

    def test_approval_requires_exact_bindings(self) -> None:
        value = self.case_input("explicit_user_approval")
        value["exact_bindings_match"] = False
        self.assert_invalid_with(value, "requires exact action and scope bindings")

    def test_policy_expiry_requires_configured_policy(self) -> None:
        value = self.case_input("configured_policy_expiry")
        value["expiry_policy_configured"] = False
        self.assert_invalid_with(value, "requires configured expiry policy")

    def test_evidence_backed_signals_require_evidence(self) -> None:
        for case_id in (
            "configured_policy_expiry",
            "verified_context_invalidation",
            "durable_state_loss",
        ):
            with self.subTest(case_id=case_id):
                value = self.case_input(case_id)
                value["evidence_ref"] = None
                self.assert_invalid_with(value, "requires evidence_ref")

    def test_unsupported_single_status_fails_closed(self) -> None:
        value = self.case_input("requester_cancelled")
        value["signal"] = "DENIED"
        self.assert_invalid_with(value, "unsupported signal")

    def test_unknown_input_field_fails_closed(self) -> None:
        value = self.case_input("requester_cancelled")
        value["legacy_status"] = "denied"
        self.assert_invalid_with(value, "unsupported fields")

    def test_malformed_signal_type_fails_closed_without_crash(self) -> None:
        value = self.case_input("requester_cancelled")
        value["signal"] = ["REQUESTER_CANCELLED"]
        self.assert_invalid_with(value, "unsupported signal")

    def test_malformed_actor_type_fails_closed_without_crash(self) -> None:
        value = self.case_input("requester_cancelled")
        value["actor"]["type"] = ["AGENT"]
        self.assert_invalid_with(value, "actor.type is required")

    def test_malformed_evidence_type_fails_closed_without_crash(self) -> None:
        value = self.case_input("durable_state_loss")
        value["evidence_ref"] = {"ref": "not-a-string"}
        self.assert_invalid_with(value, "evidence_ref must be null or a non-empty string")

    def test_duplicate_fixture_case_is_rejected(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["cases"].append(copy.deepcopy(fixture["cases"][0]))
        report = adapter.validate_fixture(fixture)
        self.assertFalse(report["passed"], report)
        self.assertTrue(
            any("required adapter cases must appear exactly once" in error for error in report["errors"]),
            report,
        )

    def test_malformed_fixture_case_id_is_rejected_without_crash(self) -> None:
        fixture = copy.deepcopy(self.fixture)
        fixture["cases"][0]["case_id"] = ["explicit_user_approval"]
        report = adapter.validate_fixture(fixture)
        self.assertFalse(report["passed"], report)
        self.assertTrue(
            any("required adapter cases must appear exactly once" in error for error in report["errors"]),
            report,
        )

    def test_projection_is_deterministic(self) -> None:
        value = self.case_input("requester_cancelled")
        self.assertEqual(adapter.project_signal(value), adapter.project_signal(copy.deepcopy(value)))


if __name__ == "__main__":
    unittest.main()
