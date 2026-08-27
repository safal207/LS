#!/usr/bin/env python3
"""Select and validate one causal-review request merged into protected main."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "ls.causal-review-request.v0.1"
ALLOWED_KEYS = {
    "schema_version",
    "request_id",
    "repository",
    "pr_number",
    "head_sha",
    "head_branch",
    "reviewers",
    "authority",
}
ALLOWED_REVIEWERS = {"grok", "deepseek", "codex"}
REQUEST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,95}$")


class QueueRequestError(ValueError):
    """Raised when a protected queue request is ambiguous or malformed."""


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QueueRequestError(f"{field} must be a non-empty string")
    return value.strip()


def _sha(value: Any, field: str) -> str:
    value = _string(value, field)
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise QueueRequestError(f"{field} must be a 40-character lowercase Git SHA")
    return value


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise QueueRequestError(f"{field} must be a positive integer")
    return value


def validate_request(payload: Mapping[str, Any], expected_repository: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise QueueRequestError("request must be one JSON object")
    keys = set(payload)
    extra = sorted(keys - ALLOWED_KEYS)
    missing = sorted(ALLOWED_KEYS - keys)
    if extra:
        raise QueueRequestError("request contains unknown properties: " + ", ".join(extra))
    if missing:
        raise QueueRequestError("request is missing required properties: " + ", ".join(missing))
    if payload["schema_version"] != SCHEMA_VERSION:
        raise QueueRequestError(f"schema_version must equal {SCHEMA_VERSION}")

    request_id = _string(payload["request_id"], "request_id")
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise QueueRequestError("request_id must use lowercase letters, digits, dot, dash, or underscore")
    repository = _string(payload["repository"], "repository")
    if repository != expected_repository:
        raise QueueRequestError(f"repository mismatch: {repository} != {expected_repository}")
    pr_number = _positive_int(payload["pr_number"], "pr_number")
    head_sha = _sha(payload["head_sha"], "head_sha")
    head_branch = _string(payload["head_branch"], "head_branch")
    authority = _string(payload["authority"], "authority")
    if authority != "advisory-only":
        raise QueueRequestError("authority must equal advisory-only")

    reviewers_raw = payload["reviewers"]
    if not isinstance(reviewers_raw, list) or not reviewers_raw:
        raise QueueRequestError("reviewers must be a non-empty array")
    reviewers = [_string(value, f"reviewers[{index}]").lower() for index, value in enumerate(reviewers_raw)]
    if len(reviewers) != len(set(reviewers)):
        raise QueueRequestError("reviewers must be unique")
    unknown = sorted(set(reviewers) - ALLOWED_REVIEWERS)
    if unknown:
        raise QueueRequestError("unsupported reviewers: " + ", ".join(unknown))
    if set(reviewers) != ALLOWED_REVIEWERS:
        raise QueueRequestError("v0.1 requests must include grok, deepseek, and codex exactly once")

    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "repository": repository,
        "pr_number": pr_number,
        "head_sha": head_sha,
        "head_branch": head_branch,
        "reviewers": reviewers,
        "authority": authority,
    }


def select_request(repo_root: Path, before_sha: str, after_sha: str, expected_repository: str) -> dict[str, Any]:
    before_sha = _sha(before_sha, "before_sha")
    after_sha = _sha(after_sha, "after_sha")
    result = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=AM",
            before_sha,
            after_sha,
            "--",
            "causal-review-requests/queue/*.json",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(paths) != 1:
        raise QueueRequestError(
            f"push must add or modify exactly one queue request, found {len(paths)}"
        )
    relative_path = Path(paths[0])
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise QueueRequestError("request path must stay inside the queue directory")
    full_path = (repo_root / relative_path).resolve()
    queue_root = (repo_root / "causal-review-requests/queue").resolve()
    if queue_root not in full_path.parents:
        raise QueueRequestError("request path escaped the queue directory")
    try:
        payload = json.loads(full_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise QueueRequestError(f"{relative_path} must contain valid UTF-8 JSON") from exc
    normalized = validate_request(payload, expected_repository)
    normalized["request_file"] = relative_path.as_posix()
    normalized["source_commit"] = after_sha
    return normalized


def write_env(path: Path, request: Mapping[str, Any]) -> None:
    values = {
        "REQUEST_ID": str(request["request_id"]),
        "PR_NUMBER": str(request["pr_number"]),
        "EXPECTED_HEAD_SHA": str(request["head_sha"]),
        "EXPECTED_HEAD_BRANCH": str(request["head_branch"]),
        "REQUEST_FILE": str(request["request_file"]),
    }
    path.write_text(
        "".join(f"export {name}={shlex.quote(value)}\n" for name, value in values.items()),
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--before-sha", required=True)
    parser.add_argument("--after-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--env-file", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request = select_request(
            Path(args.repo_root).resolve(),
            args.before_sha,
            args.after_sha,
            args.repository,
        )
        Path(args.output).write_text(
            json.dumps(request, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        write_env(Path(args.env_file), request)
    except (QueueRequestError, OSError, subprocess.CalledProcessError) as exc:
        print(f"causal-review queue error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
