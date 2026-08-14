#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "update_reopen_cases.json"
sys.path.insert(0, str(HERE))

from run_update_reopen_fixture import evaluate, summarize_reports  # noqa: E402


class UpdateReopenProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def test_frozen_cases_match_expected_verdicts(self) -> None:
        for case in self.payload["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate(case)
                for key, expected in case["expected"].items():
                    self.assertEqual(expected, report[key], f"{case['case_id']}:{key}")

    def test_ordinary_update_reopen_blocks_silent_projection_loss(self) -> None:
        case = next(
            item
            for item in self.payload["cases"]
            if item["case_id"] == "ordinary_update_reopen_preserves_projection"
        )
        report = evaluate(case)
        self.assertEqual("BLOCK_REGRESSIVE_PROJECTION", report["status"])
        self.assertEqual(2, report["missing_project_memberships"])
        self.assertEqual(2, report["dropped_pins"])
        self.assertEqual(9, report["accepted_generation"])
        self.assertEqual(3, report["accepted_project_memberships"])
        self.assertEqual(2, report["accepted_pins"])

    def test_explicit_user_mutation_is_not_misclassified_as_data_loss(self) -> None:
        case = next(
            item
            for item in self.payload["cases"]
            if item["case_id"] == "explicit_user_mutation_can_reduce_projection"
        )
        report = evaluate(case)
        self.assertTrue(report["explicit_user_mutation"])
        self.assertEqual("ACCEPT_CANDIDATE", report["status"])
        self.assertEqual(31, report["accepted_generation"])

    def test_stale_startup_writer_is_blocked(self) -> None:
        case = next(
            item
            for item in self.payload["cases"]
            if item["case_id"] == "stale_update_reopen_candidate_blocked"
        )
        report = evaluate(case)
        self.assertEqual("BLOCK_STALE_GENERATION", report["status"])
        self.assertEqual(42, report["accepted_generation"])

    def test_report_is_redaction_safe(self) -> None:
        for case in self.payload["cases"]:
            report_text = json.dumps(evaluate(case), sort_keys=True)
            self.assertNotIn("C:\\\\work", report_text)
            self.assertNotIn('"t1"', report_text)
            self.assertNotIn('"p-alpha"', report_text)
            self.assertNotIn("sha256:content", report_text)

    def test_cli_summary_does_not_cross_fixture_identity_boundary(self) -> None:
        reports = [evaluate(case) for case in self.payload["cases"]]
        summary_text = json.dumps(summarize_reports(reports), sort_keys=True)
        for case in self.payload["cases"]:
            self.assertNotIn(case["case_id"], summary_text)
        self.assertNotIn("trigger", summary_text)
        self.assertNotIn("generation", summary_text)
        self.assertEqual(len(reports), summarize_reports(reports)["case_count"])


if __name__ == "__main__":
    unittest.main()
