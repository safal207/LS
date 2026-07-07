from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

DIGEST = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
IDENT = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,63}$")
LANES = {"CLAUDE", "LS"}
SEVERITIES = {"critical", "high", "medium", "low"}
TRUE_DECISIONS = {"TRUE_REPRODUCED", "TRUE_STATICALLY_PROVEN"}
CLASSIFICATIONS = {
    "CONFIRMED_DEFECT",
    "REPRODUCIBLE_HYPOTHESIS",
    "UNSUPPORTED_HYPOTHESIS",
    "DESIGN_QUESTION",
}
REPRODUCTION_STATUSES = {
    "REPRODUCED",
    "STATICALLY_PROVEN",
    "PROPOSED",
    "NOT_AVAILABLE",
}
RELATION_STATUSES = {"OBSERVED", "INFERRED", "MISSING", "CONTRADICTED"}
PROBE_STATUSES = {"PASSED", "FAILED", "INCONCLUSIVE", "NOT_RUN"}


class BenchmarkError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"cannot load JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkError(f"{path} must contain an object")
    return value


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def exact(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkError(f"{field} must be an object")
    actual = set(value)
    if actual != keys:
        raise BenchmarkError(
            f"{field} keys mismatch; missing={sorted(keys-actual)}, "
            f"extra={sorted(actual-keys)}"
        )
    return value


def text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BenchmarkError(f"{field} must be a non-empty string")
    return value


def strings(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise BenchmarkError(f"{field} must be an array")
    if any(not isinstance(item, str) or not item for item in value):
        raise BenchmarkError(f"{field} must contain non-empty strings")
    return value


def repo_path(value: Any, field: str) -> str:
    result = text(value, field)
    path = PurePosixPath(result)
    if path.is_absolute() or ".." in path.parts:
        raise BenchmarkError(f"{field} must remain inside the repository")
    return result


def digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise BenchmarkError(f"{field} must be a lowercase SHA-256")
    return value


def confidence(value: Any, field: str) -> float:
    valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    if not valid or not 0 <= value <= 1:
        raise BenchmarkError(f"{field} must be between 0 and 1")
    return float(value)


def validate_case(case: dict[str, Any]) -> None:
    exact(
        case,
        {
            "schema_version",
            "case_id",
            "status",
            "evidence_manifest_path",
            "evidence_sha256",
            "coordinates",
            "prompt_path",
            "lanes",
        },
        "case",
    )
    if case["schema_version"] != "ls.review_benchmark_case.v0.1":
        raise BenchmarkError("unsupported case schema_version")
    text(case["case_id"], "case_id")
    if case["status"] not in {"PREPARED", "FROZEN"}:
        raise BenchmarkError("case status must be PREPARED or FROZEN")
    repo_path(case["evidence_manifest_path"], "evidence_manifest_path")
    repo_path(case["prompt_path"], "prompt_path")
    if case["status"] == "PREPARED":
        if case["evidence_sha256"] is not None:
            raise BenchmarkError("PREPARED case must not claim evidence_sha256")
    else:
        digest(case["evidence_sha256"], "evidence_sha256")

    coordinates = exact(
        case["coordinates"],
        {"repository", "pr_number", "base_sha", "head_sha", "changed_file_count"},
        "coordinates",
    )
    text(coordinates["repository"], "coordinates.repository")
    if (
        not isinstance(coordinates["pr_number"], int)
        or isinstance(coordinates["pr_number"], bool)
        or coordinates["pr_number"] < 1
    ):
        raise BenchmarkError("coordinates.pr_number must be positive")
    for field in ("base_sha", "head_sha"):
        if not isinstance(coordinates[field], str) or not COMMIT.fullmatch(
            coordinates[field]
        ):
            raise BenchmarkError(f"coordinates.{field} must be a Git commit SHA")
    if (
        not isinstance(coordinates["changed_file_count"], int)
        or coordinates["changed_file_count"] < 1
    ):
        raise BenchmarkError("coordinates.changed_file_count must be positive")

    lanes = case["lanes"]
    if not isinstance(lanes, list) or len(lanes) != 2:
        raise BenchmarkError("lanes must contain CLAUDE and LS exactly once")
    seen = set()
    for index, item in enumerate(lanes):
        item = exact(
            item,
            {"lane", "visibility", "must_not_receive"},
            f"lanes[{index}]",
        )
        if item["lane"] not in LANES or item["lane"] in seen:
            raise BenchmarkError("lanes must contain CLAUDE and LS exactly once")
        seen.add(item["lane"])
        if item["visibility"] != "FROZEN_BUNDLE_ONLY":
            raise BenchmarkError("lane visibility must be FROZEN_BUNDLE_ONLY")
        strings(item["must_not_receive"], "must_not_receive", nonempty=True)


def _validate_finding(item: Any, index: int, finding_ids: set[str]) -> None:
    prefix = f"findings[{index}]"
    item = exact(
        item,
        {
            "finding_id",
            "title",
            "severity",
            "classification",
            "confidence",
            "claim",
            "evidence",
            "failure_scenario",
            "reproduction",
            "recommendation",
            "uncertainties",
        },
        prefix,
    )
    finding_id = item["finding_id"]
    if not isinstance(finding_id, str) or not IDENT.fullmatch(finding_id):
        raise BenchmarkError(f"{prefix}.finding_id is invalid")
    if finding_id in finding_ids:
        raise BenchmarkError(f"duplicate finding_id: {finding_id}")
    finding_ids.add(finding_id)
    text(item["title"], f"{prefix}.title")
    if item["severity"] not in SEVERITIES:
        raise BenchmarkError(f"{prefix}.severity is invalid")
    if item["classification"] not in CLASSIFICATIONS:
        raise BenchmarkError(f"{prefix}.classification is invalid")
    confidence(item["confidence"], f"{prefix}.confidence")
    for field in ("claim", "failure_scenario", "recommendation"):
        text(item[field], f"{prefix}.{field}")
    strings(item["uncertainties"], f"{prefix}.uncertainties")

    evidence = item["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise BenchmarkError(f"{prefix}.evidence must not be empty")
    for evidence_index, source in enumerate(evidence):
        source = exact(
            source,
            {"path", "line_start", "line_end", "observation"},
            f"{prefix}.evidence[{evidence_index}]",
        )
        repo_path(source["path"], "evidence.path")
        start, end = source["line_start"], source["line_end"]
        if (start is None) != (end is None):
            raise BenchmarkError("evidence line range must be both null or integers")
        if start is not None and (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < 1
            or end < start
        ):
            raise BenchmarkError("evidence line range is invalid")
        text(source["observation"], "evidence.observation")

    reproduction = exact(item["reproduction"], {"status", "steps"}, "reproduction")
    if reproduction["status"] not in REPRODUCTION_STATUSES:
        raise BenchmarkError("reproduction.status is invalid")
    strings(reproduction["steps"], "reproduction.steps")


def _validate_structured(value: Any, lane: str) -> None:
    value = exact(value, {"artifact_nodes", "relations", "probes"}, "structured_analysis")
    for field in ("artifact_nodes", "relations", "probes"):
        if not isinstance(value[field], list):
            raise BenchmarkError(f"structured_analysis.{field} must be an array")
        if lane == "LS" and not value[field]:
            raise BenchmarkError(f"LS report requires non-empty {field}")

    node_ids = set()
    for index, node in enumerate(value["artifact_nodes"]):
        node = exact(
            node,
            {"node_id", "kind", "path", "observation"},
            f"artifact_nodes[{index}]",
        )
        node_id = text(node["node_id"], "node_id")
        if node_id in node_ids:
            raise BenchmarkError(f"duplicate node_id: {node_id}")
        node_ids.add(node_id)
        text(node["kind"], "node.kind")
        repo_path(node["path"], "node.path")
        text(node["observation"], "node.observation")

    relation_ids = set()
    for index, relation in enumerate(value["relations"]):
        relation = exact(
            relation,
            {
                "relation_id",
                "source_node",
                "target_node",
                "relation_type",
                "status",
                "evidence_finding_ids",
            },
            f"relations[{index}]",
        )
        relation_id = text(relation["relation_id"], "relation_id")
        if relation_id in relation_ids:
            raise BenchmarkError(f"duplicate relation_id: {relation_id}")
        relation_ids.add(relation_id)
        if relation["source_node"] not in node_ids or relation["target_node"] not in node_ids:
            raise BenchmarkError("relation references unknown node")
        text(relation["relation_type"], "relation_type")
        if relation["status"] not in RELATION_STATUSES:
            raise BenchmarkError("relation status is invalid")
        strings(relation["evidence_finding_ids"], "relation evidence")

    probe_ids = set()
    for index, probe in enumerate(value["probes"]):
        probe = exact(
            probe,
            {
                "probe_id",
                "kind",
                "status",
                "command",
                "observation",
                "evidence_finding_ids",
            },
            f"probes[{index}]",
        )
        probe_id = text(probe["probe_id"], "probe_id")
        if probe_id in probe_ids:
            raise BenchmarkError(f"duplicate probe_id: {probe_id}")
        probe_ids.add(probe_id)
        text(probe["kind"], "probe.kind")
        if probe["status"] not in PROBE_STATUSES:
            raise BenchmarkError("probe.status is invalid")
        if probe["command"] is not None:
            text(probe["command"], "probe.command")
        text(probe["observation"], "probe.observation")
        strings(probe["evidence_finding_ids"], "probe evidence")


def validate_report(report: dict[str, Any], case: dict[str, Any]) -> None:
    validate_case(case)
    if case["status"] != "FROZEN":
        raise BenchmarkError("reports cannot be accepted until the case is FROZEN")
    exact(
        report,
        {
            "schema_version",
            "case_id",
            "lane",
            "evidence_sha256",
            "reviewer",
            "prompt_sha256",
            "verdict",
            "findings",
            "structured_analysis",
            "proposed_edges",
            "limitations",
        },
        "report",
    )
    if report["schema_version"] != "ls.review_benchmark_report.v0.1":
        raise BenchmarkError("unsupported report schema_version")
    if report["case_id"] != case["case_id"]:
        raise BenchmarkError("report case_id does not match case")
    if report["lane"] not in LANES:
        raise BenchmarkError("report lane must be CLAUDE or LS")
    if report["evidence_sha256"] != case["evidence_sha256"]:
        raise BenchmarkError("report is not bound to frozen evidence")
    digest(report["prompt_sha256"], "prompt_sha256")
    reviewer = exact(report["reviewer"], {"system", "model", "version"}, "reviewer")
    for field in reviewer:
        text(reviewer[field], f"reviewer.{field}")
    if report["verdict"] not in {"APPROVE", "COMMENT", "REQUEST_CHANGES", "INCOMPLETE"}:
        raise BenchmarkError("invalid report verdict")
    if not isinstance(report["findings"], list):
        raise BenchmarkError("findings must be an array")
    finding_ids: set[str] = set()
    for index, finding in enumerate(report["findings"]):
        _validate_finding(finding, index, finding_ids)
    _validate_structured(report["structured_analysis"], report["lane"])

    if not isinstance(report["proposed_edges"], list):
        raise BenchmarkError("proposed_edges must be an array")
    proposal_ids = set()
    for index, edge in enumerate(report["proposed_edges"]):
        edge = exact(
            edge,
            {
                "proposal_id",
                "source_node",
                "target_node",
                "relation_type",
                "provenance_finding_ids",
                "confidence",
                "status",
            },
            f"proposed_edges[{index}]",
        )
        proposal_id = text(edge["proposal_id"], "proposal_id")
        if proposal_id in proposal_ids:
            raise BenchmarkError(f"duplicate proposal_id: {proposal_id}")
        proposal_ids.add(proposal_id)
        for field in ("source_node", "target_node", "relation_type"):
            text(edge[field], f"edge.{field}")
        provenance = strings(edge["provenance_finding_ids"], "edge provenance", nonempty=True)
        if any(item not in finding_ids for item in provenance):
            raise BenchmarkError("edge references unknown finding provenance")
        confidence(edge["confidence"], "edge.confidence")
        if edge["status"] != "UNTRUSTED":
            raise BenchmarkError("edge proposal must remain UNTRUSTED")
    strings(report["limitations"], "limitations")


def seal_report(case: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    validate_report(report, case)
    body = {
        "schema_version": "ls.review_benchmark_seal.v0.1",
        "case_id": report["case_id"],
        "lane": report["lane"],
        "evidence_sha256": report["evidence_sha256"],
        "prompt_sha256": report["prompt_sha256"],
        "reviewer": report["reviewer"],
        "report_sha256": sha256_json(report),
        "finding_count": len(report["findings"]),
        "finding_ids": sorted(item["finding_id"] for item in report["findings"]),
        "proposed_edge_count": len(report["proposed_edges"]),
        "proposed_edge_ids": sorted(item["proposal_id"] for item in report["proposed_edges"]),
    }
    return {**body, "seal_sha256": sha256_json(body)}


def validate_seal(seal: dict[str, Any], report: dict[str, Any]) -> None:
    body = {
        "schema_version": "ls.review_benchmark_seal.v0.1",
        "case_id": report["case_id"],
        "lane": report["lane"],
        "evidence_sha256": report["evidence_sha256"],
        "prompt_sha256": report["prompt_sha256"],
        "reviewer": report["reviewer"],
        "report_sha256": sha256_json(report),
        "finding_count": len(report["findings"]),
        "finding_ids": sorted(item["finding_id"] for item in report["findings"]),
        "proposed_edge_count": len(report["proposed_edges"]),
        "proposed_edge_ids": sorted(item["proposal_id"] for item in report["proposed_edges"]),
    }
    expected = {**body, "seal_sha256": sha256_json(body)}
    if seal != expected:
        if seal.get("report_sha256") != expected["report_sha256"]:
            raise BenchmarkError("report changed after it was sealed")
        for field, value in expected.items():
            if seal.get(field) != value:
                raise BenchmarkError(f"seal {field} does not match report")
        raise BenchmarkError("seal contains unexpected fields")
