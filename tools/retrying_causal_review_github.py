#!/usr/bin/env python3
"""Run causal-review GitHub collection and verification with bounded API retries."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.causal_review_request import (
    RequestError,
    verify_collection,
    write_env,
)
from tools.github_causal_review_collector import (
    CollectorError,
    GitHubApiClient,
    collect_exact_review_bundles,
    write_collection,
)

RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


class RetryingGitHubApiClient(GitHubApiClient):
    """GitHub client that retries only transient HTTP and transport failures."""

    def __init__(
        self,
        token: str,
        api_url: str = "https://api.github.com",
        *,
        max_attempts: int = 4,
        base_delay_seconds: float = 1.0,
        max_delay_seconds: float = 15.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(token, api_url)
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int):
            raise CollectorError("max_attempts must be an integer")
        if max_attempts < 1 or max_attempts > 8:
            raise CollectorError("max_attempts must be between 1 and 8")
        if base_delay_seconds < 0 or max_delay_seconds < 0:
            raise CollectorError("retry delays must not be negative")
        self.max_attempts = max_attempts
        self.base_delay_seconds = float(base_delay_seconds)
        self.max_delay_seconds = float(max_delay_seconds)
        self.sleeper = sleeper

    def _delay(self, attempt: int, retry_after: str | None = None) -> float:
        delay = self.base_delay_seconds * (2 ** (attempt - 1))
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        return min(delay, self.max_delay_seconds)

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        accept: str = "application/vnd.github+json",
        payload: Mapping[str, Any] | None = None,
    ) -> bytes:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        last_error: BaseException | None = None

        for attempt in range(1, self.max_attempts + 1):
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
                last_error = exc
                retryable = exc.code in RETRYABLE_HTTP_STATUSES
                if retryable and attempt < self.max_attempts:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    self.sleeper(self._delay(attempt, retry_after))
                    continue
                raise CollectorError(
                    "GitHub API returned "
                    f"HTTP {exc.code} for {url} after {attempt} attempt(s): {body}"
                ) from exc
            except (urllib.error.URLError, OSError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    self.sleeper(self._delay(attempt))
                    continue
                raise CollectorError(
                    "GitHub API transport failure for "
                    f"{url} after {attempt} attempt(s): {type(exc).__name__}: {exc}"
                ) from exc

        raise CollectorError(
            f"GitHub API request for {url} exhausted retries: {last_error!r}"
        )


def trigger_neutral_error(exc: BaseException) -> str:
    """Remove obsolete event-specific wording from shared verifier diagnostics."""
    return str(exc).replace("workflow_run", "trigger context")


def _client(args: argparse.Namespace) -> RetryingGitHubApiClient:
    token = os.environ.get(args.token_env, "")
    return RetryingGitHubApiClient(
        token,
        args.api_url,
        max_attempts=args.max_attempts,
        base_delay_seconds=args.base_delay_seconds,
    )


def _collect(args: argparse.Namespace) -> None:
    result = collect_exact_review_bundles(
        _client(args), args.repository, args.pr_number
    )
    write_collection(result, Path(args.output_dir))


def _verify(args: argparse.Namespace) -> None:
    request = verify_collection(
        _client(args),
        Path(args.input_dir),
        args.repository,
        source_run_id=args.source_run_id,
        expected_pr_number=args.expected_pr_number,
        expected_head_sha=args.expected_head_sha,
        expected_head_branch=args.expected_head_branch,
        require_same_repository_head=not args.allow_fork,
    )
    Path(args.output).write_text(
        json.dumps(request, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_env(Path(args.env_file), request, Path(args.input_dir))


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository", required=True)
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--api-url", default="https://api.github.com")
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--base-delay-seconds", type=float, default=1.0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    collect = commands.add_parser("collect")
    _common(collect)
    collect.add_argument("--pr-number", type=int, required=True)
    collect.add_argument("--output-dir", required=True)

    verify = commands.add_parser("verify")
    _common(verify)
    verify.add_argument("--input-dir", required=True)
    verify.add_argument("--source-run-id", type=int, required=True)
    verify.add_argument("--expected-pr-number", type=int)
    verify.add_argument("--expected-head-sha")
    verify.add_argument("--expected-head-branch")
    verify.add_argument("--allow-fork", action="store_true")
    verify.add_argument("--output", required=True)
    verify.add_argument("--env-file", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "collect":
            _collect(args)
        else:
            _verify(args)
    except (CollectorError, RequestError, OSError, json.JSONDecodeError) as exc:
        print(
            f"trusted causal GitHub boundary error: {trigger_neutral_error(exc)}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
