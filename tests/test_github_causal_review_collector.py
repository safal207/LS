import hashlib
import json

import pytest

from tools.github_causal_review_collector import (
    CollectionResult,
    CollectorError,
    collect_exact_review_bundles,
    normalize_review_threads,
    write_collection,
)


class FakeClient:
    def __init__(self, *, before_sha="a" * 40, after_sha=None, patch=b"patch-bytes", nodes=None):
        self.before_sha = before_sha
        self.after_sha = after_sha or before_sha
        self.patch = patch
        self.nodes = nodes or []
        self.pr_reads = 0

    def get_pull_request(self, repository, pr_number):
        self.pr_reads += 1
        sha = self.before_sha if self.pr_reads == 1 else self.after_sha
        return {"state": "open", "draft": False, "head": {"sha": sha}}

    def get_patch(self, repository, pr_number):
        return self.patch

    def get_review_threads(self, repository, pr_number):
        return self.nodes, {"pages": [{"data": "raw"}]}


def thread(
    thread_id,
    login,
    *,
    resolved=False,
    outdated=False,
    comments_has_next=False,
    body="Provider finding body",
):
    return {
        "id": thread_id,
        "isResolved": resolved,
        "isOutdated": outdated,
        "path": "tools/example.py",
        "line": 12,
        "comments": {
            "pageInfo": {"hasNextPage": comments_has_next},
            "nodes": [
                {
                    "id": f"comment-{thread_id}",
                    "url": f"https://github.example/{thread_id}",
                    "body": body,
                    "author": {"login": login},
                }
            ],
        },
    }


def test_collect_binds_patch_and_threads_to_one_exact_target():
    patch = b"exact patch\n"
    nodes = [
        thread("q1", "qodo-code-review"),
        thread("c1", "coderabbitai[bot]"),
        thread("human", "safal207"),
    ]
    result = collect_exact_review_bundles(FakeClient(patch=patch, nodes=nodes), "safal207/LS", 874)

    expected_digest = "sha256:" + hashlib.sha256(patch).hexdigest()
    assert result.manifest["target"] == {
        "repository": "safal207/LS",
        "pr_number": 874,
        "head_sha": "a" * 40,
        "patch_sha256": expected_digest,
    }
    assert result.manifest["raw_thread_count"] == 3
    assert result.manifest["provider_thread_counts"] == {"coderabbit": 1, "qodo": 1}
    assert result.bundles["qodo"]["execution"]["status"] == "COMPLETED"
    assert result.bundles["coderabbit"]["threads"][0]["id"] == "c1"


def test_unsupported_root_author_is_preserved_raw_but_not_adapted():
    grouped = normalize_review_threads([thread("human", "safal207")])
    assert grouped == {"coderabbit": [], "qodo": []}


def test_missing_provider_threads_are_diagnostic_not_no_findings():
    result = collect_exact_review_bundles(FakeClient(nodes=[]), "safal207/LS", 874)

    for provider in ("coderabbit", "qodo"):
        bundle = result.bundles[provider]
        assert bundle["execution"]["status"] == "DIAGNOSTIC"
        assert bundle["execution"]["provenance"] == "UNVERIFIED"
        assert bundle["threads"] == []
        assert "cannot distinguish" in bundle["execution"]["details"]


def test_head_change_during_collection_fails_closed():
    client = FakeClient(before_sha="a" * 40, after_sha="c" * 40)
    with pytest.raises(CollectorError, match="head changed during collection"):
        collect_exact_review_bundles(client, "safal207/LS", 874)


def test_empty_patch_fails_closed():
    with pytest.raises(CollectorError, match="non-empty bytes"):
        collect_exact_review_bundles(FakeClient(patch=b""), "safal207/LS", 874)


def test_thread_comment_pagination_fails_closed():
    nodes = [thread("q1", "qodo-code-review", comments_has_next=True)]
    with pytest.raises(CollectorError, match="evidence is incomplete"):
        normalize_review_threads(nodes)


def test_malformed_thread_boolean_is_rejected():
    raw = thread("q1", "qodo-code-review")
    raw["isResolved"] = "false"
    with pytest.raises(CollectorError, match="must be a boolean"):
        normalize_review_threads([raw])


def test_write_collection_persists_raw_evidence_and_bundles(tmp_path):
    patch = b"patch"
    result = CollectionResult(
        manifest={"schema_version": "test", "target": {}},
        patch=patch,
        raw_threads={"pages": [{"raw": True}]},
        bundles={
            "qodo": {"provider": "qodo"},
            "coderabbit": {"provider": "coderabbit"},
        },
    )

    write_collection(result, tmp_path)

    assert (tmp_path / "target.patch").read_bytes() == patch
    assert json.loads((tmp_path / "github-review-threads.raw.json").read_text())["pages"][0]["raw"] is True
    assert json.loads((tmp_path / "qodo-bundle.json").read_text())["provider"] == "qodo"
    assert json.loads((tmp_path / "coderabbit-bundle.json").read_text())["provider"] == "coderabbit"
