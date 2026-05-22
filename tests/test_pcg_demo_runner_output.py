from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_personal_cognitive_garden_demo.py"


def run_demo(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_pcg_demo_runner_human_output_locks_core_fields() -> None:
    result = run_demo()

    assert result.returncode == 0, result.stderr
    assert "Personal Cognitive Garden demo" in result.stdout
    assert "2. Development class: capital_compounding" in result.stdout
    assert "strategic_product_framing" in result.stdout
    assert "LS should develop personal goal-directed cognitive gardens" in result.stdout
    assert "Strategic product framing" in result.stdout


def test_pcg_demo_runner_json_output_is_machine_readable() -> None:
    result = run_demo("--json")

    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)

    assert summary["development_class"] == "capital_compounding"
    assert "strategic_product_framing" in summary["human_skill_delta"]
    assert summary["accepted_nodes"] == [
        "LS should develop personal goal-directed cognitive gardens",
        "Strategic product framing",
    ]
