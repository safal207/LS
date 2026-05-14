from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_session_continuity_demo_smoke() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "run_session_continuity_demo.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "LS Session Continuity Demo" in result.stdout
    assert "Rupture type: missing_pr_context" in result.stdout
    assert "Decision: hold_until_context" in result.stdout
    assert "Rupture type: session_type_mismatch" in result.stdout
    assert "Decision: repair_before_continue" in result.stdout
    assert "Rupture type: none" in result.stdout
    assert "Decision: continue" in result.stdout
