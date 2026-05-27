from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "ls_conductor_review_pr.py"


SAMPLE_DIFF = """\
diff --git a/scripts/example.py b/scripts/example.py
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/scripts/example.py
@@ -0,0 +1,2 @@
+def demo():
+    return "ok"
"""


def _run(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)] + list(args)
    return subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
        input=input_text,
    )


def test_conductor_review_pr_json_shape_from_diff_file() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_DIFF)
        diff_path = f.name
    try:
        result = _run("--diff-file", diff_path, "--json")
        payload = json.loads(result.stdout)

        assert payload["artifact_type"] == "ls.conductor.review_pr.v0.1"
        assert payload["conductor_version"] == "v0.1"
        assert payload["task_type"] == "pr_review"
        assert payload["policy"] == "cooperative_pr_review"
        assert "claim_boundary" in payload
        assert "not a formal proof" in payload["claim_boundary"]
        assert "final_answer" in payload
        assert "route_id" in payload
        assert "route_score" in payload
        assert "confidence" in payload
        assert "route_won_vs_single" in payload
        assert "evidence" in payload
        assert isinstance(payload["evidence"], list)
        assert "decision" in payload
        assert "latency_ms" in payload
        assert payload["latency_ms"] >= 0
    finally:
        Path(diff_path).unlink(missing_ok=True)


def test_conductor_review_pr_route_won_vs_single_is_boolean() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_DIFF)
        diff_path = f.name
    try:
        result = _run("--diff-file", diff_path, "--json")
        payload = json.loads(result.stdout)
        assert isinstance(payload["route_won_vs_single"], bool)
    finally:
        Path(diff_path).unlink(missing_ok=True)


def test_conductor_review_pr_human_output() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_DIFF)
        diff_path = f.name
    try:
        result = _run("--diff-file", diff_path)
        output = result.stdout

        assert "LS Conductor PR Review" in output
        assert "Policy:" in output
        assert "Decision:" in output
        assert "Route:" in output
    finally:
        Path(diff_path).unlink(missing_ok=True)
