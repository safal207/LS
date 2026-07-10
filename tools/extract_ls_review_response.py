#!/usr/bin/env python3
"""Extract a repo-native LS review comment into the LS audit response schema.

The LS multi-model reviewer already leaves a structured PR comment. This helper
turns that repository-native evidence into the JSON contract consumed by
``tools/build_ls_audit_pack.py --ls-response-json``.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "ls.manual_real_model_audit_report.v0.1"
LS_COMMENT_MARKER = "<!-- ls-multi-model-review -->"
LS_COMMENT_TITLE = "## LS multi-model PR review"
VALID_VERDICTS = {"APPROVE", "REQUEST_CHANGES", "INCOMPLETE"}
REPOSITORY = "safal207/LS"

FIELD_RE = re.compile(r"^-\s+(?P<key>[A-Za-z][A-Za-z -]*):\s+(?P<value>.+?)\s*$")
BOLD_RE = re.compile(r"^\*\*(?P<value>.+?)\*\*$")
CODE_RE = re.compile(r"^`(?P<value>.+?)`$")


def load_comments(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        comments = payload
    elif isinstance(payload, dict) and isinstance(payload.get("comments"), list):
        comments = payload["comments"]
    else:
        raise ValueError("comments JSON must be a list or an object with a comments list")

    normalized: list[dict[str, Any]] = []
    for comment in comments:
        if isinstance(comment, dict) and isinstance(comment.get("body"), str):
            normalized.append(comment)
    return normalized


def latest_ls_review_comment(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    matches = [
        comment
        for comment in comments
        if LS_COMMENT_MARKER in comment.get("body", "")
        or LS_COMMENT_TITLE in comment.get("body", "")
    ]
    if not matches:
        return None
    return matches[-1]


def clean_value(value: str) -> str:
    value = value.strip()
    for regex in (BOLD_RE, CODE_RE):
        match = regex.match(value)
        if match:
            return match.group("value").strip()
    return value


def parse_top_level_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines():
        match = FIELD_RE.match(line.strip())
        if not match:
            continue
        key = match.group("key").strip().lower().replace(" ", "_").replace("-", "_")
        fields[key] = clean_value(match.group("value"))
    return fields


def section_lines(body: str, heading: str) -> list[str]:
    lines = body.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### "):
            if in_section:
                break
            in_section = stripped == heading
            continue
        if in_section:
            collected.append(line.rstrip())
    return collected


def bullet_items(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def has_not_run_lane(body: str) -> bool:
    return "NOT_RUN" in body


def normalize_verdict(fields: dict[str, str], incomplete_lanes: list[str], body: str) -> str:
    status = fields.get("status", "").upper()
    aggregate = fields.get("aggregate_verdict", "").upper()

    if status and status not in {"COMPLETE", "COMPLETED", "SUCCESS"}:
        return "INCOMPLETE"
    if incomplete_lanes or has_not_run_lane(body):
        return "INCOMPLETE"
    if aggregate in VALID_VERDICTS:
        return aggregate
    if aggregate in {"COMMENT", "PARTIAL"}:
        return "INCOMPLETE"
    return "INCOMPLETE"


def build_limitations(fields: dict[str, str], incomplete_lanes: list[str], body: str) -> list[str]:
    limitations: list[str] = []
    status = fields.get("status")
    aggregate = fields.get("aggregate_verdict")
    if status and status.upper() not in {"COMPLETE", "COMPLETED", "SUCCESS"}:
        limitations.append(f"LS review status was {status}.")
    if aggregate and aggregate.upper() not in VALID_VERDICTS:
        limitations.append(f"LS aggregate verdict was {aggregate}; normalized to INCOMPLETE.")
    for lane in incomplete_lanes:
        limitations.append(f"Incomplete lane: {lane}")
    if has_not_run_lane(body):
        limitations.append("At least one LS model execution lane was NOT_RUN.")
    return limitations


def build_response(
    comment: dict[str, Any],
    case_id: str,
    source_pr_number: int,
    target_pr_number: int | None = None,
    target_commit_sha: str | None = None,
) -> dict[str, Any]:
    body = comment["body"]
    fields = parse_top_level_fields(body)
    incomplete_lanes = bullet_items(section_lines(body, "### Incomplete lanes"))
    verdict = normalize_verdict(fields, incomplete_lanes, body)
    created_at = comment.get("created_at") or "unknown time"
    exact_head = fields.get("exact_head", "unknown head")
    if target_pr_number is None:
        target_pr_number = source_pr_number
    if target_commit_sha is None:
        target_commit_sha = exact_head

    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "subject": {
            "repository": REPOSITORY,
            "pr_number": target_pr_number,
            "commit_sha": target_commit_sha,
        },
        "source": {
            "type": "GITHUB_PR_COMMENT",
            # The current LS comment format describes the PR containing the
            # comment and its exact head. Do not relabel that evidence as a
            # different target merely because target CLI inputs requested it.
            "reviewed_pr_number": source_pr_number,
            "reviewed_commit_sha": exact_head,
            "source_pr_number": source_pr_number,
            "source_comment_id": comment.get("id"),
            "source_head_sha": exact_head,
        },
        "model_attestation": {
            "provider": "LS",
            "model": "LS multi-model PR review",
            "channel": "GITHUB_PR_COMMENT",
            "operator_note": (
                "Extracted from repo-native LS multi-model PR review comment on "
                f"PR #{source_pr_number} "
                f"created at {created_at}; exact head {exact_head}."
            ),
        },
        "verdict": verdict,
        "findings": [],
        "limitations": build_limitations(fields, incomplete_lanes, body),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comments-json", required=True, help="Path to GitHub issue comments JSON")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--target-pr-number", required=True, type=int)
    parser.add_argument("--target-commit-sha", required=True)
    parser.add_argument("--out", required=True, help="Output ls_response.json path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    comments = load_comments(Path(args.comments_json))
    comment = latest_ls_review_comment(comments)
    if comment is None:
        print("ERROR: no LS multi-model PR review comment found")
        return 1

    response = build_response(
        comment,
        args.case_id,
        args.pr_number,
        args.target_pr_number,
        args.target_commit_sha,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(response, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote repo-native LS response to {out_path}")
    print(f"verdict={response['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
