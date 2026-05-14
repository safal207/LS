from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_route_gateway_continuity_without_remote_gateway() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "plugins" / "ls-personal-cognitive-garden" / "scripts" / "route_gateway.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--prompt",
            "continue from that PR",
            "--raw-output",
            "I will update the files now",
            "--continuity",
            "--skip-remote-gateway",
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Session continuity: ruptured" in result.stdout
    assert "Rupture type: missing_pr_context" in result.stdout
    assert "Decision: hold_until_context" in result.stdout
    assert "Repair prompt:" in result.stdout
