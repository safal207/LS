#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures" / "cases.json"
sys.path.insert(0, str(HERE))

from run_fixture import evaluate, normalize_windows_path  # noqa: E402


class StateProjectionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(FIXTURES.read_text(encoding="utf-8"))

    def test_frozen_cases_match_expected_verdicts(self) -> None:
        for case in self.payload["cases"]:
            with self.subTest(case_id=case["case_id"]):
                report = evaluate(case)
                for key, expected in case["expected"].items():
                    if key == "thread_workspace_root_hints_capability":
                        actual = report["capabilities"]["thread_workspace_root_hints"]
                    else:
                        actual = report[key]
                    self.assertEqual(expected, actual, f"{case['case_id']}:{key}")

    def test_windows_verbatim_and_normal_paths_are_equivalent(self) -> None:
        normal = normalize_windows_path(r"C:\Work\Project\src")
        verbatim = normalize_windows_path(r"\\?\C:\Work\Project\src")
        self.assertEqual(normal, verbatim)

    def test_redacted_report_does_not_emit_fixture_paths_or_thread_ids(self) -> None:
        for case in self.payload["cases"]:
            report_text = json.dumps(evaluate(case), sort_keys=True)
            self.assertNotIn("C:\\\\work", report_text)
            self.assertNotIn("D:\\\\projects", report_text)
            self.assertNotIn('"t1"', report_text)
            self.assertNotIn('"p-alpha"', report_text)

    def test_recovery_is_idempotent_for_successful_cases(self) -> None:
        for case in self.payload["cases"]:
            report = evaluate(case)
            if report["status"] in {"RECOVERED_PROJECTION", "NO_CHANGES_REQUIRED"}:
                with self.subTest(case_id=case["case_id"]):
                    self.assertEqual(0, report["second_run_semantic_changes"])

    def test_content_mutation_never_becomes_recovery_success(self) -> None:
        case = next(
            item
            for item in self.payload["cases"]
            if item["case_id"] == "conversation_content_mutation_rejected"
        )
        report = evaluate(case)
        self.assertEqual("BLOCK_CONTENT_MUTATION", report["status"])
        self.assertEqual(1, report["conversation_content_mutations"])
        self.assertEqual(0, report["semantic_changes"])

    def test_stale_generation_never_overwrites_durable_projection(self) -> None:
        case = next(
            item
            for item in self.payload["cases"]
            if item["case_id"] == "stale_generation_overwrites_richer_projection"
        )
        report = evaluate(case)
        self.assertEqual("BLOCK_STALE_GENERATION", report["status"])
        self.assertEqual(0, report["semantic_changes"])
        self.assertEqual(2, report["assignments_after"])


if __name__ == "__main__":
    unittest.main()
