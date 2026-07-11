#!/usr/bin/env python3
"""Collect exact-target CodeRabbit and Qodo review bundles from GitHub."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

PROVIDER_AUTHORS = {
    "coderabbit": {"coderabbitai", "coderabbitai[bot]"},
    "qodo": {"qodo-code-review", "qodo-code-review[bot]"},
}
GRAPHQL_QUERY = """
query ReviewThreads($owner: String!, $name: String!, $number: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          comments(first: 100) {
            pageInfo { hasNextPage }
            nodes {
              id
              url
              body
              author { login }
            }
          }
        }
      }
    }
  }
}
""".strip()


class CollectorError(ValueError):
    """Raised when exact GitHub evidence cannot be collected safely."""


class CollectorClient(Protocol):
    """Minimal GitHub client boundary used by the deterministic collector."""

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]: ...

    def get_patch(self, repository: str, pr_number: int) -> bytes: ...

    def get_review_threads(
        self, repository: str, pr_number: int
    ) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]: ...


@dataclass(frozen=True)
class CollectionResult:
    """One exact collection manifest, patch, raw response, and provider bundles."""

    manifest: dict[str, Any]
    patch: bytes
    raw_threads: dict[str, Any]
    bundles: dict[str, dict[str, Any]]


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CollectorError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise CollectorError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise CollectorError(f"{field} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise CollectorError(f"{field} must not be empty")
    return result


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise CollectorError(f"{field} must be a boolean")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CollectorError(f"{field} must be an integer")
    return value


def _optional_line(value: Any, field: str) -> int | None:
    if value is None:
        return None
    line = _integer(value, field)
    if line < 1:
        raise CollectorError(f"{field} must be null or a positive integer")
    return line


def _split_repository(repository: str) -> tuple[str, str]:
    repository = _string(repository, "repository")
    parts = repository.split("/")
    if len(parts) != 2 or not all(parts):
        raise CollectorError("repository must use owner/name form")
    return parts[0], parts[1]


def _head_sha(payload: Mapping[str, Any]) -> str:
    head = _object(payload.get("head"), "pull_request.head")
    sha = _string(head.get("sha"), "pull_request.head.sha")
    if len(sha) != 40 or any(char not in "0123456789abcdef" for char in sha):
        raise CollectorError("pull request head SHA must be 40 lowercase hex characters")
    state = _string(payload.get("state"), "pull_request.state")
    if state != "open":
        raise CollectorError(f"pull request must be open, got {state}")
    if payload.get("draft") is not False:
        raise CollectorError("pull request must be explicitly non-draft")
    return sha


def _provider_for_login(login: str) -> str | None:
    for provider, authors in PROVIDER_AUTHORS.items():
        if login in authors:
            return provider
    return None


def normalize_review_threads(nodes: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Normalize GraphQL review threads into provider-specific raw bundles."""
    grouped: dict[str, list[dict[str, Any]]] = {provider: [] for provider in PROVIDER_AUTHORS}
    for index, raw_node in enumerate(nodes):
        node = _object(raw_node, f"review_threads[{index}]")
        thread_id = _string(node.get("id"), f"review_threads[{index}].id")
        path = _string(node.get("path"), f"review_threads[{index}].path")
        line = _optional_line(node.get("line"), f"review_threads[{index}].line")
        resolved = _boolean(
            node.get("isResolved"), f"review_threads[{index}].isResolved"
        )
        outdated = _boolean(
            node.get("isOutdated"), f"review_threads[{index}].isOutdated"
        )
        comments = _object(
            node.get("comments"), f"review_threads[{index}].comments"
        )
        page_info = _object(
            comments.get("pageInfo"),
            f"review_threads[{index}].comments.pageInfo",
        )
        if _boolean(
            page_info.get("hasNextPage"),
            f"review_threads[{index}].comments.pageInfo.hasNextPage",
        ):
            raise CollectorError(
                f"review thread {thread_id} has more than 100 comments; evidence is incomplete"
            )
        comment_nodes = _array(
            comments.get("nodes"), f"review_threads[{index}].comments.nodes"
        )
        if not comment_nodes:
            raise CollectorError(f"review thread {thread_id} has no root comment")
        root = _object(comment_nodes[0], f"review_threads[{index}].comments.nodes[0]")
        author = _object(
            root.get("author"), f"review_threads[{index}].comments.nodes[0].author"
        )
        login = _string(
            author.get("login"),
            f"review_threads[{index}].comments.nodes[0].author.login",
        )
        provider = _provider_for_login(login)
        if provider is None:
            continue
        grouped[provider].append(
            {
                "id": thread_id,
                "author": {"login": login},
                "path": path,
                "line": line,
                "is_resolved": resolved,
                "is_outdated": outdated,
                "source_url": _string(
                    root.get("url"),
                    f"review_threads[{index}].comments.nodes[0].url",
                ),
                "body": _string(
                    root.get("body"),
                    f"review_threads[{index}].comments.nodes[0].body",
                ),
            }
        )
    return grouped


def _bundle(
    provider: str,
    target: Mapping[str, Any],
    threads: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if threads:
        status = "COMPLETED"
        provenance = "MATCHED"
        details = (
            "GitHub collector verified the provider-authored review-thread source and exact "
            "target. This attests collected findings only; it does not claim full provider "
            "coverage or a no-findings result."
        )
    else:
        status = "DIAGNOSTIC"
        provenance = "UNVERIFIED"
        details = (
            "No provider-authored review thread was found for the exact target. The collector "
            "cannot distinguish no findings from a provider lane that did not execute."
        )
    return {
        "provider": provider,
        "target": dict(target),
        "execution": {
            "status": status,
            "provenance": provenance,
            "details": details,
        },
        "threads": list(threads),
        "dedupe_overrides": {},
    }


def collect_exact_review_bundles(
    client: CollectorClient,
    repository: str,
    pr_number: int,
) -> CollectionResult:
    """Freeze one PR head/patch and collect all supported provider threads."""
    _split_repository(repository)
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
        raise CollectorError("pr_number must be a positive integer")

    before = client.get_pull_request(repository, pr_number)
    before_sha = _head_sha(_object(before, "pull_request_before"))
    patch = client.get_patch(repository, pr_number)
    if not isinstance(patch, bytes) or not patch:
        raise CollectorError("GitHub patch response must contain non-empty bytes")
    nodes, raw_threads = client.get_review_threads(repository, pr_number)
    after = client.get_pull_request(repository, pr_number)
    after_sha = _head_sha(_object(after, "pull_request_after"))
    if before_sha != after_sha:
        raise CollectorError(
            f"pull request head changed during collection: {before_sha} -> {after_sha}"
        )

    patch_digest = "sha256:" + hashlib.sha256(patch).hexdigest()
    target = {
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": before_sha,
        "patch_sha256": patch_digest,
    }
    grouped = normalize_review_threads(nodes)
    bundles = {
        provider: _bundle(provider, target, grouped[provider])
        for provider in sorted(PROVIDER_AUTHORS)
    }
    manifest = {
        "schema_version": "ls.github-causal-review-collection.v0.1",
        "target": target,
        "patch_bytes": len(patch),
        "raw_thread_count": len(nodes),
        "provider_thread_counts": {
            provider: len(grouped[provider]) for provider in sorted(grouped)
        },
        "outputs": {
            "patch": "target.patch",
            "raw_threads": "github-review-threads.raw.json",
            "bundles": {
                provider: f"{provider}-bundle.json" for provider in sorted(bundles)
            },
        },
    }
    return CollectionResult(
        manifest=manifest,
        patch=patch,
        raw_threads=dict(raw_threads),
        bundles=bundles,
    )


class GitHubApiClient:
    """Small urllib-based GitHub REST/GraphQL client with explicit evidence pagination."""

    def __init__(self, token: str, api_url: str = "https://api.github.com") -> None:
        self.token = _string(token, "token")
        self.api_url = api_url.rstrip("/")

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        accept: str = "application/vnd.github+json",
        payload: Mapping[str, Any] | None = None,
    ) -> bytes:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": accept,
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "LS-causal-review-collector",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:1000]
            raise CollectorError(
                f"GitHub API returned HTTP {exc.code} for {url}: {body}"
            ) from exc

    def _json_request(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        raw = self._request(url, method=method, payload=payload)
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectorError(f"GitHub API returned invalid JSON for {url}") from exc
        return _object(value, f"GitHub response from {url}")

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]:
        owner, name = _split_repository(repository)
        return self._json_request(
            f"{self.api_url}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/pulls/{pr_number}"
        )

    def get_patch(self, repository: str, pr_number: int) -> bytes:
        owner, name = _split_repository(repository)
        return self._request(
            f"{self.api_url}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/pulls/{pr_number}",
            accept="application/vnd.github.patch",
        )

    def get_review_threads(
        self, repository: str, pr_number: int
    ) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
        owner, name = _split_repository(repository)
        cursor: str | None = None
        nodes: list[Mapping[str, Any]] = []
        pages: list[Mapping[str, Any]] = []
        while True:
            response = self._json_request(
                f"{self.api_url}/graphql",
                method="POST",
                payload={
                    "query": GRAPHQL_QUERY,
                    "variables": {
                        "owner": owner,
                        "name": name,
                        "number": pr_number,
                        "cursor": cursor,
                    },
                },
            )
            errors = response.get("errors")
            if errors:
                raise CollectorError(f"GitHub GraphQL errors: {errors}")
            data = _object(response.get("data"), "graphql.data")
            repository_payload = _object(data.get("repository"), "graphql.data.repository")
            pull_request = _object(
                repository_payload.get("pullRequest"),
                "graphql.data.repository.pullRequest",
            )
            threads = _object(
                pull_request.get("reviewThreads"),
                "graphql.data.repository.pullRequest.reviewThreads",
            )
            page_nodes = _array(threads.get("nodes"), "reviewThreads.nodes")
            nodes.extend(_object(node, "reviewThreads.node") for node in page_nodes)
            pages.append(response)
            page_info = _object(threads.get("pageInfo"), "reviewThreads.pageInfo")
            if not _boolean(page_info.get("hasNextPage"), "reviewThreads.pageInfo.hasNextPage"):
                break
            cursor = _string(page_info.get("endCursor"), "reviewThreads.pageInfo.endCursor")
        return nodes, {"pages": pages}


def write_collection(result: CollectionResult, output_dir: Path) -> None:
    """Persist the patch, raw GraphQL evidence, manifest, and provider bundles."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "target.patch").write_bytes(result.patch)
    (output_dir / "github-review-threads.raw.json").write_text(
        json.dumps(result.raw_threads, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "collection-manifest.json").write_text(
        json.dumps(result.manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for provider, bundle in result.bundles.items():
        (output_dir / f"{provider}-bundle.json").write_text(
            json.dumps(bundle, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--api-url", default="https://api.github.com")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        token = os.environ.get(args.token_env, "")
        client = GitHubApiClient(token, args.api_url)
        result = collect_exact_review_bundles(client, args.repository, args.pr_number)
        write_collection(result, Path(args.output_dir))
    except (CollectorError, OSError) as exc:
        print(f"github causal-review collector error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
