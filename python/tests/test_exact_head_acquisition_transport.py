from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "multi_model_review"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from exact_head_acquisition import GitHubRestClient  # noqa: E402

BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40


class ExactHeadAcquisitionTransportTests(unittest.TestCase):
    def test_compare_entries_require_string_filenames(self) -> None:
        client = GitHubRestClient()
        compare_path = f"/repos/safal207/LS/compare/{BASE_SHA}...{HEAD_SHA}"

        for malformed in (None, {}, {"filename": None}, {"filename": ""}):
            with self.subTest(entry=malformed), patch.object(
                client,
                "_request_json",
                return_value={"files": [{"filename": "valid.py"}, malformed]},
            ):
                with self.assertRaisesRegex(RuntimeError, compare_path):
                    client.list_changed_paths("safal207/LS", BASE_SHA, HEAD_SHA)

    def test_compare_returns_validated_filenames_in_order(self) -> None:
        client = GitHubRestClient()
        with patch.object(
            client,
            "_request_json",
            return_value={
                "files": [
                    {"filename": "a.py"},
                    {"filename": "nested/b.py"},
                ]
            },
        ):
            self.assertEqual(
                list(client.list_changed_paths("safal207/LS", BASE_SHA, HEAD_SHA)),
                ["a.py", "nested/b.py"],
            )


if __name__ == "__main__":
    unittest.main()
