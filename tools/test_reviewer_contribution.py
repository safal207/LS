from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCORECARD = Path(".ci_exchange/reviewer_contribution.latest.json")


def test_reviewer_contribution_shares_sum_to_one_hundred() -> None:
    scorecard = json.loads((ROOT / SCORECARD).read_text(encoding="utf-8"))

    total_share = sum(reviewer["contribution_share_percent"] for reviewer in scorecard["reviewers"])
    assert round(total_share, 1) == 100.0


def test_reviewer_ranking_follows_contribution_points() -> None:
    scorecard = json.loads((ROOT / SCORECARD).read_text(encoding="utf-8"))
    reviewers = {reviewer["reviewer_id"]: reviewer for reviewer in scorecard["reviewers"]}

    ranked_by_points = [
        reviewer_id
        for reviewer_id, _ in sorted(
            reviewers.items(),
            key=lambda item: item[1]["contribution_points"],
            reverse=True,
        )
    ]

    assert scorecard["ranking"] == ranked_by_points


def test_duplicate_finding_gets_reduced_uniqueness_credit() -> None:
    scorecard = json.loads((ROOT / SCORECARD).read_text(encoding="utf-8"))
    reviewers = {reviewer["reviewer_id"]: reviewer for reviewer in scorecard["reviewers"]}

    qodo_overlap = next(
        finding
        for finding in reviewers["qodo"]["findings"]
        if finding["finding_id"] == "qodo-misleading-per-check-status"
    )
    grok_overlap = next(
        finding
        for finding in reviewers["grok"]["findings"]
        if finding["finding_id"] == "grok-misleading-per-check-status"
    )

    assert qodo_overlap["uniqueness"] == 0.5
    assert grok_overlap["uniqueness"] == 0.5


def test_no_execution_produces_no_contribution_credit() -> None:
    scorecard = json.loads((ROOT / SCORECARD).read_text(encoding="utf-8"))
    reviewers = {reviewer["reviewer_id"]: reviewer for reviewer in scorecard["reviewers"]}

    assert reviewers["ls_multi_model"]["contribution_points"] == 0.0
    assert reviewers["ls_multi_model"]["confirmed_findings"] == 0
