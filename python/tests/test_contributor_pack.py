from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_pack(*args: str) -> subprocess.CompletedProcess[str]:
    script = ROOT / "scripts" / "prepare_contributor_pack.py"
    return subprocess.run(
        [sys.executable, str(script), *args],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )


def test_contributor_pack_writes_issue_ready_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "pack"
    result = _run_pack("--runner", "test-runner", "--output-dir", str(output_dir))

    assert "LS Contributor Pack" in result.stdout
    expected = {
        "README.md",
        "issue_body.md",
        "network_precision_contributor_report.md",
        "network_precision_contributor_report.json",
        "pack_summary.json",
    }
    assert expected == {path.name for path in output_dir.iterdir()}

    summary = json.loads((output_dir / "pack_summary.json").read_text(encoding="utf-8"))
    assert summary["pack_version"] == "contributor_pack.v0.1"
    assert summary["runner"] == "test-runner"
    assert summary["summary"]["report_version"] == "network_precision_contributor_report.v0.2"
    assert summary["summary"]["network_precision_gain_over_baseline"] > 0

    issue_body = (output_dir / "issue_body.md").read_text(encoding="utf-8")
    assert "## Conductor Noise Robustness" in issue_body
    assert "## Live Model Pilot" in issue_body
    assert "- Runner: test-runner" in issue_body
    assert "not a model leaderboard" in issue_body


def test_contributor_pack_json_output_indexes_written_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "pack"
    result = _run_pack("--runner", "json-runner", "--output-dir", str(output_dir), "--json")
    payload = json.loads(result.stdout)

    assert payload["pack_version"] == "contributor_pack.v0.1"
    assert payload["report_version"] == "network_precision_contributor_report.v0.2"
    assert "json-runner" in payload["issue_title"]
    assert payload["summary"]["conductor_noise_decision"] == "robust_under_moderate_noise"
    assert Path(payload["files"]["issue_body.md"]).exists()
