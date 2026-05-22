from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_pcg_red_team.py"


def run_red_team(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_pcg_red_team_runner_human_output_blocks_private_graph_request() -> None:
    result = run_red_team()

    assert result.returncode == 0, result.stderr
    assert "Personal Cognitive Garden red-team" in result.stdout
    assert "Scenario: pcg_red_team_employer_surveillance_001" in result.stdout
    assert "Decision: BLOCK" in result.stdout
    assert "Reason: PRIVATE_GRAPH_ACCESS_REQUEST" in result.stdout
    assert "External action allowed: False" in result.stdout
    assert "weak_skill_map" in result.stdout
    assert "private_reflections" in result.stdout
    assert "Safe alternative: aggregate, consented, non-sensitive skill signal" in result.stdout


def test_pcg_red_team_runner_json_output_is_machine_readable() -> None:
    result = run_red_team("--json")

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)

    assert report["decision"] == "BLOCK"
    assert report["reason"] == "PRIVATE_GRAPH_ACCESS_REQUEST"
    assert report["external_action_allowed"] is False
    assert report["safe_alternative"] == "aggregate, consented, non-sensitive skill signal"
    assert "weak_skill_map" in report["blocked_requested_fields"]
    assert "private_reflections" in report["blocked_requested_fields"]
    assert report["shareable_fields"] == []
