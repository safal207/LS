import hashlib
import json

import pytest

from tools.causal_review_request import RequestError, verify_collection, write_env


class FakeClient:
    def __init__(
        self,
        *,
        sha="a" * 40,
        patch=b"patch-bytes",
        state="open",
        draft=False,
        head_repository="safal207/LS",
    ):
        self.sha = sha
        self.patch = patch
        self.state = state
        self.draft = draft
        self.head_repository = head_repository

    def get_pull_request(self, repository, pr_number):
        return {
            "state": self.state,
            "draft": self.draft,
            "head": {
                "sha": self.sha,
                "repo": {"full_name": self.head_repository},
            },
        }

    def get_patch(self, repository, pr_number):
        return self.patch


def target(patch=b"patch-bytes"):
    return {
        "repository": "safal207/LS",
        "pr_number": 42,
        "head_sha": "a" * 40,
        "patch_sha256": "sha256:" + hashlib.sha256(patch).hexdigest(),
    }


def write_collection(tmp_path, *, patch=b"patch-bytes", target_value=None):
    target_value = target_value or target(patch)
    manifest = {
        "schema_version": "ls.github-causal-review-collection.v0.1",
        "target": target_value,
        "patch_bytes": len(patch),
        "raw_thread_count": 0,
        "provider_thread_counts": {"coderabbit": 0, "qodo": 0},
        "outputs": {
            "patch": "target.patch",
            "raw_threads": "github-review-threads.raw.json",
            "bundles": {
                "coderabbit": "coderabbit-bundle.json",
                "qodo": "qodo-bundle.json",
            },
        },
    }
    (tmp_path / "collection-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (tmp_path / "target.patch").write_bytes(patch)
    for provider in ("coderabbit", "qodo"):
        bundle = {
            "provider": provider,
            "target": target_value,
            "execution": {
                "status": "DIAGNOSTIC",
                "provenance": "UNVERIFIED",
                "details": "No thread found.",
            },
            "threads": [],
            "dedupe_overrides": {},
        }
        (tmp_path / f"{provider}-bundle.json").write_text(
            json.dumps(bundle), encoding="utf-8"
        )


def test_verified_request_rechecks_exact_current_patch(tmp_path):
    patch = b"exact patch\n"
    write_collection(tmp_path, patch=patch)
    request = verify_collection(
        FakeClient(patch=patch),
        tmp_path,
        "safal207/LS",
        source_run_id=123,
        expected_pr_number=42,
    )

    assert request["status"] == "MATCHED"
    assert request["source_run_id"] == 123
    assert request["target"] == target(patch)
    assert request["head_repository"] == "safal207/LS"
    assert request["patch_bytes"] == len(patch)


def test_triggering_pr_mismatch_fails_closed(tmp_path):
    write_collection(tmp_path)
    with pytest.raises(RequestError, match="triggering PR mismatch"):
        verify_collection(
            FakeClient(),
            tmp_path,
            "safal207/LS",
            source_run_id=1,
            expected_pr_number=99,
        )


def test_fork_pr_is_not_authorized_by_default(tmp_path):
    write_collection(tmp_path)
    with pytest.raises(RequestError, match="fork PRs are not authorized"):
        verify_collection(
            FakeClient(head_repository="attacker/fork"),
            tmp_path,
            "safal207/LS",
            source_run_id=1,
            expected_pr_number=42,
        )


def test_explicit_fork_policy_can_be_enabled(tmp_path):
    write_collection(tmp_path)
    request = verify_collection(
        FakeClient(head_repository="contributor/fork"),
        tmp_path,
        "safal207/LS",
        source_run_id=1,
        expected_pr_number=42,
        require_same_repository_head=False,
    )
    assert request["head_repository"] == "contributor/fork"


def test_persisted_patch_digest_mismatch_fails_closed(tmp_path):
    write_collection(tmp_path)
    (tmp_path / "target.patch").write_bytes(b"tampered")
    with pytest.raises(RequestError, match="persisted patch bytes"):
        verify_collection(FakeClient(), tmp_path, "safal207/LS", source_run_id=1)


def test_current_head_change_fails_closed(tmp_path):
    write_collection(tmp_path)
    with pytest.raises(RequestError, match="head changed after collection"):
        verify_collection(
            FakeClient(sha="c" * 40), tmp_path, "safal207/LS", source_run_id=1
        )


def test_current_patch_change_fails_closed(tmp_path):
    write_collection(tmp_path)
    with pytest.raises(RequestError, match="current GitHub patch digest"):
        verify_collection(
            FakeClient(patch=b"different"), tmp_path, "safal207/LS", source_run_id=1
        )


def test_repository_mismatch_fails_closed(tmp_path):
    write_collection(tmp_path)
    with pytest.raises(RequestError, match="repository mismatch"):
        verify_collection(FakeClient(), tmp_path, "other/repo", source_run_id=1)


def test_bundle_target_mismatch_fails_closed(tmp_path):
    write_collection(tmp_path)
    bundle_path = tmp_path / "qodo-bundle.json"
    bundle = json.loads(bundle_path.read_text())
    bundle["target"]["head_sha"] = "c" * 40
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    with pytest.raises(RequestError, match="qodo bundle target mismatch"):
        verify_collection(FakeClient(), tmp_path, "safal207/LS", source_run_id=1)


def test_draft_or_closed_target_fails_closed(tmp_path):
    write_collection(tmp_path)
    with pytest.raises(RequestError, match="draft"):
        verify_collection(
            FakeClient(draft=True), tmp_path, "safal207/LS", source_run_id=1
        )
    with pytest.raises(RequestError, match="not open"):
        verify_collection(
            FakeClient(state="closed"), tmp_path, "safal207/LS", source_run_id=1
        )


def test_shell_env_is_quoted_and_contains_wrapper_owned_target(tmp_path):
    patch = b"patch"
    write_collection(tmp_path, patch=patch)
    request = verify_collection(
        FakeClient(patch=patch), tmp_path, "safal207/LS", source_run_id=9
    )
    env_path = tmp_path / "target.env"
    write_env(env_path, request, tmp_path)
    text = env_path.read_text()
    assert "TARGET_REPOSITORY=safal207/LS" in text
    assert "TARGET_PR_NUMBER=42" in text
    assert f"TARGET_HEAD_SHA={'a' * 40}" in text
    assert "PATCH_FILE=" in text
