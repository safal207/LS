#!/usr/bin/env python3
"""Regression tests for tools/build_ls_audit_pack.py."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import build_ls_audit_pack as audit_pack


class LSAuditPackBuilderTest(unittest.TestCase):
    def valid_report(self) -> dict[str, object]:
        return {
            "schema_version": "ls.manual_real_model_audit_report.v0.1",
            "case_id": audit_pack.DEFAULT_CASE_ID,
            "model_attestation": {
                "provider": "LS",
                "model": "LS deterministic",
                "channel": "LS_RUN",
                "operator_note": "Independent LS audit of merged PR #824.",
            },
            "verdict": "APPROVE",
            "findings": [],
            "limitations": [],
        }

    def test_valid_report_passes_validation(self) -> None:
        errors = audit_pack.validate_ls_response(
            self.valid_report(),
            audit_pack.DEFAULT_CASE_ID,
        )
        self.assertEqual(errors, [])

    def test_non_object_report_returns_structured_error(self) -> None:
        errors = audit_pack.validate_ls_response([], audit_pack.DEFAULT_CASE_ID)
        self.assertEqual(errors, ["report must be an object"])

    def test_invalid_verdict_is_rejected(self) -> None:
        report = self.valid_report()
        report["verdict"] = "APPROVE | REQUEST_CHANGES | INCOMPLETE"
        errors = audit_pack.validate_ls_response(report, audit_pack.DEFAULT_CASE_ID)
        self.assertIn(
            "verdict must be one of ['APPROVE', 'INCOMPLETE', 'REQUEST_CHANGES']",
            errors,
        )

    def test_expected_schema_uses_concrete_verdict_and_allowed_values(self) -> None:
        schema = audit_pack.build_expected_report_schema(audit_pack.DEFAULT_CASE_ID)
        self.assertEqual(schema["verdict"], "APPROVE")
        self.assertEqual(
            schema["verdict_allowed_values"],
            ["APPROVE", "INCOMPLETE", "REQUEST_CHANGES"],
        )

    def test_positive_int_rejects_invalid_values(self) -> None:
        self.assertEqual(audit_pack.positive_int("825"), 825)
        with self.assertRaises(Exception):
            audit_pack.positive_int("not-a-number")
        with self.assertRaises(Exception):
            audit_pack.positive_int("0")

    def test_display_path_handles_absolute_path_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            absolute_path = Path(tmp_dir).resolve()
            self.assertEqual(audit_pack.display_path(absolute_path), str(absolute_path))

    def test_build_scorecard_uses_supplied_case_id(self) -> None:
        scorecard = audit_pack.build_scorecard("case-x", None, [])
        self.assertEqual(scorecard["case_id"], "case-x")
        self.assertEqual(scorecard["ls_result"]["status"], "PENDING")


if __name__ == "__main__":
    unittest.main()
