#!/usr/bin/env python3
"""Validate the individual-system-environment overlay for a causal phase trail."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
LEVELS = {"INDIVIDUAL", "SYSTEM", "ENVIRONMENT"}
MODES = {"INTRA_LEVEL", "CROSS_LEVEL"}
MECHANISMS = {
    "OBSERVES",
    "CONSTRAINS",
    "MODIFIES",
    "INVALIDATES",
    "CONFIRMS",
    "ADAPTS_TO",
    "AMPLIFIES",
    "BLOCKS",
}
REQUIRED_FEEDBACK = {
    ("INDIVIDUAL", "SYSTEM"),
    ("SYSTEM", "INDIVIDUAL"),
    ("SYSTEM", "ENVIRONMENT"),
    ("ENVIRONMENT", "SYSTEM"),
}


class LevelOverlayError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LevelOverlayError(message)


def require_object(value: Any, name: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{name} must be an object")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    require(isinstance(value, list), f"{name} must be an array")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    require(set(value) == expected, f"{name} contains missing or unknown fields")


def require_id(value: Any, name: str) -> None:
    require(isinstance(value, str) and bool(ID_RE.fullmatch(value)), f"{name} is invalid")


def require_sha(value: Any, name: str) -> None:
    require(isinstance(value, str) and bool(SHA_RE.fullmatch(value)), f"{name} must be a full lowercase SHA")


def index_unique(items: list[dict[str, Any]], key: str, name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        item = require_object(item, f"{name}[{index}]")
        item_id = item.get(key)
        require_id(item_id, f"{name}[{index}].{key}")
        require(item_id not in result, f"duplicate {name} id: {item_id}")
        result[item_id] = item
    return result


def validate_level_overlay(trail: dict[str, Any], overlay: dict[str, Any]) -> None:
    trail = require_object(trail, "trail")
    overlay = require_object(overlay, "overlay")
    exact_keys(
        overlay,
        {
            "schemaVersion",
            "overlayId",
            "authority",
            "trailRef",
            "levelDefinitions",
            "assignments",
            "interactions",
            "summary",
        },
        "overlay",
    )
    require(overlay["schemaVersion"] == "ls.causal-level-overlay.v0", "unsupported overlay schemaVersion")
    require(isinstance(overlay["overlayId"], str) and overlay["overlayId"].startswith("CLO-"), "overlayId is invalid")
    require(overlay["authority"] == "EVIDENCE_ONLY", "overlay must remain evidence-only")

    trail_ref = require_object(overlay["trailRef"], "trailRef")
    exact_keys(trail_ref, {"trailId", "path", "currentHead"}, "trailRef")
    require(trail_ref["trailId"] == trail.get("trailId"), "trailRef.trailId does not match trail")
    require(isinstance(trail_ref["path"], str) and trail_ref["path"], "trailRef.path is invalid")
    require_sha(trail_ref["currentHead"], "trailRef.currentHead")
    require(
        trail_ref["currentHead"] == trail.get("subject", {}).get("currentHead"),
        "trailRef.currentHead does not match trail currentHead",
    )

    definitions = require_list(overlay["levelDefinitions"], "levelDefinitions")
    require(len(definitions) == 3, "levelDefinitions must define exactly three levels")
    defined_levels: set[str] = set()
    for index, definition in enumerate(definitions):
        definition = require_object(definition, f"levelDefinitions[{index}]")
        exact_keys(definition, {"level", "meaning"}, f"levelDefinitions[{index}]")
        require(definition["level"] in LEVELS, f"levelDefinitions[{index}].level is invalid")
        require(definition["level"] not in defined_levels, f"duplicate level definition: {definition['level']}")
        require(isinstance(definition["meaning"], str) and definition["meaning"], f"levelDefinitions[{index}].meaning is invalid")
        defined_levels.add(definition["level"])
    require(defined_levels == LEVELS, "levelDefinitions must contain INDIVIDUAL, SYSTEM and ENVIRONMENT")

    trail_nodes = require_list(trail.get("nodes"), "trail.nodes")
    trail_node_index = index_unique(trail_nodes, "id", "trail.nodes")
    trail_edges = require_list(trail.get("edges"), "trail.edges")
    trail_edge_index = index_unique(trail_edges, "id", "trail.edges")

    assignments = require_list(overlay["assignments"], "assignments")
    require(assignments, "assignments must not be empty")
    level_by_node: dict[str, str] = {}
    for index, assignment in enumerate(assignments):
        assignment = require_object(assignment, f"assignments[{index}]")
        exact_keys(assignment, {"nodeId", "level", "rationale"}, f"assignments[{index}]")
        node_id = assignment["nodeId"]
        require_id(node_id, f"assignments[{index}].nodeId")
        require(node_id in trail_node_index, f"assignment references unknown trail node {node_id}")
        require(node_id not in level_by_node, f"duplicate level assignment for {node_id}")
        require(assignment["level"] in LEVELS, f"assignment level for {node_id} is invalid")
        require(isinstance(assignment["rationale"], str) and assignment["rationale"], f"assignment rationale for {node_id} is required")
        level_by_node[node_id] = assignment["level"]
    missing = set(trail_node_index) - set(level_by_node)
    extra = set(level_by_node) - set(trail_node_index)
    require(not missing, f"every trail node must have a causal level; missing: {sorted(missing)}")
    require(not extra, f"assignments contain unknown nodes: {sorted(extra)}")
    require(set(level_by_node.values()) == LEVELS, "all three causal levels must be represented by nodes")

    interactions = require_list(overlay["interactions"], "interactions")
    require(len(interactions) >= 4, "at least four level interactions are required")
    interaction_ids: set[str] = set()
    observed_pairs: set[tuple[str, str]] = set()
    for index, interaction in enumerate(interactions):
        interaction = require_object(interaction, f"interactions[{index}]")
        exact_keys(
            interaction,
            {
                "id",
                "edgeId",
                "fromNodeId",
                "toNodeId",
                "fromLevel",
                "toLevel",
                "mode",
                "mechanism",
                "evidenceNodeIds",
                "explanation",
            },
            f"interactions[{index}]",
        )
        interaction_id = interaction["id"]
        require_id(interaction_id, f"interactions[{index}].id")
        require(interaction_id not in interaction_ids, f"duplicate interaction id: {interaction_id}")
        interaction_ids.add(interaction_id)
        from_node = interaction["fromNodeId"]
        to_node = interaction["toNodeId"]
        require(from_node in trail_node_index, f"interaction {interaction_id} has unknown fromNodeId")
        require(to_node in trail_node_index, f"interaction {interaction_id} has unknown toNodeId")
        require(from_node != to_node, f"interaction {interaction_id} cannot self-reference")
        require(interaction["fromLevel"] == level_by_node[from_node], f"interaction {interaction_id} fromLevel disagrees with assignment")
        require(interaction["toLevel"] == level_by_node[to_node], f"interaction {interaction_id} toLevel disagrees with assignment")
        expected_mode = "INTRA_LEVEL" if interaction["fromLevel"] == interaction["toLevel"] else "CROSS_LEVEL"
        require(interaction["mode"] in MODES, f"interaction {interaction_id} mode is invalid")
        require(interaction["mode"] == expected_mode, f"interaction {interaction_id} mode does not match its levels")
        require(interaction["mechanism"] in MECHANISMS, f"interaction {interaction_id} mechanism is invalid")
        evidence_ids = require_list(interaction["evidenceNodeIds"], f"interaction {interaction_id}.evidenceNodeIds")
        require(evidence_ids, f"interaction {interaction_id} needs evidenceNodeIds")
        require(len(evidence_ids) == len(set(evidence_ids)), f"interaction {interaction_id} duplicates evidence nodes")
        for evidence_id in evidence_ids:
            require(evidence_id in trail_node_index, f"interaction {interaction_id} references unknown evidence node {evidence_id}")
        require(isinstance(interaction["explanation"], str) and interaction["explanation"], f"interaction {interaction_id} explanation is required")

        edge_id = interaction["edgeId"]
        if edge_id is not None:
            require_id(edge_id, f"interaction {interaction_id}.edgeId")
            require(edge_id in trail_edge_index, f"interaction {interaction_id} references unknown edge {edge_id}")
            edge = trail_edge_index[edge_id]
            require(edge["from"] == from_node, f"interaction {interaction_id} fromNodeId disagrees with edge")
            require(edge["to"] == to_node, f"interaction {interaction_id} toNodeId disagrees with edge")
        else:
            require(
                len(evidence_ids) >= 2,
                f"derived interaction {interaction_id} without edgeId needs at least two evidence nodes",
            )
        if interaction["mode"] == "CROSS_LEVEL":
            observed_pairs.add((interaction["fromLevel"], interaction["toLevel"]))

    missing_feedback = REQUIRED_FEEDBACK - observed_pairs
    require(
        not missing_feedback,
        f"level interaction loop is incomplete; missing directed pairs: {sorted(missing_feedback)}",
    )

    summary = require_object(overlay["summary"], "summary")
    exact_keys(summary, {"dominantLoop", "conclusion"}, "summary")
    dominant_loop = require_list(summary["dominantLoop"], "summary.dominantLoop")
    require(len(dominant_loop) >= 4, "dominantLoop must show a closed multi-level cycle")
    for level in dominant_loop:
        require(level in LEVELS, f"dominantLoop contains unknown level {level}")
    require(dominant_loop[0] == dominant_loop[-1], "dominantLoop must return to its starting level")
    require(set(dominant_loop) == LEVELS, "dominantLoop must include all three levels")
    require(isinstance(summary["conclusion"], str) and summary["conclusion"], "summary.conclusion is required")


def load_json(path: Path, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LevelOverlayError(f"cannot read {name}: {exc}") from exc
    return require_object(payload, name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trail", type=Path)
    parser.add_argument("overlay", type=Path)
    args = parser.parse_args()
    try:
        trail = load_json(args.trail, "trail")
        overlay = load_json(args.overlay, "overlay")
        validate_level_overlay(trail, overlay)
    except LevelOverlayError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {overlay['overlayId']} -> individual/system/environment loop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
