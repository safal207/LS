#!/usr/bin/env python3
"""Revalidate an unprivileged causal-review collection before secret-backed review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.github_causal_review_collector import GitHubApiClient

SCHEMA_VERSION = "ls.trusted-causal-review-request.v0.1"
EXPECTED_BUNDLES = {"coderabbit": "coderabbit-bundle.json", "qodo": "qodo-bundle.json"}


class RequestError(ValueError):
    """Raised when a collected request cannot cross the secret boundary."""


class RequestClient(Protocol):
    """Minimal GitHub API boundary used by the verifier."""

    def get_pull_request(self, repository: str, pr_number: int) -> Mapping[str, Any]: ...

    def get_patch(self, repository: str, pr_number: int) -> bytes: ...


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RequestError(f"{field} must be an object")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RequestError(f"{field} must be a non-empty string")
    return value.strip()


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise RequestError(f"{field} must be a positive integer")
    return value


def _sha(value: Any, field: str) -> str:
    value = _string(value, field)
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise RequestError(f"{field} must be a 40-character lowercase Git SHA")
    return value


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _read_json(path: Path, field: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RequestError(f"{field} must contain valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise RequestError(f"{field} must contain one JSON object")
    return payload


def _target(payload: Mapping[str, Any], field: str = "target") -> dict[str, Any]:
    target = _object(payload, field)
    repository = _string(target.get("repository"), f"{field}.repository")
    if repository.count("/") != 1:
        raise RequestError(f"{field}.repository must use owner/name form")
    pr_number = _integer(target.get("pr_number"), f"{field}.pr_number")
    head_sha = _sha(target.get("head_sha"), f"{field}.head_sha")
    patch_sha256 = _string(target.get("patch_sha256"), f"{field}.patch_sha256")
    if not patch_sha256.startswith("sha256:") or len(patch_sha256) != 71:
        raise RequestError(f"{field}.patch_sha256 must be sha256:<64 lowercase hex>")
    suffix = patch_sha256.removeprefix("sha256:")
    if any(char not in "0123456789abcdef" for char in suffix):
        raise RequestError(f"{field}.patch_sha256 must use lowercase hex")
    return {
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "patch_sha256": patch_sha256,
    }


def _current_head(pr: Mapping[str, Any]) -> tuple[str, str, bool]:
    state = _string(pr.get("state"), "pull_request.state")
    draft = pr.get("draft")
    if not isinstance(draft, bool):
        raise RequestError("pull_request.draft must be a boolean")
    head = _object(pr.get("head"), "pull_request.head")
    return _sha(head.get("sha"), "pull_request.head.sha"), state, draft


def verify_collection(
    client: RequestClient,
    input_dir: Path,
    expected_repository: str,
    *,
    source_run_id: int,
) -> dict[str, Any]:
    """Verify exact bytes, target identity, and current GitHub state."""
    manifest = _read_json(input_dir / "collection-manifest.json", "collection manifest")
    if manifest.get("schema_version") != "ls.github-causal-review-collection.v0.1":
        raise RequestError("unsupported collection manifest schema_version")
    target = _target(manifest.get("target"), "manifest.target")
    if target["repository"] != expected_repository:
        raise RequestError(
            f"repository mismatch: {target['repository']} != {expected_repository}"
        )

    patch_path = input_dir / "target.patch"
    try:
        patch = patch_path.read_bytes()
    except OSError as exc:
        raise RequestError("target.patch is unavailable") from exc
    if not patch:
        raise RequestError("target.patch must not be empty")
    if _digest(patch) != target["patch_sha256"]:
        raise RequestError("persisted patch bytes do not match manifest patch_sha256")
    if manifest.get("patch_bytes") != len(patch):
        raise RequestError("manifest patch_bytes does not match persisted patch length")

    for provider, filename in EXPECTED_BUNDLES.items():
        bundle = _read_json(input_dir / filename, f"{provider} bundle")
        if bundle.get("provider") != provider:
            raise RequestError(f"{provider} bundle provider identity mismatch")
        if _target(bundle.get("target"), f"{provider}.target") != target:
            raise RequestError(f"{provider} bundle target mismatch")

    pr = client.get_pull_request(target["repository"], target["pr_number"])
    current_sha, state, draft = _current_head(_object(pr, "pull_request"))
    if state != "open":
        raise RequestError(f"target PR is not open: {state}")
    if draft:
        raise RequestError("target PR is a draft")
    if current_sha != target["head_sha"]:
        raise RequestError(
            f"target head changed after collection: {target['head_sha']} -> {current_sha}"
        )

    current_patch = client.get_patch(target["repository"], target["pr_number"])
    if not isinstance(current_patch, bytes) or not current_patch:
        raise RequestError("GitHub returned an empty current patch")
    current_digest = _digest(current_patch)
    if current_digest != target["patch_sha256"]:
        raise RequestError(
            "current GitHub patch digest does not match the collected request: "
            f"{target['patch_sha256']} != {current_digest}"
        )
    if current_patch != patch:
        raise RequestError("current GitHub patch bytes differ despite matching target metadata")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "MATCHED",
        "source_run_id": source_run_id,
        "target": target,
        "patch_bytes": len(patch),
        "collection_manifest_sha256": _digest(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
    }


def write_env(path: Path, request: Mapping[str, Any], input_dir: Path) -> None:
    """Write shell-safe wrapper-owned target variables."""
    target = _target(request.get("target"), "request.target")
    values = {
        "TARGET_REPOSITORY": target["repository"],
        "TARGET_PR_NUMBER": str(target["pr_number"]),
        "TARGET_HEAD_SHA": target["head_sha"],
        "TARGET_PATCH_SHA256": target["patch_sha256"],
        "PATCH_FILE": str(input_dir / "target.patch"),
    }
    path.write_text(
        "".join(f"export {name}={shlex.quote(value)}\n" for name, value in values.items()),
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--api-url", default="https://api.github.com")
    parser.add_argument("--output", required=True)
    parser.add_argument("--env-file", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        token = os.environ.get(args.token_env, "")
        client = GitHubApiClient(token, args.api_url)
        request = verify_collection(
            client,
            Path(args.input_dir),
            args.repository,
            source_run_id=args.source_run_id,
        )
        Path(args.output).write_text(
            json.dumps(request, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_env(Path(args.env_file), request, Path(args.input_dir))
    except (RequestError, OSError) as exc:
        print(f"trusted causal-review request error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
