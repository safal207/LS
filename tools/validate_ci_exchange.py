#!/usr/bin/env python3
"""Validate LS CI Node Mesh and CI Exchange metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = Path(".ci_nodes/registry.json")
AGENT_CONTEXT_PATH = Path(".ci_exchange/agent_context.latest.json")
ROUTES_DIR = Path(".ci_exchange/routes")
CONTEXTS_DIR = Path(".ci_exchange/contexts")
ANTI_PATTERNS_DIR = Path(".ci_exchange/anti_patterns")


class MetadataError(ValueError):
    """Raised when CI metadata is internally inconsistent."""


def load_json(repo_root: Path, path: Path) -> dict[str, Any]:
    with (repo_root / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate(repo_root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    errors.extend(_validate_registry(repo_root))
    errors.extend(_validate_routes(repo_root))
    errors.extend(_validate_contexts(repo_root))
    errors.extend(_validate_anti_patterns(repo_root))
    errors.extend(_validate_agent_context(repo_root))
    return errors


def _validate_registry(repo_root: Path) -> list[str]:
    errors: list[str] = []
    registry = load_json(repo_root, REGISTRY_PATH)
    nodes = registry.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return ["registry must contain a non-empty nodes list"]

    seen_node_ids: set[str] = set()
    for index, node in enumerate(nodes):
        node_id = _string_field(node, "node_id", f"registry.nodes[{index}]", errors)
        manifest_value = _string_field(node, "manifest", f"registry.nodes[{index}]", errors)
        if node_id:
            if node_id in seen_node_ids:
                errors.append(f"duplicate node_id in registry: {node_id}")
            seen_node_ids.add(node_id)
        if not manifest_value:
            continue
        manifest_path = Path(manifest_value)
        if not (repo_root / manifest_path).is_file():
            errors.append(f"registry manifest does not exist: {manifest_path}")
            continue
        manifest = load_json(repo_root, manifest_path)
        if node_id and manifest.get("node_id") != node_id:
            errors.append(f"manifest {manifest_path} node_id does not match registry node_id {node_id}")
        _string_field(manifest, "schema_version", str(manifest_path), errors)
        _string_field(manifest, "repo", str(manifest_path), errors)
        _string_field(manifest, "type", str(manifest_path), errors)
        _string_field(manifest, "authority", str(manifest_path), errors)
    return errors


def _validate_routes(repo_root: Path) -> list[str]:
    errors: list[str] = []
    route_paths = sorted((repo_root / ROUTES_DIR).glob("*.route.json"))
    if not route_paths:
        return ["at least one route export is required"]

    for route_file in route_paths:
        rel = route_file.relative_to(repo_root)
        route = load_json(repo_root, rel)
        _string_field(route, "schema_version", str(rel), errors)
        _string_field(route, "route_id", str(rel), errors)
        _string_field(route, "problem", str(rel), errors)
        if not isinstance(route.get("best_path"), dict):
            errors.append(f"{rel}: best_path must be an object")
        if not isinstance(route.get("evidence"), list) or not route.get("evidence"):
            errors.append(f"{rel}: evidence must be a non-empty list")
        if not isinstance(route.get("valid_for"), list) or not route.get("valid_for"):
            errors.append(f"{rel}: valid_for must be a non-empty list")
        if not isinstance(route.get("not_validated_for"), list):
            errors.append(f"{rel}: not_validated_for must be a list")
        markers = route.get("best_path", {}).get("observable_markers", [])
        if not isinstance(markers, list) or not markers:
            errors.append(f"{rel}: best_path.observable_markers must be a non-empty list")
    return errors


def _validate_contexts(repo_root: Path) -> list[str]:
    errors: list[str] = []
    context_paths = sorted((repo_root / CONTEXTS_DIR).glob("*.context.json"))
    if not context_paths:
        return ["at least one context export is required"]

    for context_file in context_paths:
        rel = context_file.relative_to(repo_root)
        context = load_json(repo_root, rel)
        _string_field(context, "schema_version", str(rel), errors)
        _string_field(context, "context_id", str(rel), errors)
        _string_field(context, "summary", str(rel), errors)
        if not isinstance(context.get("claims"), list) or not context.get("claims"):
            errors.append(f"{rel}: claims must be a non-empty list")
        if not isinstance(context.get("evidence"), list) or not context.get("evidence"):
            errors.append(f"{rel}: evidence must be a non-empty list")
    return errors


def _validate_anti_patterns(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for anti_pattern_file in sorted((repo_root / ANTI_PATTERNS_DIR).glob("*.antipattern.json")):
        rel = anti_pattern_file.relative_to(repo_root)
        anti_pattern = load_json(repo_root, rel)
        _string_field(anti_pattern, "schema_version", str(rel), errors)
        _string_field(anti_pattern, "anti_pattern_id", str(rel), errors)
        _string_field(anti_pattern, "symptom", str(rel), errors)
        _string_field(anti_pattern, "impact", str(rel), errors)
        _string_field(anti_pattern, "replacement", str(rel), errors)
        if not isinstance(anti_pattern.get("evidence"), list) or not anti_pattern.get("evidence"):
            errors.append(f"{rel}: evidence must be a non-empty list")
    return errors


def _validate_agent_context(repo_root: Path) -> list[str]:
    errors: list[str] = []
    context = load_json(repo_root, AGENT_CONTEXT_PATH)
    _string_field(context, "schema_version", str(AGENT_CONTEXT_PATH), errors)
    _string_field(context, "context_id", str(AGENT_CONTEXT_PATH), errors)
    _string_field(context, "summary", str(AGENT_CONTEXT_PATH), errors)
    _string_field(context, "next_recommended_action", str(AGENT_CONTEXT_PATH), errors)
    _string_field(context, "authority_boundary", str(AGENT_CONTEXT_PATH), errors)

    for field in ["generated_from", "known_working_routes", "known_bad_routes", "evidence", "valid_for", "not_validated_for"]:
        if not isinstance(context.get(field), list) or not context.get(field):
            errors.append(f"{AGENT_CONTEXT_PATH}: {field} must be a non-empty list")

    for generated_from in context.get("generated_from", []):
        generated_path = Path(str(generated_from))
        if not (repo_root / generated_path).exists():
            errors.append(f"{AGENT_CONTEXT_PATH}: generated_from path does not exist: {generated_path}")

    working_route_ids = {route.get("route_id") for route in context.get("known_working_routes", [])}
    if "ls.route.grok_review.command_pr_pull_request" not in working_route_ids:
        errors.append(f"{AGENT_CONTEXT_PATH}: missing Grok command PR working route")

    bad_route_ids = {route.get("route_id") for route in context.get("known_bad_routes", [])}
    for expected in ["connector_issue_comment_command", "connector_push_command_branch", "pull_request_target_command_pr"]:
        if expected not in bad_route_ids:
            errors.append(f"{AGENT_CONTEXT_PATH}: missing known bad route {expected}")
    return errors


def _string_field(data: dict[str, Any], field: str, subject: str, errors: list[str]) -> str | None:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{subject}: {field} must be a non-empty string")
        return None
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()

    errors = validate(args.repo_root.resolve())
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("CI Exchange metadata validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
