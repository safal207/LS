from __future__ import annotations

import re
from typing import Any

from review_benchmark_contract import (
    BenchmarkError,
    LANES,
    SEVERITIES,
    TRUE_DECISIONS,
    exact,
    sha256_json,
    strings,
    text,
    validate_report,
    validate_seal,
)

CLUSTER = re.compile(r"^C[0-9]{3,}$")
DECISIONS = TRUE_DECISIONS | {
    "PLAUSIBLE_NOT_PROVEN",
    "FALSE_POSITIVE",
    "DUPLICATE",
    "OUT_OF_SCOPE",
    "REQUIRES_HUMAN_DECISION",
}
EDGE_DECISIONS = {"APPROVE_PROPOSAL", "REJECT_PROPOSAL", "DEFER"}
ESCALATION = {"UNSUPPORTED_HYPOTHESIS", "DESIGN_QUESTION"}


def validate_adjudication(
    adjudication: dict[str, Any],
    case: dict[str, Any],
    reports: dict[str, dict[str, Any]],
) -> None:
    exact(
        adjudication,
        {
            "schema_version",
            "case_id",
            "evidence_sha256",
            "adjudicator",
            "ground_truth_complete",
            "known_truth",
            "clusters",
            "edge_decisions",
        },
        "adjudication",
    )
    if adjudication["schema_version"] != "ls.review_benchmark_adjudication.v0.1":
        raise BenchmarkError("unsupported adjudication schema_version")
    if (
        adjudication["case_id"] != case["case_id"]
        or adjudication["evidence_sha256"] != case["evidence_sha256"]
    ):
        raise BenchmarkError("adjudication is not bound to frozen evidence")
    text(adjudication["adjudicator"], "adjudicator")
    if not isinstance(adjudication["ground_truth_complete"], bool):
        raise BenchmarkError("ground_truth_complete must be boolean")

    expected = {
        (lane, finding["finding_id"])
        for lane, report in reports.items()
        for finding in report["findings"]
    }
    seen: set[tuple[str, str]] = set()
    cluster_ids = set()
    clusters = adjudication["clusters"]
    if not isinstance(clusters, list):
        raise BenchmarkError("clusters must be an array")
    for index, cluster in enumerate(clusters):
        cluster = exact(
            cluster,
            {
                "cluster_id",
                "canonical_claim",
                "members",
                "decision",
                "adjudicated_severity",
                "rationale",
            },
            f"clusters[{index}]",
        )
        cluster_id = cluster["cluster_id"]
        if (
            not isinstance(cluster_id, str)
            or not CLUSTER.fullmatch(cluster_id)
            or cluster_id in cluster_ids
        ):
            raise BenchmarkError("cluster_id is invalid or duplicate")
        cluster_ids.add(cluster_id)
        text(cluster["canonical_claim"], "canonical_claim")
        text(cluster["rationale"], "rationale")
        if cluster["decision"] not in DECISIONS:
            raise BenchmarkError("cluster decision is invalid")
        if cluster["adjudicated_severity"] not in SEVERITIES | {"none"}:
            raise BenchmarkError("adjudicated severity is invalid")
        members = cluster["members"]
        if not isinstance(members, list) or not members:
            raise BenchmarkError("cluster members must not be empty")
        for member in members:
            member = exact(
                member,
                {"lane", "finding_id", "attribution_correct"},
                "cluster member",
            )
            key = (member["lane"], member["finding_id"])
            if key not in expected or key in seen:
                raise BenchmarkError(f"unknown or duplicate finding member: {key}")
            if not isinstance(member["attribution_correct"], bool):
                raise BenchmarkError("attribution_correct must be boolean")
            seen.add(key)
    missing = expected - seen
    if missing:
        raise BenchmarkError(
            f"every finding must be adjudicated exactly once; missing: {sorted(missing)}"
        )

    known_truth = adjudication["known_truth"]
    if not isinstance(known_truth, list):
        raise BenchmarkError("known_truth must be an array")
    truth_ids = set()
    for truth in known_truth:
        truth = exact(
            truth,
            {"ground_truth_id", "title", "severity", "matched_cluster_ids"},
            "known_truth item",
        )
        truth_id = text(truth["ground_truth_id"], "ground_truth_id")
        if truth_id in truth_ids:
            raise BenchmarkError(f"duplicate ground_truth_id: {truth_id}")
        truth_ids.add(truth_id)
        text(truth["title"], "known_truth.title")
        if truth["severity"] not in SEVERITIES:
            raise BenchmarkError("known_truth severity is invalid")
        matched = strings(truth["matched_cluster_ids"], "matched_cluster_ids")
        if any(item not in cluster_ids for item in matched):
            raise BenchmarkError("known_truth references unknown cluster")

    expected_edges = {
        (lane, edge["proposal_id"])
        for lane, report in reports.items()
        for edge in report["proposed_edges"]
    }
    seen_edges = set()
    edge_decisions = adjudication["edge_decisions"]
    if not isinstance(edge_decisions, list):
        raise BenchmarkError("edge_decisions must be an array")
    for item in edge_decisions:
        item = exact(
            item,
            {"lane", "proposal_id", "decision", "rationale"},
            "edge decision",
        )
        key = (item["lane"], item["proposal_id"])
        if key not in expected_edges or key in seen_edges:
            raise BenchmarkError(f"unknown or duplicate edge proposal: {key}")
        if item["decision"] not in EDGE_DECISIONS:
            raise BenchmarkError("edge decision is invalid")
        text(item["rationale"], "edge decision rationale")
        seen_edges.add(key)
    missing_edges = expected_edges - seen_edges
    if missing_edges:
        raise BenchmarkError(
            "every proposed edge must be adjudicated exactly once; "
            f"missing: {sorted(missing_edges)}"
        )


def _category(cluster: dict[str, Any]) -> str:
    lanes = {member["lane"] for member in cluster["members"]}
    decision = cluster["decision"]
    if decision in TRUE_DECISIONS:
        if lanes == LANES:
            return "BOTH_TRUE"
        return "CLAUDE_ONLY_TRUE" if lanes == {"CLAUDE"} else "LS_ONLY_TRUE"
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
    reports: dict[str, dict[str, Any]],
    seals: dict[str, dict[str, Any]],
    adjudication: dict[str, Any],
) -> dict[str, Any]:
    indexes = {}
    for lane in LANES:
        validate_report(reports[lane], case)
        validate_seal(seals[lane], reports[lane])
        indexes[lane] = {
            item["finding_id"]: item for item in reports[lane]["findings"]
        }
    validate_adjudication(adjudication, case, reports)
    cluster_by_id = {
        cluster["cluster_id"]: cluster for cluster in adjudication["clusters"]
    }

    lane_stats = {}
    for lane in sorted(LANES):
        stats = {
            "total_findings": len(reports[lane]["findings"]),
            "true_findings": 0,
            "false_positives": 0,
            "plausible_not_proven": 0,
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
            "known_truth_total": (
                len(adjudication["known_truth"])
                if adjudication["ground_truth_complete"]
                else None
            ),
        }
        for cluster in adjudication["clusters"]:
            for member in [m for m in cluster["members"] if m["lane"] == lane]:
                finding = indexes[lane][member["finding_id"]]
                decision = cluster["decision"]
                if decision in TRUE_DECISIONS:
                    stats["true_findings"] += 1
                    stats["severity_compared"] += 1
                    stats["severity_correct"] += (
                        finding["severity"] == cluster["adjudicated_severity"]
                    )
                    stats["reproduced_true_findings"] += (
                        finding["reproduction"]["status"]
                        in {"REPRODUCED", "STATICALLY_PROVEN"}
                    )
                    stats["unique_true_findings"] += (
                        {m["lane"] for m in cluster["members"]} == {lane}
                    )
                elif decision == "FALSE_POSITIVE":
                    stats["false_positives"] += 1
                elif decision == "PLAUSIBLE_NOT_PROVEN":
                    stats["plausible_not_proven"] += 1
                elif decision == "REQUIRES_HUMAN_DECISION":
                    stats["requires_human_decision"] += 1
                elif decision == "OUT_OF_SCOPE":
                    stats["out_of_scope"] += 1
                stats["attribution_correct"] += member["attribution_correct"]
                if finding["classification"] in ESCALATION:
                    stats["escalation_attempts"] += 1
                    stats["correct_escalations"] += decision in {
                        "PLAUSIBLE_NOT_PROVEN",
                        "REQUIRES_HUMAN_DECISION",
                    }

        if adjudication["ground_truth_complete"]:
            for truth in adjudication["known_truth"]:
                detected = any(
                    any(member["lane"] == lane for member in cluster_by_id[cid]["members"])
                    for cid in truth["matched_cluster_ids"]
                )
                stats["known_truth_detected"] += detected

        stats["precision"] = _ratio(
            stats["true_findings"],
            stats["true_findings"] + stats["false_positives"],
        )
        stats["recall"] = _ratio(
            stats["known_truth_detected"], stats["known_truth_total"]
        )
        stats["reproduction_rate"] = _ratio(
            stats["reproduced_true_findings"], stats["true_findings"]
        )
        stats["escalation_quality"] = _ratio(
            stats["correct_escalations"], stats["escalation_attempts"]
        )
        stats["attribution_accuracy"] = _ratio(
            stats["attribution_correct"], stats["total_findings"]
        )
        stats["severity_accuracy"] = _ratio(
            stats["severity_correct"], stats["severity_compared"]
        )
        lane_stats[lane] = stats

    true_clusters = [
        cluster
        for cluster in adjudication["clusters"]
        if cluster["decision"] in TRUE_DECISIONS
    ]
    body = {
        "schema_version": "ls.review_benchmark_scorecard.v0.1",
        "case_id": case["case_id"],
        "evidence_sha256": case["evidence_sha256"],
        "ground_truth_complete": adjudication["ground_truth_complete"],
        "sealed_reports": {
            lane: seals[lane]["seal_sha256"] for lane in sorted(LANES)
        },
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
                "approved_proposals": sum(
                    item["lane"] == lane
                    and item["decision"] == "APPROVE_PROPOSAL"
                    for item in adjudication["edge_decisions"]
                ),
                "rejected_proposals": sum(
                    item["lane"] == lane
                    and item["decision"] == "REJECT_PROPOSAL"
                    for item in adjudication["edge_decisions"]
                ),
                "deferred_proposals": sum(
                    item["lane"] == lane and item["decision"] == "DEFER"
                    for item in adjudication["edge_decisions"]
                ),
                "trusted_graph_mutations": 0,
            }
            for lane in sorted(LANES)
        },
        "true_cluster_count": len(true_clusters),
        "overlap_true_cluster_count": sum(
            {m["lane"] for m in cluster["members"]} == LANES
            for cluster in true_clusters
        ),
        "human_required_cluster_count": sum(
            cluster["decision"] == "REQUIRES_HUMAN_DECISION"
            for cluster in adjudication["clusters"]
        ),
    }
    return {**body, "scorecard_sha256": sha256_json(body)}
