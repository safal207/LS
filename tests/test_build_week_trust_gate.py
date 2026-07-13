from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.build_week_trust_gate import CHECK_STATUSES, evaluate, render_human


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "build-week" / "policy" / "trust-policy.json"
FIXTURE_DIR = ROOT / "build-week" / "demo"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class BuildWeekTrustGateTests(unittest.TestCase):
    def test_stale_approval_is_deterministically_blocked(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "stale-approval.json")

        first = evaluate(fixture, policy)
        second = evaluate(copy.deepcopy(fixture), copy.deepcopy(policy))

        self.assertEqual(first, second)
        self.assertEqual("BLOCKED", fixture["expected_outcome"]["verdict"])
        self.assertEqual(fixture["expected_outcome"]["verdict"], first["verdict"])
        self.assertEqual("STALE_APPROVAL", fixture["expected_outcome"]["reason_code"])
        self.assertEqual(fixture["expected_outcome"]["reason_code"], first["reason_code"])
        self.assertEqual("a" * 40, first["decision_input"]["review_head_sha"])
        self.assertEqual("b" * 40, first["decision_input"]["current_head_sha"])
        self.assertFalse(first["side_effects_performed"])
        self.assertIn("The approval is stale and cannot authorize delivery.", render_human(first))

    def test_current_head_approval_is_trusted_but_still_requires_a_human(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "trusted-current-head.json")

        report = evaluate(fixture, policy)

        self.assertEqual("TRUSTED", fixture["expected_outcome"]["verdict"])
        self.assertEqual(fixture["expected_outcome"]["verdict"], report["verdict"])
        self.assertEqual("ALL_REQUIRED_EVIDENCE_VALID", report["reason_code"])
        self.assertEqual("ELIGIBLE_FOR_HUMAN_AUTHORIZED_DELIVERY", report["delivery_state"])
        self.assertTrue(report["human_authorization_required"])
        self.assertFalse(report["side_effects_performed"])
        self.assertTrue(all(check["status"] == "PASS" for check in report["checks"]))

    def test_fixture_expectation_cannot_self_authorize(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "stale-approval.json")
        fixture["expected_outcome"] = {
            "verdict": "TRUSTED",
            "reason_code": "ALL_REQUIRED_EVIDENCE_VALID",
        }

        report = evaluate(fixture, policy)

        self.assertEqual("BLOCKED", report["verdict"])
        self.assertEqual("STALE_APPROVAL", report["reason_code"])

    def test_machine_report_keeps_three_check_states_distinct(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "trusted-current-head.json")

        report = evaluate(fixture, policy)

        self.assertEqual(("PASS", "FAIL", "NOT_RUN"), CHECK_STATUSES)
        self.assertEqual(set(CHECK_STATUSES), set(report["status_vocabulary"]))
        self.assertNotEqual(
            report["status_vocabulary"]["PASS"],
            report["status_vocabulary"]["NOT_RUN"],
        )


if __name__ == "__main__":
    unittest.main()
