from __future__ import annotations

import json
import sys
import urllib.error
import unittest
from pathlib import Path

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
    load_manifest,
    normalize_repo_path,
    _RejectRedirectHandler,
)


BASE_SHA = "a" * 40
HEAD_SHA = "b" * 40
BLOB_A = "c" * 40
BLOB_B = "d" * 40


def manifest_value(**overrides):
    value = {
        "schema_version": "ls.exact_head_acquisition_manifest.v0.1",
        "repository": "safal207/LS",
        "pr_number": 796,
        "expected_base_sha": BASE_SHA,
        "expected_head_sha": HEAD_SHA,
        "expected_changed_file_count": 1,
        "artifact_paths": ["tools/validate.py"],
        "related_artifacts": [],
        "selection_mode": "ALL_CHANGED",
        "max_file_bytes": 1000,
        "max_total_bytes": 2000,
    }
    value.update(overrides)
    return value


class FakeClient:
    def __init__(
        self,
        *,
        base_sha=BASE_SHA,
        head_sha=HEAD_SHA,
        changed=None,
        files=None,
        snapshots=None,
        reported_changed_count=None,
    ):
        self.base_sha = base_sha
        self.head_sha = head_sha
        self.snapshots = list(snapshots or [])
        self.pr_calls = 0
        self.changed = changed or ["tools/validate.py"]
        self.reported_changed_count = (
            len(self.changed)
            if reported_changed_count is None
            else reported_changed_count
        )
        self.files = files or {
            "tools/validate.py": FetchedArtifact(
                path="tools/validate.py",
                git_blob_sha=BLOB_A,
                content=b"print('ok')\n",
            )
        }
        self.fetch_calls = []
        self.list_calls = 0
        self.list_call_args = []

    def get_pull_request(self, repository, pr_number):
        self.pr_calls += 1
        if self.snapshots:
            index = min(self.pr_calls - 1, len(self.snapshots) - 1)
            base_sha, head_sha = self.snapshots[index]
        else:
            base_sha, head_sha = self.base_sha, self.head_sha
        return PullRequestSnapshot(
            repository,
            pr_number,
            base_sha,
            head_sha,
            self.reported_changed_count,
        )

    def list_changed_paths(self, repository, base_sha, head_sha):
        self.list_calls += 1
        self.list_call_args.append((repository, base_sha, head_sha))
        return list(self.changed)

    def fetch_artifact(self, repository, head_sha, path):
        self.fetch_calls.append((repository, head_sha, path))
        return self.files[path]


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class FakeOpener:
    def __init__(self, *, payload: bytes = b"{}", error=None):
        self.payload = payload
        self.error = error

    def open(self, request, timeout):
        if self.error is not None:
            raise self.error
        return FakeResponse(self.payload)


class ExactHeadAcquisitionTests(unittest.TestCase):
    def test_head_drift_aborts_before_listing_or_fetching(self):
        manifest = AcquisitionManifest.from_dict(manifest_value())
        client = FakeClient(head_sha="e" * 40)
        with self.assertRaisesRegex(ValueError, "head SHA drift"):
            acquire_exact_head_bundle(manifest, client)
        self.assertEqual(client.list_calls, 0)
        self.assertEqual(client.fetch_calls, [])

    def test_mid_acquisition_head_drift_discards_bundle(self):
        manifest = AcquisitionManifest.from_dict(manifest_value())
        client = FakeClient(
            snapshots=[
                (BASE_SHA, HEAD_SHA),
                (BASE_SHA, "e" * 40),
            ]
        )
        with self.assertRaisesRegex(ValueError, "changed during acquisition"):
            acquire_exact_head_bundle(manifest, client)
        self.assertEqual(client.pr_calls, 2)
        self.assertEqual(len(client.fetch_calls), 1)

    def test_all_changed_mode_rejects_omitted_changed_files(self):
        manifest = AcquisitionManifest.from_dict(
            manifest_value(expected_changed_file_count=2)
        )
        client = FakeClient(changed=["tools/validate.py", "tools/test_validate.py"])
        with self.assertRaisesRegex(ValueError, "ALL_CHANGED selection mismatch"):
            acquire_exact_head_bundle(manifest, client)
        self.assertEqual(client.fetch_calls, [])

    def test_changed_file_metadata_must_match_listing(self):
        manifest = AcquisitionManifest.from_dict(
            manifest_value(expected_changed_file_count=2)
        )
        client = FakeClient(
            changed=["tools/validate.py"],
            reported_changed_count=2,
        )
        with self.assertRaisesRegex(ValueError, "listing is incomplete"):
            acquire_exact_head_bundle(manifest, client)
        self.assertEqual(client.fetch_calls, [])

    def test_changed_file_count_drift_aborts_before_listing(self):
        manifest = AcquisitionManifest.from_dict(manifest_value())
        client = FakeClient(reported_changed_count=2)
        with self.assertRaisesRegex(ValueError, "changed-file count drift"):
            acquire_exact_head_bundle(manifest, client)
        self.assertEqual(client.list_calls, 0)
        self.assertEqual(client.fetch_calls, [])

    def test_changed_listing_is_pinned_to_exact_commit_pair(self):
        manifest = AcquisitionManifest.from_dict(manifest_value())
        client = FakeClient()
        acquire_exact_head_bundle(manifest, client)
        self.assertEqual(
            client.list_call_args,
            [("safal207/LS", BASE_SHA, HEAD_SHA)],
        )

    def test_fetch_uses_exact_commit_sha_and_records_hashes(self):
        manifest = AcquisitionManifest.from_dict(manifest_value())
        client = FakeClient()
        bundle = acquire_exact_head_bundle(manifest, client)
        self.assertEqual(
            client.fetch_calls,
            [("safal207/LS", HEAD_SHA, "tools/validate.py")],
        )
        artifact = bundle.artifacts[0]
        self.assertEqual(artifact.repository, "safal207/LS")
        self.assertEqual(artifact.pr_number, 796)
        self.assertEqual(artifact.base_sha, BASE_SHA)
        self.assertEqual(artifact.head_sha, HEAD_SHA)
        self.assertEqual(artifact.admission, "CHANGED")
        self.assertEqual(artifact.git_blob_sha, BLOB_A)
        self.assertEqual(artifact.byte_length, len(b"print('ok')\n"))
        self.assertEqual(len(artifact.content_sha256), 64)
        self.assertEqual(len(bundle.evidence_sha256), 64)

    def test_related_path_requires_explicit_admission(self):
        direct = "tools/validate.py"
        related = "fixtures/schema.json"
        manifest = AcquisitionManifest.from_dict(
            manifest_value(
                related_artifacts=[
                    {
                        "source_path": direct,
                        "path": related,
                        "relation": "IMPLEMENTS",
                        "evidence": "validator loads this schema path",
                    }
                ]
            )
        )
        client = FakeClient(
            changed=[direct],
            files={
                direct: FetchedArtifact(direct, BLOB_A, b"validator\n"),
                related: FetchedArtifact(related, BLOB_B, b"{}\n"),
            },
        )
        bundle = acquire_exact_head_bundle(manifest, client)
        by_path = {artifact.path: artifact for artifact in bundle.artifacts}
        self.assertEqual(by_path[related].admission, "RELATED")
        self.assertEqual(by_path[related].relation, "IMPLEMENTS")
        self.assertEqual(by_path[related].relation_source_path, direct)

    def test_changed_artifact_cannot_be_relabeled_as_related(self):
        manifest = AcquisitionManifest.from_dict(
            manifest_value(
                selection_mode="DECLARED_SUBSET",
                expected_changed_file_count=2,
                related_artifacts=[
                    {
                        "source_path": "tools/validate.py",
                        "path": "fixtures/schema.json",
                        "relation": "IMPLEMENTS",
                        "evidence": "validator loads schema",
                    }
                ],
            )
        )
        client = FakeClient(
            changed=["tools/validate.py", "fixtures/schema.json"],
            reported_changed_count=2,
        )
        with self.assertRaisesRegex(ValueError, "cannot be admitted as RELATED"):
            acquire_exact_head_bundle(manifest, client)

    def test_direct_artifact_must_be_changed(self):
        manifest = AcquisitionManifest.from_dict(manifest_value())
        client = FakeClient(changed=["README.md"])
        with self.assertRaisesRegex(ValueError, "not changed"):
            acquire_exact_head_bundle(manifest, client)
        self.assertEqual(client.fetch_calls, [])

    def test_path_traversal_aliases_and_duplicates_are_rejected(self):
        for invalid in ("../secret", "/absolute", "a//b", "a/./b", "a\\b", "dir/"):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    normalize_repo_path(invalid)
        with self.assertRaisesRegex(ValueError, "unique"):
            AcquisitionManifest.from_dict(
                manifest_value(
                    artifact_paths=["tools/validate.py"],
                    related_artifacts=[
                        {
                            "source_path": "tools/validate.py",
                            "path": "tools/validate.py",
                            "relation": "TESTS",
                            "evidence": "duplicate",
                        }
                    ],
                )
            )

    def test_size_limits_fail_closed(self):
        manifest = AcquisitionManifest.from_dict(
            manifest_value(max_file_bytes=3, max_total_bytes=10)
        )
        client = FakeClient(
            files={
                "tools/validate.py": FetchedArtifact(
                    "tools/validate.py", BLOB_A, b"four"
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "max_file_bytes"):
            acquire_exact_head_bundle(manifest, client)

        manifest = AcquisitionManifest.from_dict(
            manifest_value(
                artifact_paths=["a.txt", "b.txt"],
                expected_changed_file_count=2,
                max_file_bytes=5,
                max_total_bytes=5,
            )
        )
        client = FakeClient(
            changed=["a.txt", "b.txt"],
            files={
                "a.txt": FetchedArtifact("a.txt", BLOB_A, b"aaa"),
                "b.txt": FetchedArtifact("b.txt", BLOB_B, b"bbb"),
            },
        )
        with self.assertRaisesRegex(ValueError, "max_total_bytes"):
            acquire_exact_head_bundle(manifest, client)

    def test_bundle_hash_is_independent_of_manifest_path_order(self):
        files = {
            "a.txt": FetchedArtifact("a.txt", BLOB_A, b"A\n"),
            "b.txt": FetchedArtifact("b.txt", BLOB_B, b"B\n"),
        }
        first = AcquisitionManifest.from_dict(
            manifest_value(
                artifact_paths=["b.txt", "a.txt"],
                expected_changed_file_count=2,
            )
        )
        second = AcquisitionManifest.from_dict(
            manifest_value(
                artifact_paths=["a.txt", "b.txt"],
                expected_changed_file_count=2,
            )
        )
        first_bundle = acquire_exact_head_bundle(
            first, FakeClient(changed=["a.txt", "b.txt"], files=files)
        )
        second_bundle = acquire_exact_head_bundle(
            second, FakeClient(changed=["b.txt", "a.txt"], files=files)
        )
        self.assertEqual(first_bundle.evidence_sha256, second_bundle.evidence_sha256)
        self.assertEqual(
            [item.path for item in first_bundle.artifacts],
            ["a.txt", "b.txt"],
        )

    def test_invalid_utf8_is_rejected(self):
        manifest = AcquisitionManifest.from_dict(manifest_value())
        client = FakeClient(
            files={
                "tools/validate.py": FetchedArtifact(
                    "tools/validate.py", BLOB_A, b"\xff"
                )
            }
        )
        with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
            acquire_exact_head_bundle(manifest, client)

    def test_redirect_handler_rejects_redirects(self):
        handler = _RejectRedirectHandler()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example")
        )

    def test_transport_errors_include_api_path(self):
        client = GitHubRestClient(
            opener=FakeOpener(error=urllib.error.URLError("offline"))
        )
        with self.assertRaisesRegex(RuntimeError, "/repos/safal207/LS/pulls/796"):
            client._request_json("/repos/safal207/LS/pulls/796")

    def test_invalid_api_json_includes_api_path(self):
        client = GitHubRestClient(opener=FakeOpener(payload=b"not-json"))
        with self.assertRaisesRegex(RuntimeError, "/repos/safal207/LS/pulls/796"):
            client._request_json("/repos/safal207/LS/pulls/796")

    def test_pr796_calibration_manifest_uses_real_changed_paths(self):
        manifest_path = (
            ROOT / "benchmarks/exact-head/pr796-calibration-v0.1.json"
        )
        manifest = load_manifest(manifest_path)
        expected = {
            ".github/workflows/durable-approval-fixtures.yml",
            "fixtures/trusted-runtime/durable-approval/CONFORMANCE.md",
            "fixtures/trusted-runtime/durable-approval/README.md",
            "fixtures/trusted-runtime/durable-approval/configured_policy_expiry_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/durable_state_loss_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/envelope.schema.json",
            "fixtures/trusted-runtime/durable-approval/event.schema.json",
            "fixtures/trusted-runtime/durable-approval/pending_approval_not_missing_authority_v0.1.json",
            "fixtures/trusted-runtime/durable-approval/reconcile_in_doubt_committed_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/reconcile_in_doubt_failed_v0.2.json",
            "fixtures/trusted-runtime/durable-approval/verified_context_invalidation_v0.2.json",
            "spec/durable-approval-conformance-v0.1.md",
            "spec/durable-approval-conformance-v0.2.md",
            "tools/test_durable_approval_v0_1.py",
            "tools/test_durable_approval_v0_2.py",
            "tools/validate_durable_approval_v0_1.py",
            "tools/validate_durable_approval_v0_2.py",
        }
        self.assertEqual(manifest.repository, "safal207/LS")
        self.assertEqual(manifest.pr_number, 796)
        self.assertEqual(manifest.expected_changed_file_count, 17)
        self.assertEqual(
            manifest.expected_head_sha,
            "a9bcc1c550f1139cd0233ecc8b05837d5c6d558c",
        )
        self.assertEqual(set(manifest.artifact_paths), expected)
        self.assertEqual(manifest.related_artifacts, ())
        self.assertEqual(manifest.selection_mode, "ALL_CHANGED")


if __name__ == "__main__":
    unittest.main()
