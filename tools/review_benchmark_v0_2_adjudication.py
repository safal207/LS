from __future__ import annotations

import re
from typing import Any

from review_benchmark_v0_2_common import (
    BenchmarkV02Error,
    LANES,
    SEVERITIES,
    exact,
    sha256_json,
    strings,
    text,
)

CLUSTER = re.compile(r"^C[0-9]{3,}$")
TRUE_DECISIONS = {"TRUE_REPRODUCED", "TRUE_STATICALLY_PROVEN"}
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
    if adjudication["schema_version"] != "ls.review_benchmark_adjudication.v0.2":
        raise BenchmarkV02Error("unsupported adjudication schema_version")
    if (
        adjudication["case_id"] != case["case_id"]
        or adjudication["evidence_sha256"] != case["evidence_sha256"]
    ):
        raise BenchmarkV02Error("adjudication is not bound to frozen evidence")
    text(adjudication["adjudicator"], "adjudicator")
    if not isinstance(adjudication["ground_truth_complete"], bool):
        raise BenchmarkV02Error("ground_truth_complete must be boolean")

    expected = {
        (lane, finding["finding_id"])
        for lane, report in reports.items()
        for finding in report["findings"]
    }
    seen: set[tuple[str, str]] = set()
    cluster_ids = set()
    clusters = adjudication["clusters"]
    if not isinstance(clusters, list):
        raise BenchmarkV02Error("clusters must be an array")
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
            raise BenchmarkV02Error("cluster_id is invalid or duplicate")
        cluster_ids.add(cluster_id)
        text(cluster["canonical_claim"], "canonical_claim")
        text(cluster["rationale"], "rationale")
        if cluster["decision"] not in DECISIONS:
            raise BenchmarkV02Error("cluster decision is invalid")
        if cluster["adjudicated_severity"] not in SEVERITIES | {"none"}:
            raise BenchmarkV02Error("adjudicated severity is invalid")
        members = cluster["members"]
        if not isinstance(members, list) or not members:
            raise BenchmarkV02Error("cluster members must not be empty")
        for member in members:
            member = exact(
                member,
                {"lane", "finding_id", "attribution_correct"},
                "cluster member",
            )
            key = (member["lane"], member["finding_id"])
            if key not in expected or key in seen:
                raise BenchmarkV02Error(f"unknown or duplicate finding member: {key}")
            if not isinstance(member["attribution_correct"], bool):
                raise BenchmarkV02Error("attribution_correct must be boolean")
            seen.add(key)
    missing = expected - seen
    if missing:
        raise BenchmarkV02Error(
            f"every finding must be adjudicated exactly once; missing: {sorted(missing)}"
        )

    known_truth = adjudication["known_truth"]
    if not isinstance(known_truth, list):
        raise BenchmarkV02Error("known_truth must be an array")
    truth_ids = set()
    for truth in known_truth:
        truth = exact(
            truth,
            {"ground_truth_id", "title", "severity", "matched_cluster_ids"},
            "known_truth item",
        )
        truth_id = text(truth["ground_truth_id"], "ground_truth_id")
        if truth_id in truth_ids:
            raise BenchmarkV02Error(f"duplicate ground_truth_id: {truth_id}")
        truth_ids.add(truth_id)
        text(truth["title"], "known_truth.title")
        if truth["severity"] not in SEVERITIES:
            raise BenchmarkV02Error("known_truth severity is invalid")
        matched = strings(truth["matched_cluster_ids"], "matched_cluster_ids")
        if any(item not in cluster_ids for item in matched):
            raise BenchmarkV02Error("known_truth references unknown cluster")

    expected_edges = {
        (lane, edge["proposal_id"])
        for lane, report in reports.items()
        for edge in report["proposed_edges"]
    }
    seen_edges = set()
    edge_decisions = adjudication["edge_decisions"]
    if not isinstance(edge_decisions, list):
        raise BenchmarkV02Error("edge_decisions must be an array")
    for item in edge_decisions:
        item = exact(
            item,
            {"lane", "proposal_id", "decision", "rationale"},
            "edge decision",
        )
        key = (item["lane"], item["proposal_id"])
        if key not in expected_edges or key in seen_edges:
            raise BenchmarkV02Error(f"unknown or duplicate edge proposal: {key}")
        if item["decision"] not in EDGE_DECISIONS:
            raise BenchmarkV02Error("edge decision is invalid")
        text(item["rationale"], "edge decision rationale")
        seen_edges.add(key)
    missing_edges = expected_edges - seen_edges
    if missing_edges:
        raise BenchmarkV02Error(
            "every proposed edge must be adjudicated exactly once; "
            f"missing: {sorted(missing_edges)}"
        )
