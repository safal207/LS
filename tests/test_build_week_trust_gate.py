from __future__ import annotations

import copy
import io
import json
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from tools.build_week_trust_gate import CHECK_STATUSES, evaluate, main, render_human


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
        baseline = evaluate(copy.deepcopy(fixture), policy)
        fixture["expected_outcome"] = {
            "verdict": "TRUSTED",
            "reason_code": "ALL_REQUIRED_EVIDENCE_VALID",
        }

        report = evaluate(fixture, policy)

        self.assertEqual("BLOCKED", report["verdict"])
        self.assertEqual("STALE_APPROVAL", report["reason_code"])
        self.assertEqual(baseline["input_digest_sha256"], report["input_digest_sha256"])

    def test_spoofed_reviewer_login_with_user_account_type_is_blocked(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "spoofed-reviewer.json")

        report = evaluate(fixture, policy)

        self.assertEqual(fixture["expected_outcome"]["verdict"], report["verdict"])
        self.assertEqual(fixture["expected_outcome"]["reason_code"], report["reason_code"])
        identity = next(check for check in report["checks"] if check["check_id"] == "review.identity")
        exact_head = next(check for check in report["checks"] if check["check_id"] == "review.exact_head")
        self.assertEqual("FAIL", identity["status"])
        self.assertEqual("PASS", exact_head["status"])

    def test_required_lane_not_run_is_not_collapsed_to_pass_or_fail(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "required-check-not-run.json")

        report = evaluate(fixture, policy)

        self.assertEqual(fixture["expected_outcome"]["verdict"], report["verdict"])
        self.assertEqual(fixture["expected_outcome"]["reason_code"], report["reason_code"])
        security = next(check for check in report["checks"] if check["check_id"] == "lane.security")
        self.assertEqual("NOT_RUN", security["status"])
        self.assertEqual("NOT_RUN", report["decision_input"]["required_lane_statuses"]["security"])
        self.assertFalse(report["side_effects_performed"])

    def test_stale_failed_lane_is_classified_by_commit_binding_first(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "trusted-current-head.json")
        security = next(lane for lane in fixture["lanes"] if lane["name"] == "security")
        security["status"] = "FAIL"
        security["head_sha"] = "f" * 40

        report = evaluate(fixture, policy)

        self.assertEqual("BLOCKED", report["verdict"])
        self.assertEqual("STALE_REQUIRED_LANE", report["reason_code"])
        security_check = next(check for check in report["checks"] if check["check_id"] == "lane.security")
        self.assertEqual(f"FAIL at {'f' * 40}", security_check["observed"])

    def test_current_head_failed_lane_remains_a_lane_failure(self) -> None:
        policy = load(POLICY_PATH)
        fixture = load(FIXTURE_DIR / "trusted-current-head.json")
        security = next(lane for lane in fixture["lanes"] if lane["name"] == "security")
        security["status"] = "FAIL"

        report = evaluate(fixture, policy)

        self.assertEqual("BLOCKED", report["verdict"])
        self.assertEqual("REQUIRED_LANE_FAILED", report["reason_code"])

    def test_report_write_failure_returns_controlled_exit_code(self) -> None:
        stderr = io.StringIO()
        fixture = FIXTURE_DIR / "trusted-current-head.json"
        report_path = ROOT / "unused-report.json"

        with mock.patch.object(Path, "write_text", side_effect=OSError("simulated write failure")):
            with redirect_stderr(stderr):
                exit_code = main(
                    [
                        str(fixture),
                        "--policy",
                        str(POLICY_PATH),
                        "--report-out",
                        str(report_path),
                    ]
                )

        self.assertEqual(2, exit_code)
        self.assertIn("trust-gate output error:", stderr.getvalue())
        self.assertIn("simulated write failure", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

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
