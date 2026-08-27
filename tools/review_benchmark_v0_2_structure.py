from __future__ import annotations

from typing import Any

from review_benchmark_v0_2_common import (
    PROBE_STATUSES,
    RELATION_STATUSES,
    BenchmarkV02Error,
    exact,
    repo_path,
    strings,
    text,
)


def validate_structured(value: Any, lane: str, finding_ids: set[str]) -> None:
    exact(value, {"artifact_nodes", "relations", "probes"}, "structured_analysis")
    for name in ("artifact_nodes", "relations", "probes"):
        if not isinstance(value[name], list):
            raise BenchmarkV02Error(f"structured_analysis.{name} must be an array")
        if lane == "LS" and not value[name]:
            raise BenchmarkV02Error(f"LS report requires non-empty {name}")

    node_ids: set[str] = set()
    for index, node in enumerate(value["artifact_nodes"]):
        exact(node, {"node_id", "kind", "path", "observation"}, f"nodes[{index}]")
        node_id = text(node["node_id"], "node_id")
        if node_id in node_ids:
            raise BenchmarkV02Error(f"duplicate node_id: {node_id}")
        node_ids.add(node_id)
        text(node["kind"], "node.kind")
        repo_path(node["path"], "node.path")
        text(node["observation"], "node.observation")

    relation_ids: set[str] = set()
    for index, relation in enumerate(value["relations"]):
        exact(
            relation,
            {"relation_id", "source_node", "target_node", "relation_type", "status", "evidence_finding_ids"},
            f"relations[{index}]",
        )
        relation_id = text(relation["relation_id"], "relation_id")
        if relation_id in relation_ids:
            raise BenchmarkV02Error(f"duplicate relation_id: {relation_id}")
        relation_ids.add(relation_id)
        if relation["source_node"] not in node_ids or relation["target_node"] not in node_ids:
            raise BenchmarkV02Error("relation references unknown node")
        text(relation["relation_type"], "relation_type")
        if relation["status"] not in RELATION_STATUSES:
            raise BenchmarkV02Error("relation status is invalid")
        refs = strings(relation["evidence_finding_ids"], "relation evidence")
        if any(ref not in finding_ids for ref in refs):
            raise BenchmarkV02Error("relation references unknown finding")

    probe_ids: set[str] = set()
    for index, probe in enumerate(value["probes"]):
        exact(
            probe,
            {"probe_id", "kind", "status", "command", "observation", "evidence_finding_ids"},
            f"probes[{index}]",
        )
        probe_id = text(probe["probe_id"], "probe_id")
        if probe_id in probe_ids:
            raise BenchmarkV02Error(f"duplicate probe_id: {probe_id}")
        probe_ids.add(probe_id)
        text(probe["kind"], "probe.kind")
        if probe["status"] not in PROBE_STATUSES:
            raise BenchmarkV02Error("probe.status is invalid")
        if probe["command"] is not None:
            text(probe["command"], "probe.command")
        text(probe["observation"], "probe.observation")
        refs = strings(probe["evidence_finding_ids"], "probe evidence")
        if any(ref not in finding_ids for ref in refs):
            raise BenchmarkV02Error("probe references unknown finding")
