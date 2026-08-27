#!/usr/bin/env python3
"""Generate a compact CI Exchange metadata health report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_ci_exchange import validate_sections

ROOT = Path(__file__).resolve().parents[1]
JSON_OUTPUT = Path(".ci_exchange/health.latest.json")
MARKDOWN_OUTPUT = Path(".ci_exchange/health.latest.md")

CHECKS = [
    {
        "check_id": "registry",
        "summary": "CI node registry is present and references reachable node manifests.",
        "evidence": [".ci_nodes/registry.json", ".ci_nodes/nodes"],
    },
    {
        "check_id": "routes",
        "summary": "Route exports include best path, markers, evidence, and applicability boundaries.",
        "evidence": [".ci_exchange/routes/grok-review-command-bus.route.json"],
    },
    {
        "check_id": "contexts",
        "summary": "Context exports include summary, claims, and evidence.",
        "evidence": [".ci_exchange/contexts/connector-safe-command-bus.context.json"],
    },
    {
        "check_id": "anti_patterns",
        "summary": "Anti-pattern exports include symptom, impact, replacement, and evidence.",
        "evidence": [".ci_exchange/anti_patterns/connector-issue-comment-trigger.antipattern.json"],
    },
    {
        "check_id": "agent_context",
        "summary": "Latest agent context references existing sources and keeps key route memory.",
        "evidence": [".ci_exchange/agent_context.latest.json"],
    },
]


def _normalized_runtime_error(exc: Exception) -> str:
    """Return deterministic validation failure details without host-specific paths."""

    error_type = type(exc).__name__
    if isinstance(exc, json.JSONDecodeError):
        return f"validate_ci_exchange crashed: {error_type}: line={exc.lineno},column={exc.colno}"
    if isinstance(exc, UnicodeDecodeError):
        return (
            f"validate_ci_exchange crashed: {error_type}: "
            f"encoding={exc.encoding},start={exc.start},end={exc.end}"
        )
    if isinstance(exc, OSError) and exc.errno is not None:
        return f"validate_ci_exchange crashed: {error_type}: errno={exc.errno}"
    return f"validate_ci_exchange crashed: {error_type}"


def build_health_report(repo_root: Path = ROOT) -> dict[str, Any]:
    runtime_errors: list[str] = []
    try:
        section_errors = validate_sections(repo_root)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError, ValueError) as exc:
        section_errors = {check["check_id"]: [] for check in CHECKS}
        runtime_errors.append(_normalized_runtime_error(exc))

    all_errors = [error for errors in section_errors.values() for error in errors]
    all_errors.extend(runtime_errors)
    status = "pass" if not all_errors else "fail"
    checks = []
    for check in CHECKS:
        check_id = check["check_id"]
        errors = section_errors.get(check_id, [])
        checks.append(
            {
                "check_id": check_id,
                "status": "pass" if not errors and not runtime_errors else ("unknown" if runtime_errors else "fail"),
                "summary": check["summary"],
                "evidence": check["evidence"],
                "errors": errors,
            }
        )

    if runtime_errors:
        checks.append(
            {
                "check_id": "validator_runtime",
                "status": "fail",
                "summary": "The metadata validator must complete before section health can be trusted.",
                "evidence": ["tools/validate_ci_exchange.py"],
                "errors": runtime_errors,
            }
        )

    return {
        "schema_version": "ls.ci_exchange_health.v0.1",
        "report_id": "ls.ci_exchange.health.latest",
        "status": status,
        "generated_from": [
            "tools/validate_ci_exchange.py",
            ".ci_nodes/registry.json",
            ".ci_exchange/routes/grok-review-command-bus.route.json",
            ".ci_exchange/contexts/connector-safe-command-bus.context.json",
            ".ci_exchange/anti_patterns/connector-issue-comment-trigger.antipattern.json",
            ".ci_exchange/agent_context.latest.json",
        ],
        "checks": checks,
        "errors": all_errors,
        "boundary": (
            "This report checks static CI Exchange metadata health only. It does not run the "
            "Grok command bus, call external model providers, approve pull requests, or prove "
            "that a route is operationally healthy right now."
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# CI Exchange Health Report",
        "",
        f"Status: **{report['status'].upper()}**",
        "",
        "## Checks",
        "",
        "| Check | Status | Summary | Errors |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        errors = check.get("errors", [])
        error_summary = "None" if not errors else f"{len(errors)} error(s)"
        lines.append(
            f"| `{check['check_id']}` | `{check['status']}` | {check['summary']} | {error_summary} |"
        )

    lines.extend(["", "## Generated from", ""])
    for path in report["generated_from"]:
        lines.append(f"- `{path}`")

    lines.extend(["", "## Boundary", "", report["boundary"], ""])

    if report["errors"]:
        lines.extend(["## Errors", ""])
        for error in report["errors"]:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines)


def _dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _read_committed_output(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(
            f"Missing CI Exchange health report output: {exc.filename}; "
            "run tools/generate_ci_exchange_health.py"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--json-output", type=Path, default=JSON_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=MARKDOWN_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Fail if committed health reports are stale.")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    report = build_health_report(repo_root)
    json_text = _dump_json(report)
    markdown_text = render_markdown(report)

    if args.check:
        current_json = _read_committed_output(repo_root / args.json_output)
        current_markdown = _read_committed_output(repo_root / args.markdown_output)
        if current_json != json_text or current_markdown != markdown_text:
            raise SystemExit("CI Exchange health reports are stale; run tools/generate_ci_exchange_health.py")
        return 0 if report["status"] == "pass" else 1

    (repo_root / args.json_output).write_text(json_text, encoding="utf-8")
    (repo_root / args.markdown_output).write_text(markdown_text, encoding="utf-8")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
