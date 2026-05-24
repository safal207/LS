from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_report(*args: str) -> subprocess.CompletedProcess[str]:
    script = ROOT / "scripts" / "prepare_network_precision_contributor_report.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )


def test_contributor_report_json_contains_summary_and_roster() -> None:
    result = _run_report("--json", "--runner", "test-runner")
    payload = json.loads(result.stdout)
    summary = payload["summary"]

    assert payload["report_version"] == "network_precision_contributor_report.v0.1"
    assert payload["runner"] == "test-runner"
    assert summary["network_precision_gain_over_baseline"] > 0
    assert summary["measured_route_reward_gain"] > 0
    assert "codex-self-use" in summary["ready_actors"]
    assert "python scripts/run_network_precision_gain_demo.py --json" in payload["commands"]


def test_contributor_report_markdown_is_issue_ready() -> None:
    result = _run_report("--runner", "test-runner")

    assert "# LS Network Precision Contributor Report" in result.stdout
    assert "- Runner: test-runner" in result.stdout
    assert "network_precision_gain_over_baseline" in result.stdout
    assert "## Ready Actors" in result.stdout
    assert "not a model leaderboard" in result.stdout
