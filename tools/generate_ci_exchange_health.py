#!/usr/bin/env python3
"""Generate a human-readable health report for LS CI Exchange metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_ci_exchange import validate

ROOT = Path(__file__).resolve().parents[1]
HEALTH_JSON_PATH = Path(".ci_exchange/health/latest.json")
HEALTH_MARKDOWN_PATH = Path(".ci_exchange/health/latest.md")
REGISTRY_PATH = Path(".ci_nodes/registry.json")
AGENT_CONTEXT_PATH = Path(".ci_exchange/agent_context.latest.json")
ROUTES_DIR = Path(".ci_exchange/routes")
CONTEXTS_DIR = Path(".ci_exchange/contexts")
ANTI_PATTERNS_DIR = Path(".ci_exchange/anti_patterns")


def _load_json(repo_root: Path, path: Path) -> dict[str, Any]:
    with (repo_root / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _json_dump(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def build_health_report(repo_root: Path = ROOT) -> dict[str, Any]:
    errors = validate(repo_root)
    registry = _load_json(repo_root, REGISTRY_PATH)
    agent_context = _load_json(repo_root, AGENT_CONTEXT_PATH)

    route_paths = sorted((repo_root / ROUTES_DIR).glob("*.route.json"))
    context_paths = sorted((repo_root / CONTEXTS_DIR).glob("*.context.json"))
    anti_pattern_paths = sorted((repo_root / ANTI_PATTERNS_DIR).glob("*.antipattern.json"))
    node_manifests = [node.get("manifest") for node in registry.get("nodes", []) if node.get("manifest")]

    status = "pass" if not errors else "fail"

    return {
        "schema_version": "ls.ci_exchange.health.v0.1",
        "report_id": "ls.ci_exchange.health.latest",
        "status": status,
        "summary": "CI Exchange metadata is internally consistent." if status == "pass" else "CI Exchange metadata has consistency errors.",
        "checks": [
            {
                "name": "metadata_validator",
                "status": status,
                "error_count": len(errors),
            },
            {
                "name": "registry",
                "status": "pass" if registry.get("nodes") else "fail",
                "node_count": len(registry.get("nodes", [])),
                "manifest_count": len(node_manifests),
            },
            {
                "name": "routes",
                "status": "pass" if route_paths else "fail",
                "route_count": len(route_paths),
            },
            {
                "name": "contexts",
                "status": "pass" if context_paths else "fail",
                "context_count": len(context_paths),
            },
            {
                "name": "anti_patterns",
                "status": "pass" if anti_pattern_paths else "fail",
                "anti_pattern_count": len(anti_pattern_paths),
            },
            {
                "name": "agent_context",
                "status": "pass" if agent_context.get("known_working_routes") else "fail",
                "generated_from_count": len(agent_context.get("generated_from", [])),
                "known_working_route_count": len(agent_context.get("known_working_routes", [])),
                "known_bad_route_count": len(agent_context.get("known_bad_routes", [])),
            },
        ],
        "counts": {
            "nodes": len(registry.get("nodes", [])),
            "node_manifests": len(node_manifests),
            "routes": len(route_paths),
            "contexts": len(context_paths),
            "anti_patterns": len(anti_pattern_paths),
            "agent_context_sources": len(agent_context.get("generated_from", [])),
            "known_working_routes": len(agent_context.get("known_working_routes", [])),
            "known_bad_routes": len(agent_context.get("known_bad_routes", [])),
        },
        "errors": errors,
        "sources": {
            "registry": str(REGISTRY_PATH),
            "agent_context": str(AGENT_CONTEXT_PATH),
            "routes_dir": str(ROUTES_DIR),
            "contexts_dir": str(CONTEXTS_DIR),
            "anti_patterns_dir": str(ANTI_PATTERNS_DIR),
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# CI Exchange Health Report",
        "",
        f"Status: **{report['status'].upper()}**",
        "",
        report["summary"],
        "",
        "## Checks",
        "",
        "| Check | Status | Details |",
        "| --- | --- | --- |",
    ]

    for check in report["checks"]:
        details = ", ".join(
            f"{key}={value}"
            for key, value in check.items()
            if key not in {"name", "status"}
        )
        lines.append(f"| {check['name']} | {check['status']} | {details} |")

    lines.extend([
        "",
        "## Counts",
        "",
    ])
    for key, value in report["counts"].items():
        lines.append(f"- {key}: {value}")

    if report["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in report["errors"]:
            lines.append(f"- {error}")

    lines.extend([
        "",
        "## Boundary",
        "",
        "This report checks static CI Exchange metadata consistency. It does not prove that external services are currently available.",
        "",
    ])
    return "\n".join(lines)


def write_reports(repo_root: Path = ROOT) -> None:
    report = build_health_report(repo_root)
    (repo_root / HEALTH_JSON_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / HEALTH_JSON_PATH).write_text(_json_dump(report), encoding="utf-8")
    (repo_root / HEALTH_MARKDOWN_PATH).write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true", help="Fail if committed reports are stale.")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    report = build_health_report(repo_root)
    markdown = render_markdown(report)

    if args.check:
        current_json = json.loads((repo_root / HEALTH_JSON_PATH).read_text(encoding="utf-8"))
        current_md = (repo_root / HEALTH_MARKDOWN_PATH).read_text(encoding="utf-8")
        if current_json != report or current_md != markdown:
            raise SystemExit("CI Exchange health report is stale; run tools/generate_ci_exchange_health.py")
        return 0

    (repo_root / HEALTH_JSON_PATH).parent.mkdir(parents=True, exist_ok=True)
    (repo_root / HEALTH_JSON_PATH).write_text(_json_dump(report), encoding="utf-8")
    (repo_root / HEALTH_MARKDOWN_PATH).write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
