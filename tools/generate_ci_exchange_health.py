#!/usr/bin/env python3
"""Generate health reports for LS CI Exchange metadata."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from validate_ci_exchange import (
    AGENT_CONTEXT_PATH,
    ANTI_PATTERNS_DIR,
    CONTEXTS_DIR,
    REGISTRY_PATH,
    ROUTES_DIR,
    load_json,
    validate,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON_OUTPUT = Path(".ci_exchange/health/ci_exchange_health.json")
DEFAULT_MARKDOWN_OUTPUT = Path(".ci_exchange/health/ci_exchange_health.md")


@dataclass(frozen=True)
class Section:
    name: str
    status: str
    count: int
    detail: str


def build_health_report(repo_root: Path = ROOT) -> dict[str, Any]:
    errors = validate(repo_root)
    sections = _build_sections(repo_root, errors)

    return {
        "schema_version": "ls.ci_exchange.health.v0.1",
        "status": "pass" if not errors else "fail",
        "summary": "CI Exchange metadata is internally consistent." if not errors else "CI Exchange metadata has validation errors.",
        "sections": [section.__dict__ for section in sections],
        "errors": errors,
        "validated_paths": [
            str(REGISTRY_PATH),
            str(ROUTES_DIR),
            str(CONTEXTS_DIR),
            str(ANTI_PATTERNS_DIR),
            str(AGENT_CONTEXT_PATH),
        ],
        "known_working_route": "ls.route.grok_review.command_pr_pull_request",
        "authority_boundary": "Health reports describe static metadata consistency only; they do not approve, merge, deploy, or replace operational smoke tests.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    status_icon = "✅" if report["status"] == "pass" else "❌"
    lines = [
        "# CI Exchange Health Report",
        "",
        f"Status: {status_icon} `{report['status']}`",
        "",
        report["summary"],
        "",
        "## Sections",
        "",
        "| Section | Status | Count | Detail |",
        "| --- | --- | ---: | --- |",
    ]

    for section in report["sections"]:
        icon = "✅" if section["status"] == "pass" else "❌"
        lines.append(
            f"| {section['name']} | {icon} `{section['status']}` | {section['count']} | {section['detail']} |"
        )

    lines.extend(["", "## Validated paths", ""])
    for path in report["validated_paths"]:
        lines.append(f"- `{path}`")

    lines.extend(["", "## Errors", ""])
    if report["errors"]:
        for error in report["errors"]:
            lines.append(f"- {error}")
    else:
        lines.append("No metadata validation errors were found.")

    lines.extend(
        [
            "",
            "## Authority boundary",
            "",
            report["authority_boundary"],
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(
    repo_root: Path = ROOT,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    markdown_output: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> dict[str, Any]:
    report = build_health_report(repo_root)
    json_path = repo_root / json_output
    markdown_path = repo_root / markdown_output
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return report


def check_reports(
    repo_root: Path = ROOT,
    json_output: Path = DEFAULT_JSON_OUTPUT,
    markdown_output: Path = DEFAULT_MARKDOWN_OUTPUT,
) -> dict[str, Any]:
    report = build_health_report(repo_root)
    json_path = repo_root / json_output
    markdown_path = repo_root / markdown_output

    current_json = json.loads(json_path.read_text(encoding="utf-8"))
    current_markdown = markdown_path.read_text(encoding="utf-8")

    expected_markdown = render_markdown(report)
    if current_json != report:
        raise SystemExit("ci_exchange_health.json is stale; run tools/generate_ci_exchange_health.py")
    if current_markdown != expected_markdown:
        raise SystemExit("ci_exchange_health.md is stale; run tools/generate_ci_exchange_health.py")
    return report


def _build_sections(repo_root: Path, errors: list[str]) -> list[Section]:
    registry = load_json(repo_root, REGISTRY_PATH)
    agent_context = load_json(repo_root, AGENT_CONTEXT_PATH)
    routes = sorted((repo_root / ROUTES_DIR).glob("*.route.json"))
    contexts = sorted((repo_root / CONTEXTS_DIR).glob("*.context.json"))
    anti_patterns = sorted((repo_root / ANTI_PATTERNS_DIR).glob("*.antipattern.json"))

    return [
        Section(
            name="registry",
            status=_section_status(errors, "registry", str(REGISTRY_PATH)),
            count=len(registry.get("nodes", [])),
            detail="registered CI nodes",
        ),
        Section(
            name="node_manifests",
            status=_section_status(errors, "manifest", ".ci_nodes/nodes"),
            count=_count_existing_manifests(repo_root, registry),
            detail="reachable node manifests",
        ),
        Section(
            name="routes",
            status=_section_status(errors, "route", str(ROUTES_DIR)),
            count=len(routes),
            detail="route exports",
        ),
        Section(
            name="contexts",
            status=_section_status(errors, "context", str(CONTEXTS_DIR)),
            count=len(contexts),
            detail="context exports",
        ),
        Section(
            name="anti_patterns",
            status=_section_status(errors, "anti_pattern", str(ANTI_PATTERNS_DIR)),
            count=len(anti_patterns),
            detail="anti-pattern exports",
        ),
        Section(
            name="agent_context",
            status=_section_status(errors, "agent_context", str(AGENT_CONTEXT_PATH)),
            count=len(agent_context.get("known_working_routes", [])) + len(agent_context.get("known_bad_routes", [])),
            detail="known route entries",
        ),
    ]


def _section_status(errors: list[str], *needles: str) -> str:
    lowered = [error.lower() for error in errors]
    for error in lowered:
        if any(needle.lower() in error for needle in needles):
            return "fail"
    return "pass"


def _count_existing_manifests(repo_root: Path, registry: dict[str, Any]) -> int:
    count = 0
    for node in registry.get("nodes", []):
        manifest = node.get("manifest")
        if manifest and (repo_root / str(manifest)).is_file():
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MARKDOWN_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if committed reports are stale or metadata is unhealthy.")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    if args.check:
        report = check_reports(repo_root, args.json_output, args.markdown_output)
    else:
        report = write_reports(repo_root, args.json_output, args.markdown_output)

    if report["status"] != "pass":
        return 1
    print(f"CI Exchange health: {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
