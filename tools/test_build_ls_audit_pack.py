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
            "subject": {
                "repository": audit_pack.REPOSITORY,
                "pr_number": audit_pack.DEFAULT_PR_NUMBER,
                "commit_sha": audit_pack.DEFAULT_COMMIT_SHA,
            },
            "source": {
                "type": "LS_RUN",
                "reviewed_pr_number": audit_pack.DEFAULT_PR_NUMBER,
                "reviewed_commit_sha": audit_pack.DEFAULT_COMMIT_SHA,
                "source_pr_number": audit_pack.DEFAULT_PR_NUMBER,
                "source_comment_id": None,
                "source_head_sha": audit_pack.DEFAULT_COMMIT_SHA,
            },
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

    def test_missing_subject_is_rejected(self) -> None:
        report = self.valid_report()
        del report["subject"]
        errors = audit_pack.validate_ls_response(report, audit_pack.DEFAULT_CASE_ID)
        self.assertIn("missing top-level fields: ['subject']", errors)
        self.assertIn("subject must be an object", errors)

    def test_source_reviewed_pr_mismatch_is_rejected(self) -> None:
        report = self.valid_report()
        source = report["source"]
        self.assertIsInstance(source, dict)
        source["reviewed_pr_number"] = 828
        errors = audit_pack.validate_ls_response(report, audit_pack.DEFAULT_CASE_ID)
        self.assertIn("provenance mismatch: source.reviewed_pr_number must be 824", errors)

    def test_source_head_mismatch_is_rejected(self) -> None:
        report = self.valid_report()
        source = report["source"]
        self.assertIsInstance(source, dict)
        source["type"] = "GITHUB_PR_COMMENT"
        source["source_comment_id"] = 4914994285
        source["source_head_sha"] = "0b953d3428adca691421dddd861e20e1c0213b47"
        errors = audit_pack.validate_ls_response(report, audit_pack.DEFAULT_CASE_ID)
        self.assertIn(
            "provenance mismatch: source.source_head_sha must match "
            f"{audit_pack.DEFAULT_COMMIT_SHA!r}",
            errors,
        )

    def test_provenance_errors_get_distinct_scorecard_status(self) -> None:
        scorecard = audit_pack.build_scorecard(
            audit_pack.DEFAULT_CASE_ID,
            self.valid_report(),
            ["provenance mismatch: source.reviewed_pr_number must be 824"],
        )
        self.assertEqual(scorecard["ls_result"]["status"], "PROVENANCE_MISMATCH")

    def test_expected_schema_uses_concrete_verdict_and_allowed_values(self) -> None:
        schema = audit_pack.build_expected_report_schema(audit_pack.DEFAULT_CASE_ID)
        self.assertEqual(schema["verdict"], "APPROVE")
        self.assertEqual(
            schema["verdict_allowed_values"],
            ["APPROVE", "INCOMPLETE", "REQUEST_CHANGES"],
        )
        self.assertEqual(
            schema["source_type_allowed_values"],
            ["GITHUB_PR_COMMENT", "LS_RUN"],
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

    def test_build_scorecard_marks_invalid_non_object_report(self) -> None:
        scorecard = audit_pack.build_scorecard(
            "case-x",
            [],
            ["report must be an object"],
        )
        self.assertEqual(scorecard["case_id"], "case-x")
        self.assertEqual(scorecard["ls_result"]["status"], "INVALID_REPORT")
        self.assertEqual(
            scorecard["ls_result"]["errors"],
            ["report must be an object"],
        )


if __name__ == "__main__":
    unittest.main()
