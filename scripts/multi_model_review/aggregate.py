"""Independent-finding aggregation and policy decisions."""
from __future__ import annotations

import re
from typing import Any

from .contracts import ReviewRuntimeError, SEVERITY_ORDER

TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(value: str) -> set[str]:
    stop = {"the", "and", "for", "with", "that", "this", "from", "into", "when", "then", "can", "may"}
    return {token for token in TOKEN_RE.findall(value.lower()) if len(token) >= 3 and token not in stop}


def findings_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left["file"] != right["file"]:
        return False
    left_line, right_line = left.get("line"), right.get("line")
    if left_line is not None and right_line is not None and abs(left_line - right_line) > 5:
        return False
    left_tokens = _tokens(f"{left['title']} {left['failure_scenario']}")
    right_tokens = _tokens(f"{right['title']} {right['failure_scenario']}")
    if not left_tokens or not right_tokens:
        return False
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens) >= 0.25


def aggregate_reviews(reviews: list[dict[str, Any]], confirmation_threshold: int) -> dict[str, Any]:
    if confirmation_threshold < 2:
        raise ReviewRuntimeError("confirmation_threshold must be at least 2")
    findings: list[dict[str, Any]] = []
    for review in reviews:
        if review.get("status") != "VALID":
            continue
        for finding in review["result"]["findings"]:
            findings.append({**finding, "model_key": review["key"], "model_id": review["model_id"]})

    clusters: list[list[dict[str, Any]]] = []
    for finding in findings:
        target = next((cluster for cluster in clusters if any(findings_overlap(finding, other) for other in cluster)), None)
        (clusters.append([finding]) if target is None else target.append(finding))

    candidates: list[dict[str, Any]] = []
    confirmed: list[dict[str, Any]] = []
    for cluster in clusters:
        model_keys = sorted({item["model_key"] for item in cluster})
        representative = max(cluster, key=lambda item: (SEVERITY_ORDER[item["severity"]], len(item["evidence"])))
        high_support = {item["model_key"] for item in cluster if item["severity"] in {"critical", "high"}}
        record = {
            "severity": representative["severity"],
            "title": representative["title"],
            "file": representative["file"],
            "line": representative.get("line"),
            "evidence": representative["evidence"],
            "failure_scenario": representative["failure_scenario"],
            "recommendation": representative["recommendation"],
            "supporting_models": model_keys,
            "support_count": len(model_keys),
            "high_severity_support_count": len(high_support),
        }
        candidates.append(record)
        if len(model_keys) >= confirmation_threshold:
            confirmed.append(record)

    valid_verdicts = [review["result"]["verdict"] for review in reviews if review.get("status") == "VALID"]
    if any(item["high_severity_support_count"] >= confirmation_threshold for item in confirmed):
        verdict = "REQUEST_CHANGES"
    elif confirmed or any(item["severity"] in {"critical", "high"} for item in candidates):
        verdict = "COMMENT"
    elif valid_verdicts and all(value == "APPROVE" for value in valid_verdicts):
        verdict = "APPROVE"
    else:
        verdict = "COMMENT"

    conflict = (
        "APPROVE" in valid_verdicts and "REQUEST_CHANGES" in valid_verdicts
    ) or any(
        item["severity"] in {"critical", "high"} and item["support_count"] < confirmation_threshold
        for item in candidates
    )
    sorter = lambda item: (-SEVERITY_ORDER[item["severity"]], item["file"], item["line"] or 0)
    return {
        "verdict": verdict,
        "candidate_findings": sorted(candidates, key=sorter),
        "confirmed_findings": sorted(confirmed, key=sorter),
        "conflict": conflict,
        "valid_review_count": len(valid_verdicts),
    }


def policy_decision(*, mode: str, status: str, aggregate: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if status != "COMPLETE":
        reasons.append(f"review status is {status}")
    if aggregate.get("verdict") == "REQUEST_CHANGES":
        reasons.append("at least one critical/high finding is independently confirmed")
    would_block = bool(reasons)
    return {
        "mode": mode,
        "would_block": would_block,
        "enforced_block": mode == "strict" and would_block,
        "reasons": reasons,
    }
