from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import ls_audit as core

ALLOWED_DISPOSITIONS = {"confirmed", "rejected", "scoped", "unresolved"}
GITHUB_API = "https://api.github.com"


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


def validate_network_boundary(ref: core.Ref, api_base: str | None) -> str:
    if ref.host != "github.com":
        raise core.InputError("LS Exact-Head Audit v0.1 supports github.com only")
    if api_base is not None and api_base.rstrip("/") != GITHUB_API:
        raise core.InputError("Custom API bases are disabled in v0.1 to protect the GitHub token boundary")
    return GITHUB_API


def validate_output_boundary(output: Path, overwrite: bool) -> None:
    if output.is_symlink():
        raise core.InputError("Output path must not be a symbolic link")
    if not overwrite or not output.exists():
        return
    marker = output / "manifest.json"
    try:
        manifest = json.loads(marker.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise core.InputError(
            "--overwrite is allowed only for an existing LS audit bundle"
        ) from exc
    if manifest.get("schema_version") != core.SCHEMA or manifest.get("authority") != "advisory-only":
        raise core.InputError("Refusing to overwrite a directory without a valid LS audit manifest")


def review_submission_state(reviews: list[dict[str, Any]] | None, expected_head: str) -> str:
    if reviews is None:
        return "INCOMPLETE"
    if not reviews:
        return "NOT_RUN"
    exact = [review for review in reviews if review.get("commit_id") == expected_head]
    if not exact:
        return "INCOMPLETE"

    latest_by_reviewer: dict[str, dict[str, Any]] = {}
    for review in exact:
        reviewer = str(review.get("reviewer") or f"anonymous:{review.get('id')}")
        key = (str(review.get("submitted_at") or ""), int(review.get("id") or 0))
        current = latest_by_reviewer.get(reviewer)
        current_key = (str(current.get("submitted_at") or ""), int(current.get("id") or 0)) if current else ("", -1)
        if current is None or key > current_key:
            latest_by_reviewer[reviewer] = review

    states = {str(review.get("state") or "").upper() for review in latest_by_reviewer.values()}
    if "CHANGES_REQUESTED" in states:
        return "FAIL"
    if "APPROVED" in states:
        return "PASS"
    return "INCOMPLETE"


def policy_verdict(lanes: dict[str, str], human: dict[str, Any] | None) -> str:
    if "FAIL" in lanes.values():
        return "HOLD"
    if lanes.get("exact_head") != "PASS" or lanes.get("final_exact_head") != "PASS":
        return "INCONCLUSIVE — EXACT-HEAD EVIDENCE INCOMPLETE"
    return core.verdict(lanes, human)


def read_json(path: Path, expected_type: type[Any]) -> Any | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise core.InputError(f"Cannot read frozen evidence {path.name}: {exc}") from exc
    if not isinstance(value, expected_type):
        raise core.InputError(f"Frozen evidence {path.name} has an invalid shape")
    return value


def record_final_head(
    client: core.Client,
    ref: core.Ref,
    expected_head: str,
    output: Path,
) -> tuple[str, str]:
    endpoint = f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}"
    payload: dict[str, Any] = {"expected_head": expected_head}
    try:
        pr = client.get(endpoint)
        if not isinstance(pr, dict):
            raise core.ApiError(endpoint, None, "Expected a JSON object for pull request")
        observed = str((pr.get("head") or {}).get("sha") or "").lower() or None
        state = "PASS" if observed == expected_head else "FAIL"
        payload.update({"observed_head": observed, "status": state})
    except core.ApiError as exc:
        state = "INCOMPLETE"
        payload.update({
            "observed_head": None,
            "status": state,
            "error": {"endpoint": exc.endpoint, "http_status": exc.status, "message": exc.message},
        })
    digest = core.write_json(output / "evidence" / "final-head.json", payload)
    return state, digest


def harden_collection_lanes(output: Path, lanes: dict[str, str], expected_head: str) -> None:
    evidence = output / "evidence"
    reviews = read_json(evidence / "reviews.json", list)
    review_state = review_submission_state(reviews, expected_head)
    if reviews is not None and len(reviews) >= 2000 and review_state != "FAIL":
        review_state = "INCOMPLETE"
    lanes.pop("exact_head_reviews", None)
    lanes["exact_head_review_submissions"] = review_state

    pr = read_json(evidence / "pr.json", dict)
    files = read_json(evidence / "files.json", list)
    if pr is not None and files is not None:
        declared = pr.get("changed_files")
        if isinstance(declared, int) and declared != len(files):
            lanes["changed_files"] = "INCOMPLETE"

    checks = read_json(evidence / "check-runs.json", dict)
    if checks is not None:
        runs = checks.get("check_runs")
        total = checks.get("total_count")
        if isinstance(runs, list) and isinstance(total, int) and total > len(runs):
            lanes["check_runs"] = "INCOMPLETE"

    statuses = read_json(evidence / "commit-status.json", dict)
    if statuses is not None:
        items = statuses.get("statuses")
        total = statuses.get("total_count")
        if isinstance(items, list) and isinstance(total, int) and total > len(items):
            lanes["commit_status"] = "INCOMPLETE"


def harden_scorecard(output: Path, final_head_state: str, final_head_digest: str) -> core.Result:
    scorecard_path = output / "scorecard.json"
    manifest_path = output / "manifest.json"
    card = read_json(scorecard_path, dict)
    manifest = read_json(manifest_path, dict)
    if card is None or manifest is None:
        raise core.InputError("Generated Scorecard or manifest is missing")

    expected = card["target"]["expected_head"]
    lanes = dict(card["lanes"])
    harden_collection_lanes(output, lanes, expected)
    lanes["final_exact_head"] = final_head_state
    card["lanes"] = lanes

    digests = dict(card.get("evidence_digests") or {})
    digests["evidence/final-head.json"] = final_head_digest
    card["evidence_digests"] = digests
    bundle_digest = hashlib.sha256(core.canonical(sorted(digests.items()))).hexdigest()
    card["bundle_digest"] = f"sha256:{bundle_digest}"
    card["verdict"] = policy_verdict(lanes, card.get("adjudication"))

    review_state = lanes["exact_head_review_submissions"]
    if final_head_state == "FAIL":
        card["interpretation"] = (
            "The PR head changed during evidence collection. The bundle is stale and the verdict is HOLD."
        )
    elif final_head_state == "INCOMPLETE":
        card["interpretation"] = (
            "The final exact-head recheck did not complete. The collected evidence cannot support PASS."
        )
    elif card["verdict"].startswith("PASS"):
        card["interpretation"] = (
            "Human adjudication supports PASS. Any incomplete lanes were explicitly accepted with reasons."
        )
    elif review_state == "FAIL":
        card["interpretation"] = (
            "An exact-head review requested changes. The evidence requires HOLD regardless of green automation."
        )
    elif review_state == "INCOMPLETE":
        card["interpretation"] = (
            "Exact-head review evidence is commentary-only, stale, unavailable, or otherwise incomplete. "
            "It cannot be treated as approval."
        )

    core.write_json(scorecard_path, card)
    markdown_path = output / "SCORECARD.md"
    markdown_path.write_text(core.markdown(card))

    manifest["evidence_digests"] = digests
    manifest["bundle_digest"] = card["bundle_digest"]
    manifest["scorecard_digests"] = {
        "scorecard.json": hashlib.sha256(scorecard_path.read_bytes()).hexdigest(),
        "SCORECARD.md": hashlib.sha256(markdown_path.read_bytes()).hexdigest(),
    }
    core.write_json(manifest_path, manifest)

    effective_exact = "FAIL" if "FAIL" in {lanes["exact_head"], final_head_state} else lanes["exact_head"]
    return core.Result(output, card["verdict"], effective_exact, 3 if effective_exact == "FAIL" else 0)


def main(argv: list[str] | None = None) -> int:
    parser = core.parser()
    args = parser.parse_args(argv)
    try:
        ref = core.parse_url(args.pr_url)
        expected = core.validate_sha(args.expected_head)
        base = validate_network_boundary(ref, args.api_base)
        validate_finding_dispositions(args.adjudication)
        output = args.output or Path(
            f"ls-audit-{ref.owner}-{ref.repo}-pr-{ref.number}-{expected[:12]}"
        )
        validate_output_boundary(output, args.overwrite)
        client = core.Client(base, os.environ.get(args.token_env), args.timeout)
        core.run(
            args.pr_url,
            expected,
            output,
            client,
            args.overwrite,
            args.adjudication,
        )
        final_state, final_digest = record_final_head(client, ref, expected, output)
        result = harden_scorecard(output, final_state, final_digest)
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
