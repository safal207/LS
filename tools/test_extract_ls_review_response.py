#!/usr/bin/env python3
"""Regression tests for tools/extract_ls_review_response.py."""

from __future__ import annotations

import unittest

import build_ls_audit_pack as audit_pack
import extract_ls_review_response as extractor


PARTIAL_COMMENT = """<!-- ls-multi-model-review -->
## LS multi-model PR review

- Exact head: `0b953d3428adca691421dddd861e20e1c0213b47`
- Base: `3c0ffacb5a9b669f5d07f0745f72ed015eef96db`
- Provider: `openrouter`
- Status: **PARTIAL**
- Aggregate verdict: **COMMENT**
- Mode: `advisory`
- High-risk route: `true`
- Diff truncated: `false`
- Files represented in bounded evidence: `3/3`
- Policy would block: `true`

### Model executions

| Role | Model | Status | Verdict |
| --- | --- | --- | --- |
| - | - | NOT_RUN | - |

### Confirmed findings

No finding reached independent two-model confirmation.
### Candidate findings

No structured candidate finding was produced.

### Incomplete lanes

- `provider`: {'key': 'provider', 'reason': 'provider credential is not configured'}

### Authority boundary

This output is evidence for human review.
"""


APPROVE_COMMENT = """<!-- ls-multi-model-review -->
## LS multi-model PR review

- Exact head: `abc123`
- Status: **COMPLETE**
- Aggregate verdict: **APPROVE**

### Confirmed findings

No finding reached independent two-model confirmation.
"""


class LSReviewResponseExtractionTest(unittest.TestCase):
    def test_latest_ls_review_comment_ignores_unrelated_comments(self) -> None:
        comments = [
            {"body": "hello"},
            {"body": PARTIAL_COMMENT, "created_at": "2026-07-08T12:55:43Z"},
        ]
        selected = extractor.latest_ls_review_comment(comments)
        self.assertIsNotNone(selected)
        self.assertIn("LS multi-model PR review", selected["body"])

    def test_partial_comment_becomes_incomplete_response(self) -> None:
        response = extractor.build_response(
            {
                "id": 4914994285,
                "body": PARTIAL_COMMENT,
                "created_at": "2026-07-08T12:55:43Z",
            },
            "pr824-ls-audit-v0.1",
            828,
            824,
            audit_pack.DEFAULT_COMMIT_SHA,
        )
        self.assertEqual(response["schema_version"], extractor.SCHEMA_VERSION)
        self.assertEqual(response["case_id"], "pr824-ls-audit-v0.1")
        self.assertEqual(response["model_attestation"]["provider"], "LS")
        self.assertEqual(response["verdict"], "INCOMPLETE")
        self.assertEqual(response["findings"], [])
        self.assertEqual(response["subject"]["pr_number"], 824)
        self.assertEqual(response["source"]["source_pr_number"], 828)
        self.assertEqual(response["source"]["source_comment_id"], 4914994285)
        self.assertEqual(response["source"]["reviewed_pr_number"], 828)
        self.assertEqual(
            response["source"]["reviewed_commit_sha"],
            "0b953d3428adca691421dddd861e20e1c0213b47",
        )
        self.assertTrue(
            any("provider credential is not configured" in item for item in response["limitations"])
        )
        self.assertTrue(any("NOT_RUN" in item for item in response["limitations"]))

    def test_complete_approve_comment_stays_approve(self) -> None:
        response = extractor.build_response(
            {
                "id": 123,
                "body": APPROVE_COMMENT,
                "created_at": "2026-07-08T12:55:43Z",
            },
            "case-x",
            830,
        )
        self.assertEqual(response["verdict"], "APPROVE")
        self.assertEqual(response["limitations"], [])

    def test_extracted_same_pr_response_passes_provenance_validation(self) -> None:
        response = extractor.build_response(
            {
                "id": 123,
                "body": APPROVE_COMMENT,
                "created_at": "2026-07-08T12:55:43Z",
            },
            "case-x",
            830,
            830,
            "abc123",
        )

        errors = audit_pack.validate_ls_response(response, "case-x", 830, "abc123")
        self.assertEqual(errors, [])

    def test_extracted_cross_pr_response_cannot_relabel_reviewed_target(self) -> None:
        response = extractor.build_response(
            {
                "id": 4914994285,
                "body": PARTIAL_COMMENT,
                "created_at": "2026-07-08T12:55:43Z",
            },
            "pr824-ls-audit-v0.1",
            828,
            824,
            audit_pack.DEFAULT_COMMIT_SHA,
        )

        errors = audit_pack.validate_ls_response(
            response,
            "pr824-ls-audit-v0.1",
            824,
            audit_pack.DEFAULT_COMMIT_SHA,
        )

        self.assertIn("provenance mismatch: source.reviewed_pr_number must be 824", errors)
        self.assertIn(
            "provenance mismatch: source.reviewed_commit_sha must be "
            f"{audit_pack.DEFAULT_COMMIT_SHA!r}",
            errors,
        )

    def test_missing_comment_returns_none(self) -> None:
        self.assertIsNone(extractor.latest_ls_review_comment([{"body": "no marker"}]))


if __name__ == "__main__":
    unittest.main()
