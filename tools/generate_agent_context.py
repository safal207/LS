#!/usr/bin/env python3
"""Generate the latest LS agent context from CI Exchange metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROUTE_PATH = Path(".ci_exchange/routes/grok-review-command-bus.route.json")
CONTEXT_PATH = Path(".ci_exchange/contexts/connector-safe-command-bus.context.json")
OUTPUT_PATH = Path(".ci_exchange/agent_context.latest.json")


def _load_json(repo_root: Path, path: Path) -> dict[str, Any]:
    with (repo_root / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def build_agent_context(repo_root: Path = ROOT) -> dict[str, Any]:
    route = _load_json(repo_root, ROUTE_PATH)
    context = _load_json(repo_root, CONTEXT_PATH)

    best_path = route.get("best_path", {})
    markers = best_path.get("observable_markers", [])
    route_id = route.get("route_id", "unknown")

    known_working_routes = [
        {
            "route_id": route_id,
            "description": (
                "Create or update a same-repository command PR whose branch starts with "
                "ci/grok-review-command and whose diff changes .github/grok-review-command.json. "
                "The pull_request workflow reads the JSON command, publishes source diagnostic, "
                "target ack, Grok review, and target result markers."
            ),
            "route_export": str(ROUTE_PATH),
            "confidence": route.get("confidence", "medium"),
            "evidence_refs": [item.get("ref", "") for item in route.get("evidence", [])],
            "observable_markers": markers,
        }
    ]

    known_bad_routes = []
    for bad_path in route.get("bad_paths", []):
        route_type = bad_path.get("type", "unknown")
        known_bad_routes.append(
            {
                "route_id": route_type,
                "description": bad_path.get("result", "Recorded as a non-winning route in LS evidence."),
                "replacement": route_id,
                "evidence_refs": _evidence_for_bad_route(route_type),
                "confidence": _confidence_for_bad_route(route_type),
            }
        )

    summary = context.get(
        "summary",
        "Use the PR-backed command-file route for connector-safe Grok review requests.",
    )

    return {
        "schema_version": "ls.agent_context.v0.1",
        "context_id": "ls.agent_context.latest",
        "generated_from": [
            ".ci_nodes/registry.json",
            str(ROUTE_PATH),
            str(CONTEXT_PATH),
            "docs/CI_NODE_MESH.md",
        ],
        "summary": summary,
        "known_working_routes": known_working_routes,
        "known_bad_routes": known_bad_routes,
        "next_recommended_action": (
            "For new connector-safe review requests, create or update a same-repository "
            "command PR using the pull_request command-file route. Watch for source "
            "diagnostic first, then target ack, then target result."
        ),
        "authority_boundary": (
            "This file is advisory memory for agents. It does not approve, merge, deploy, "
            "or replace human review."
        ),
        "evidence": _merge_evidence(route.get("evidence", []), context.get("evidence", [])),
        "valid_for": route.get("valid_for", context.get("valid_for", [])),
        "not_validated_for": route.get("not_validated_for", context.get("not_validated_for", [])),
    }


def _evidence_for_bad_route(route_type: str) -> list[str]:
    mapping = {
        "issue_comment": ["#842", "#843", "#838 smoke target"],
        "push_command_branch": ["#844", "#838 smoke target"],
        "pull_request_target": ["#845", "#847 before #848"],
    }
    return mapping.get(route_type, [])


def _confidence_for_bad_route(route_type: str) -> str:
    if route_type in {"issue_comment", "push_command_branch"}:
        return "medium_high"
    return "medium"


def _merge_evidence(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    merged: list[dict[str, Any]] = []
    for group in groups:
        for item in group:
            key = (str(item.get("kind", "")), str(item.get("ref", "")))
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--check", action="store_true", help="Fail if the committed output is stale.")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_path = repo_root / args.output
    generated = _dump_json(build_agent_context(repo_root))

    if args.check:
        current = output_path.read_text(encoding="utf-8")
        if current != generated:
            raise SystemExit("agent_context.latest.json is stale; run tools/generate_agent_context.py")
        return 0

    output_path.write_text(generated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
