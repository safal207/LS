from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts" / "multi_model_review"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from exact_head_acquisition import (  # noqa: E402
    AcquisitionManifest,
    FetchedArtifact,
    GitHubRestClient,
    PullRequestSnapshot,
    acquire_exact_head_bundle,
)

BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40
BLOB_SHA = "c" * 40


class RelatedClient:
    def get_pull_request(self, repository, pr_number):
        return PullRequestSnapshot(repository, pr_number, BASE_SHA, HEAD_SHA, 1)

    def list_changed_paths(self, repository, base_sha, head_sha):
        return ["tools/validate.py"]

    def fetch_artifact(self, repository, head_sha, path):
        return FetchedArtifact(path, BLOB_SHA, b"{}\n")


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

    def test_pull_request_response_shape_fails_with_api_context(self) -> None:
        client = GitHubRestClient()
        api_path = "/repos/safal207/LS/pulls/796"
        malformed_values = (
            None,
            {},
            {"base": {}, "head": {"sha": HEAD_SHA}, "changed_files": 1},
            {"base": {"sha": BASE_SHA}, "head": {}, "changed_files": 1},
            {"base": {"sha": BASE_SHA}, "head": {"sha": HEAD_SHA}, "changed_files": "1"},
        )
        for malformed in malformed_values:
            with self.subTest(value=malformed), patch.object(
                client, "_request_json", return_value=malformed
            ):
                with self.assertRaisesRegex(RuntimeError, api_path):
                    client.get_pull_request("safal207/LS", 796)

    def test_contents_response_shape_fails_with_artifact_context(self) -> None:
        client = GitHubRestClient()
        malformed_values = (
            None,
            {"type": "file", "encoding": "base64"},
            {"type": "file", "encoding": "base64", "path": "a.py", "sha": BLOB_SHA},
            {
                "type": "file",
                "encoding": "base64",
                "path": "a.py",
                "sha": "bad",
                "content": "e30=",
            },
        )
        for malformed in malformed_values:
            with self.subTest(value=malformed), patch.object(
                client, "_request_json", return_value=malformed
            ):
                with self.assertRaisesRegex(RuntimeError, "a.py"):
                    client.fetch_artifact("safal207/LS", HEAD_SHA, "a.py")

    def test_related_artifact_records_relation_evidence(self) -> None:
        manifest = AcquisitionManifest.from_dict(
            {
                "schema_version": "ls.exact_head_acquisition_manifest.v0.1",
                "repository": "safal207/LS",
                "pr_number": 796,
                "expected_base_sha": BASE_SHA,
                "expected_head_sha": HEAD_SHA,
                "expected_changed_file_count": 1,
                "artifact_paths": ["tools/validate.py"],
                "related_artifacts": [
                    {
                        "source_path": "tools/validate.py",
                        "path": "fixtures/schema.json",
                        "relation": "IMPLEMENTS",
                        "evidence": "validator loads this schema path",
                    }
                ],
                "selection_mode": "ALL_CHANGED",
                "max_file_bytes": 1000,
                "max_total_bytes": 2000,
            }
        )
        bundle = acquire_exact_head_bundle(manifest, RelatedClient())
        related = {artifact.path: artifact for artifact in bundle.artifacts}[
            "fixtures/schema.json"
        ]
        self.assertEqual(related.relation_evidence, "validator loads this schema path")


if __name__ == "__main__":
    unittest.main()
