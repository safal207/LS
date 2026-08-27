from __future__ import annotations

from pathlib import Path
from typing import Any

from review_benchmark_v0_2_adjudication import (
    TRUE_DECISIONS,
    validate_adjudication,
)
from review_benchmark_v0_2_common import LANES, BenchmarkV02Error, sha256_json
from review_benchmark_v0_2_report import validate_report
from review_benchmark_v0_2_seal import validate_seal

ESCALATION = {"UNSUPPORTED_HYPOTHESIS", "DESIGN_QUESTION"}


def _category(cluster: dict[str, Any]) -> str:
    lanes = {member["lane"] for member in cluster["members"]}
    decision = cluster["decision"]
    if decision in TRUE_DECISIONS:
        if lanes == LANES:
            return "BOTH_TRUE"
        return "FRONTIER_MODEL_ONLY_TRUE" if lanes == {"FRONTIER_MODEL"} else "LS_ONLY_TRUE"
    return {
        "FALSE_POSITIVE": "FALSE_POSITIVE",
        "PLAUSIBLE_NOT_PROVEN": "EVIDENCE_GAP",
        "DUPLICATE": "DUPLICATE_FINDING",
        "REQUIRES_HUMAN_DECISION": "HUMAN_DECISION_REQUIRED",
        "OUT_OF_SCOPE": "OUT_OF_SCOPE",
    }[decision]


def _ratio(numerator: int, denominator: int | None) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def score(
    case: dict[str, Any],
    bindings: dict[str, dict[str, Any]],
    reports: dict[str, dict[str, Any]],
    seals: dict[str, dict[str, Any]],
    adjudication: dict[str, Any],
    repository_root: Path,
) -> dict[str, Any]:
    if set(bindings) != LANES or set(reports) != LANES or set(seals) != LANES:
        raise BenchmarkV02Error("bindings, reports, and seals must contain both v0.2 lanes")
    indexes = {}
    for lane in LANES:
        validate_report(reports[lane], case, bindings[lane], repository_root)
        validate_seal(seals[lane], reports[lane], bindings[lane])
        indexes[lane] = {item["finding_id"]: item for item in reports[lane]["findings"]}
    validate_adjudication(adjudication, case, reports)
    cluster_by_id = {cluster["cluster_id"]: cluster for cluster in adjudication["clusters"]}

    lane_stats = {}
    for lane in sorted(LANES):
        stats = {
            "executor": bindings[lane]["executor"],
            "provenance_level": bindings[lane]["provenance"]["level"],
            "total_findings": len(reports[lane]["findings"]),
            "true_findings": 0,
            "false_positives": 0,
            "plausible_not_proven": 0,
            "duplicate_findings": 0,
            "requires_human_decision": 0,
            "out_of_scope": 0,
            "attribution_correct": 0,
            "severity_correct": 0,
            "severity_compared": 0,
            "reproduced_true_findings": 0,
            "unique_true_findings": 0,
            "escalation_attempts": 0,
            "correct_escalations": 0,
            "known_truth_detected": 0,
            "known_truth_total": len(adjudication["known_truth"]) if adjudication["ground_truth_complete"] else None,
        }
        for cluster in adjudication["clusters"]:
            for member in [m for m in cluster["members"] if m["lane"] == lane]:
                finding = indexes[lane][member["finding_id"]]
                decision = cluster["decision"]
                if decision in TRUE_DECISIONS:
                    stats["true_findings"] += 1
                    stats["severity_compared"] += 1
                    stats["severity_correct"] += finding["severity"] == cluster["adjudicated_severity"]
                    stats["reproduced_true_findings"] += finding["reproduction"]["status"] in {"REPRODUCED", "STATICALLY_PROVEN"}
                    stats["unique_true_findings"] += {m["lane"] for m in cluster["members"]} == {lane}
                elif decision == "FALSE_POSITIVE":
                    stats["false_positives"] += 1
                elif decision == "PLAUSIBLE_NOT_PROVEN":
                    stats["plausible_not_proven"] += 1
                elif decision == "DUPLICATE":
                    stats["duplicate_findings"] += 1
                elif decision == "REQUIRES_HUMAN_DECISION":
                    stats["requires_human_decision"] += 1
                elif decision == "OUT_OF_SCOPE":
                    stats["out_of_scope"] += 1
                stats["attribution_correct"] += member["attribution_correct"]
                if finding["classification"] in ESCALATION:
                    stats["escalation_attempts"] += 1
                    stats["correct_escalations"] += decision in {"PLAUSIBLE_NOT_PROVEN", "REQUIRES_HUMAN_DECISION"}

        if adjudication["ground_truth_complete"]:
            for truth in adjudication["known_truth"]:
                detected = any(
                    any(member["lane"] == lane for member in cluster_by_id[cid]["members"])
                    for cid in truth["matched_cluster_ids"]
                )
                stats["known_truth_detected"] += detected

        stats["precision"] = _ratio(stats["true_findings"], stats["true_findings"] + stats["false_positives"])
        stats["recall"] = _ratio(stats["known_truth_detected"], stats["known_truth_total"])
        stats["reproduction_rate"] = _ratio(stats["reproduced_true_findings"], stats["true_findings"])
        stats["escalation_quality"] = _ratio(stats["correct_escalations"], stats["escalation_attempts"])
        stats["attribution_accuracy"] = _ratio(stats["attribution_correct"], stats["total_findings"])
        stats["severity_accuracy"] = _ratio(stats["severity_correct"], stats["severity_compared"])
        lane_stats[lane] = stats

    true_clusters = [cluster for cluster in adjudication["clusters"] if cluster["decision"] in TRUE_DECISIONS]
    body = {
        "schema_version": "ls.review_benchmark_scorecard.v0.2",
        "case_id": case["case_id"],
        "evidence_sha256": case["evidence_sha256"],
        "prompt_sha256": case["prompt_sha256"],
        "ground_truth_complete": adjudication["ground_truth_complete"],
        "sealed_reports": {lane: seals[lane]["seal_sha256"] for lane in sorted(LANES)},
        "lanes": lane_stats,
        "cluster_analysis": [
            {
                "cluster_id": cluster["cluster_id"],
                "category": _category(cluster),
                "decision": cluster["decision"],
                "lanes": sorted({m["lane"] for m in cluster["members"]}),
            }
            for cluster in adjudication["clusters"]
        ],
        "edge_proposal_summary": {
            lane: {
                "proposed": len(reports[lane]["proposed_edges"]),
                "approved_proposals": sum(item["lane"] == lane and item["decision"] == "APPROVE_PROPOSAL" for item in adjudication["edge_decisions"]),
                "rejected_proposals": sum(item["lane"] == lane and item["decision"] == "REJECT_PROPOSAL" for item in adjudication["edge_decisions"]),
                "deferred_proposals": sum(item["lane"] == lane and item["decision"] == "DEFER" for item in adjudication["edge_decisions"]),
                "trusted_graph_mutations": 0,
            }
            for lane in sorted(LANES)
        },
        "true_cluster_count": len(true_clusters),
        "overlap_true_cluster_count": sum({m["lane"] for m in cluster["members"]} == LANES for cluster in true_clusters),
        "human_required_cluster_count": sum(cluster["decision"] == "REQUIRES_HUMAN_DECISION" for cluster in adjudication["clusters"]),
    }
    return {**body, "scorecard_sha256": sha256_json(body)}
