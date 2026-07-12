from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import ls_audit as core

ALLOWED_DISPOSITIONS = {"confirmed", "rejected", "scoped", "unresolved"}


def validate_finding_dispositions(path: Path | None) -> None:
    if path is None:
        return
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return  # core emits the canonical input error
    findings = data.get("findings")
    if not isinstance(findings, list):
        return  # core emits the canonical input error
    for finding in findings:
        if not isinstance(finding, dict) or finding.get("disposition") not in ALLOWED_DISPOSITIONS:
            raise core.InputError(
                "Each finding requires disposition: confirmed, rejected, scoped, or unresolved"
            )


def review_submission_state(reviews: list[dict[str, Any]] | None, expected_head: str) -> str:
    if reviews is None:
        return "INCOMPLETE"
    if not reviews:
        return "NOT_RUN"
    exact = [review for review in reviews if review.get("commit_id") == expected_head]
    if not exact:
        return "INCOMPLETE"
    states = {str(review.get("state") or "").upper() for review in exact}
    if "CHANGES_REQUESTED" in states:
        return "FAIL"
    if "APPROVED" in states:
        return "PASS"
    return "INCOMPLETE"


def read_reviews(output: Path) -> list[dict[str, Any]] | None:
    path = output / "evidence" / "reviews.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise core.InputError(f"Cannot read frozen review evidence: {exc}") from exc
    if not isinstance(value, list):
        raise core.InputError("Frozen review evidence must be a list")
    return value


def harden_scorecard(output: Path) -> core.Result:
    scorecard_path = output / "scorecard.json"
    try:
        card = json.loads(scorecard_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise core.InputError(f"Cannot read generated Scorecard: {exc}") from exc

    expected = card["target"]["expected_head"]
    state = review_submission_state(read_reviews(output), expected)
    lanes = dict(card["lanes"])
    lanes.pop("exact_head_reviews", None)
    lanes["exact_head_review_submissions"] = state
    card["lanes"] = lanes
    card["verdict"] = core.verdict(lanes, card.get("adjudication"))

    if card["verdict"].startswith("PASS"):
        card["interpretation"] = (
            "Human adjudication supports PASS. Any incomplete lanes were explicitly accepted with reasons."
        )
    elif state == "FAIL":
        card["interpretation"] = (
            "An exact-head review requested changes. The evidence requires HOLD regardless of green automation."
        )
    elif state == "INCOMPLETE":
        card["interpretation"] = (
            "Exact-head review evidence is commentary-only, stale, unavailable, or otherwise incomplete. "
            "It cannot be treated as approval."
        )

    core.write_json(scorecard_path, card)
    (output / "SCORECARD.md").write_text(core.markdown(card))
    return core.Result(output, card["verdict"], lanes["exact_head"], 3 if lanes["exact_head"] == "FAIL" else 0)


def main(argv: list[str] | None = None) -> int:
    parser = core.parser()
    args = parser.parse_args(argv)
    try:
        ref = core.parse_url(args.pr_url)
        expected = core.validate_sha(args.expected_head)
        validate_finding_dispositions(args.adjudication)
        output = args.output or Path(
            f"ls-audit-{ref.owner}-{ref.repo}-pr-{ref.number}-{expected[:12]}"
        )
        core.run(
            args.pr_url,
            expected,
            output,
            core.Client(
                args.api_base or core.api_base(ref),
                os.environ.get(args.token_env),
                args.timeout,
            ),
            args.overwrite,
            args.adjudication,
        )
        result = harden_scorecard(output)
    except core.InputError as exc:
        parser.error(str(exc))
    except core.ApiError as exc:
        print(
            f"ls-audit: GitHub API failure at {exc.endpoint}: {exc.message}",
            file=sys.stderr,
        )
        return 4

    print(
        f"Bundle: {result.output}\n"
        f"Exact head: {result.exact_head}\n"
        f"Verdict: {result.verdict}"
    )
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
