from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import run_multi_model_pr_review as review  # noqa: E402

BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40


class MultiModelReviewTransportTests(unittest.TestCase):
    def test_deterministic_provider_error_is_not_retried(self):
        calls = []
        sleeps = []

        def transport(url, headers, payload, timeout):
            calls.append(url)
            raise review.ReviewRuntimeError("provider returned invalid JSON")

        client = review.OpenRouterClient(
            base_url="https://example.test/v1",
            api_key="test-value",
            timeout_seconds=5,
            max_attempts=3,
            transport=transport,
            sleeper=sleeps.append,
        )
        with self.assertRaisesRegex(review.ReviewRuntimeError, "invalid JSON"):
            client.catalog()
        self.assertEqual(len(calls), 1)
        self.assertEqual(sleeps, [])

    def test_transient_network_error_keeps_bounded_retry(self):
        calls = []
        sleeps = []

        def transport(url, headers, payload, timeout):
            calls.append(url)
            raise URLError("offline")

        client = review.OpenRouterClient(
            base_url="https://example.test/v1",
            api_key="test-value",
            timeout_seconds=5,
            max_attempts=3,
            transport=transport,
            sleeper=sleeps.append,
        )
        with self.assertRaisesRegex(review.ReviewRuntimeError, "after 3 attempt"):
            client.catalog()
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleeps, [1.0, 2.0])

    def test_cli_missing_diff_file_returns_clean_exit_three(self):
        missing = ROOT / "python" / "tests" / "does-not-exist.diff"
        argv = [
            "run_multi_model_pr_review.py",
            "--config",
            str(ROOT / ".github" / "ai-review-models.json"),
            "--diff-file",
            str(missing),
            "--repository",
            "safal207/LS",
            "--pr-number",
            "797",
            "--base-sha",
            BASE_SHA,
            "--head-sha",
            HEAD_SHA,
        ]
        stderr = io.StringIO()
        with patch.object(sys, "argv", argv), patch.dict(
            os.environ, {"OPENROUTER_API_KEY": ""}, clear=False
        ), redirect_stderr(stderr):
            result = review.main()
        self.assertEqual(result, 3)
        self.assertIn("cannot read diff file", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_cli_exports_are_explicit(self):
        self.assertIn("main", review.__all__)
        self.assertIn("parse_args", review.__all__)
        for leaked in ("argparse", "json", "os", "sys", "Path", "annotations"):
            self.assertNotIn(leaked, review.__all__)


if __name__ == "__main__":
    unittest.main()
