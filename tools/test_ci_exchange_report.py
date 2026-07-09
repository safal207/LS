from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_REPORT = ROOT / ".ci_exchange/health/ci_exchange_health.json"
MD_REPORT = ROOT / ".ci_exchange/health/ci_exchange_health.md"


def test_ci_exchange_report_command_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "tools/generate_ci_exchange_health.py", "--check"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_ci_exchange_report_files_exist() -> None:
    assert JSON_REPORT.is_file()
    assert MD_REPORT.is_file()


def test_ci_exchange_report_json_status() -> None:
    report = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    assert report["status"] == "pass"
    assert report["errors"] == []
    assert report["known_working_route"] == "ls.route.grok_review.command_pr_pull_request"
    assert {section["name"] for section in report["sections"]} >= {
        "registry",
        "node_manifests",
        "routes",
        "contexts",
        "agent_context",
    }
