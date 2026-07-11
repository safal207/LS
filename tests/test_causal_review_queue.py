import json
import subprocess
from pathlib import Path

import pytest

from tools.causal_review_queue import (
    QueueRequestError,
    select_request,
    validate_request,
    write_env,
)


def request_payload():
    return {
        "schema_version": "ls.causal-review-request.v0.1",
        "request_id": "pr-889-aba39f8",
        "repository": "safal207/LS",
        "pr_number": 889,
        "head_sha": "a" * 40,
        "head_branch": "ci/prove-protected-five-lane-ensemble",
        "reviewers": ["grok", "deepseek", "codex"],
        "authority": "advisory-only",
    }


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def init_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "base")
    return repo, git(repo, "rev-parse", "HEAD")


def add_request(repo: Path, name: str = "pr-889.json") -> str:
    queue = repo / "causal-review-requests/queue"
    queue.mkdir(parents=True, exist_ok=True)
    (queue / name).write_text(json.dumps(request_payload()), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", f"request {name}")
    return git(repo, "rev-parse", "HEAD")


def test_valid_request_is_normalized():
    request = validate_request(request_payload(), "safal207/LS")
    assert request["pr_number"] == 889
    assert set(request["reviewers"]) == {"grok", "deepseek", "codex"}
    assert request["authority"] == "advisory-only"


def test_request_rejects_wrong_repository_or_authority():
    payload = request_payload()
    payload["repository"] = "other/repo"
    with pytest.raises(QueueRequestError, match="repository mismatch"):
        validate_request(payload, "safal207/LS")

    payload = request_payload()
    payload["authority"] = "merge"
    with pytest.raises(QueueRequestError, match="advisory-only"):
        validate_request(payload, "safal207/LS")


def test_request_requires_all_three_unique_native_reviewers():
    payload = request_payload()
    payload["reviewers"] = ["grok", "codex"]
    with pytest.raises(QueueRequestError, match="grok, deepseek, and codex"):
        validate_request(payload, "safal207/LS")

    payload = request_payload()
    payload["reviewers"] = ["grok", "grok", "codex"]
    with pytest.raises(QueueRequestError, match="unique"):
        validate_request(payload, "safal207/LS")


def test_select_request_binds_exact_merge_commit(tmp_path):
    repo, before = init_repo(tmp_path)
    after = add_request(repo)
    request = select_request(repo, before, after, "safal207/LS")

    assert request["request_file"] == "causal-review-requests/queue/pr-889.json"
    assert request["source_commit"] == after
    assert request["head_sha"] == "a" * 40


def test_select_request_rejects_ambiguous_push(tmp_path):
    repo, before = init_repo(tmp_path)
    queue = repo / "causal-review-requests/queue"
    queue.mkdir(parents=True)
    for name in ("one.json", "two.json"):
        (queue / name).write_text(json.dumps(request_payload()), encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "two requests")
    after = git(repo, "rev-parse", "HEAD")

    with pytest.raises(QueueRequestError, match="exactly one queue request"):
        select_request(repo, before, after, "safal207/LS")


def test_queue_environment_is_shell_quoted(tmp_path):
    request = request_payload()
    request["request_file"] = "causal-review-requests/queue/pr-889.json"
    env_file = tmp_path / "queue.env"
    write_env(env_file, request)
    text = env_file.read_text(encoding="utf-8")
    assert "export REQUEST_ID=pr-889-aba39f8" in text
    assert "export PR_NUMBER=889" in text
    assert "export EXPECTED_HEAD_SHA=" + "a" * 40 in text
    assert "export EXPECTED_HEAD_BRANCH=ci/prove-protected-five-lane-ensemble" in text
