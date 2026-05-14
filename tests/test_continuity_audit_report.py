from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_continuity_audit_report_renderer_smoke(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    demo_script = repo_root / "scripts" / "run_session_continuity_demo.py"
    report_script = repo_root / "scripts" / "render_continuity_audit_report.py"
    jsonl_path = tmp_path / "events.jsonl"
    report_path = tmp_path / "report.md"

    demo_result = subprocess.run(
        [sys.executable, str(demo_script), "--write-jsonl", str(jsonl_path)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert demo_result.returncode == 0, demo_result.stderr
    assert jsonl_path.exists()

    report_result = subprocess.run(
        [sys.executable, str(report_script), "--input", str(jsonl_path), "--output", str(report_path)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    assert report_result.returncode == 0, report_result.stderr
    assert report_path.exists()

    report = report_path.read_text(encoding="utf-8")
    assert "# AI Co-work Continuity Audit Report" in report
    assert "## Rupture classes" in report
    assert "`missing_pr_context`" in report
    assert "`session_type_mismatch`" in report
    assert "## Repair prompt library" in report
    assert "## Recommended gateway fields" in report
