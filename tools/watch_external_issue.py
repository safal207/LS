#!/usr/bin/env python3
"""Watch a public GitHub issue and mirror new human responses into an LS tracker.

The watcher stores its durable cursor in a hidden marker in the tracker issue body.
It ignores comments from configured users and bots, sanitizes excerpts, and can
fail soft when an external API is temporarily unavailable.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Iterable

API_ROOT = "https://api.github.com"
CURSOR_PATTERN = re.compile(r"<!--\s*external-watch:last-comment-id=(\d+)\s*-->")


class WatchError(RuntimeError):
    """Raised for invalid watcher state or GitHub API failures."""


@dataclass(frozen=True)
class WatchResult:
    previous_cursor: int
    next_cursor: int
    meaningful_comments: tuple[dict[str, Any], ...]

    @property
    def changed(self) -> bool:
        return self.next_cursor > self.previous_cursor


def cursor_value(body: str) -> int:
    matches = CURSOR_PATTERN.findall(body)
    if len(matches) != 1:
        raise WatchError("tracker issue must contain exactly one external-watch cursor marker")
    return int(matches[0])


def parse_cursor(body: str) -> int:
    return cursor_value(body)


def replace_cursor(body: str, cursor: int) -> str:
    if cursor < 0:
        raise WatchError("cursor must be non-negative")
    cursor_value(body)
    replacement = f"<!-- external-watch:last-comment-id={cursor} -->"
    updated, count = CURSOR_PATTERN.subn(replacement, body)
    if count != 1:
        raise WatchError("tracker issue must contain exactly one external-watch cursor marker")
    return updated


def sanitize_excerpt(value: Any, limit: int = 600) -> str:
    if not isinstance(value, str):
        return ""
    normalized = " ".join(value.split())
    normalized = normalized.replace("@", "@\u200b")
    escaped = html.escape(normalized, quote=False)
    if len(escaped) <= limit:
        return escaped
    return escaped[: max(0, limit - 1)].rstrip() + "…"


def is_bot(comment: dict[str, Any]) -> bool:
    user = comment.get("user")
    if not isinstance(user, dict):
        return True
    login = user.get("login")
    user_type = user.get("type")
    if not isinstance(login, str) or not login:
        return True
    return user_type == "Bot" or login.casefold().endswith("[bot]")


def is_meaningful(comment: dict[str, Any], ignored_logins: set[str]) -> bool:
    user = comment.get("user")
    if not isinstance(user, dict):
        return False
    login = user.get("login")
    if not isinstance(login, str) or not login:
        return False
    if login.casefold() in ignored_logins or is_bot(comment):
        return False
    body = comment.get("body")
    return isinstance(body, str) and bool(body.strip())


def select_new_comments(
    comments: Iterable[dict[str, Any]],
    previous_cursor: int,
    ignored_logins: set[str],
) -> WatchResult:
    ordered: list[dict[str, Any]] = []
    for comment in comments:
        comment_id = comment.get("id")
        if isinstance(comment_id, bool) or not isinstance(comment_id, int):
            continue
        if comment_id > previous_cursor:
            ordered.append(comment)
    ordered.sort(key=lambda item: item["id"])

    next_cursor = previous_cursor
    if ordered:
        next_cursor = ordered[-1]["id"]

    meaningful = tuple(
        comment for comment in ordered if is_meaningful(comment, ignored_logins)
    )
    return WatchResult(previous_cursor, next_cursor, meaningful)


def build_tracker_comment(
    source_repo: str,
    source_issue: int,
    comments: Iterable[dict[str, Any]],
) -> str:
    lines = [
        "## New external response",
        "",
        f"Source: https://github.com/{source_repo}/issues/{source_issue}",
        "",
    ]
    for comment in comments:
        user = comment.get("user") if isinstance(comment.get("user"), dict) else {}
        login = sanitize_excerpt(user.get("login"), limit=80) or "unknown"
        url = comment.get("html_url")
        safe_url = url if isinstance(url, str) and url.startswith("https://github.com/") else ""
        created_at = sanitize_excerpt(comment.get("created_at"), limit=40)
        excerpt = sanitize_excerpt(comment.get("body")) or "(empty comment)"
        header = f"- **{login}**"
        if created_at:
            header += f" · {created_at}"
        if safe_url:
            header += f" · [open comment]({safe_url})"
        lines.extend([header, f"  > {excerpt}", ""])
    lines.append(
        "The watcher advanced its durable cursor after recording this batch."
    )
    return "\n".join(lines)


def api_request(
    method: str,
    path: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    if not token:
        raise WatchError("GH_TOKEN is required")
    url = path if path.startswith("https://") else API_ROOT + path
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "LS-external-issue-watch/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise WatchError(f"GitHub API {exc.code} for {url}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise WatchError(f"GitHub API unavailable for {url}: {exc.reason}") from exc
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise WatchError(f"GitHub API returned invalid JSON for {url}") from exc


def fetch_all_comments(source_repo: str, source_issue: int, token: str) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    page = 1
    encoded_repo = urllib.parse.quote(source_repo, safe="/")
    while True:
        path = (
            f"/repos/{encoded_repo}/issues/{source_issue}/comments"
            f"?per_page=100&page={page}&sort=created&direction=asc"
        )
        batch = api_request("GET", path, token)
        if not isinstance(batch, list):
            raise WatchError("GitHub comments response must be an array")
        comments.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < 100:
            return comments
        page += 1


def run_watch(args: argparse.Namespace) -> WatchResult:
    token = os.environ.get("GH_TOKEN", "")
    tracker = api_request(
        "GET",
        f"/repos/{args.tracker_repo}/issues/{args.tracker_issue}",
        token,
    )
    if not isinstance(tracker, dict) or not isinstance(tracker.get("body"), str):
        raise WatchError("tracker issue body is unavailable")

    previous_cursor = parse_cursor(tracker["body"])
    ignored = {login.casefold() for login in args.ignore_login}
    comments = fetch_all_comments(args.source_repo, args.source_issue, token)
    result = select_new_comments(comments, previous_cursor, ignored)

    if result.meaningful_comments:
        body = build_tracker_comment(
            args.source_repo,
            args.source_issue,
            result.meaningful_comments,
        )
        api_request(
            "POST",
            f"/repos/{args.tracker_repo}/issues/{args.tracker_issue}/comments",
            token,
            {"body": body},
        )

    if result.changed:
        updated_body = replace_cursor(tracker["body"], result.next_cursor)
        api_request(
            "PATCH",
            f"/repos/{args.tracker_repo}/issues/{args.tracker_issue}",
            token,
            {"body": updated_body},
        )

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-repo", required=True)
    parser.add_argument("--source-issue", required=True, type=int)
    parser.add_argument("--tracker-repo", required=True)
    parser.add_argument("--tracker-issue", required=True, type=int)
    parser.add_argument("--ignore-login", action="append", default=[])
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when GitHub is temporarily unavailable",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = run_watch(args)
    except WatchError as exc:
        prefix = "ERROR" if args.strict else "WARNING"
        print(f"{prefix}: {exc}", file=sys.stderr)
        return 1 if args.strict else 0

    print(
        json.dumps(
            {
                "previous_cursor": result.previous_cursor,
                "next_cursor": result.next_cursor,
                "new_meaningful_comments": len(result.meaningful_comments),
                "changed": result.changed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
