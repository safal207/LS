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


def test_sdk_run_returns_conductor_response() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_DIFF)
        diff_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff-file", diff_path, "--json"],
            check=True,
            capture_output=True,
            encoding="utf-8",
            text=True,
        )
        payload = json.loads(result.stdout)

        assert payload["artifact_type"] == "ls.conductor.review_pr.v0.1"
        assert "final_answer" in payload
        assert "route_id" in payload
        assert "route_score" in payload
        assert "confidence" in payload
        assert "evidence" in payload
        assert "signals" in payload
        assert "claim_boundary" in payload
    finally:
        Path(diff_path).unlink(missing_ok=True)


def test_sdk_run_returns_valid_json() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_DIFF)
        diff_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff-file", diff_path, "--json"],
            check=True,
            capture_output=True,
            encoding="utf-8",
            text=True,
        )
        payload = json.loads(result.stdout)
        assert isinstance(payload, dict)
        assert payload.get("task_type") == "pr_review"
    finally:
        Path(diff_path).unlink(missing_ok=True)


def test_sdk_run_with_output_file() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_DIFF)
        diff_path = f.name
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        out_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff-file", diff_path, "--output", out_path, "--json"],
            check=True,
            capture_output=True,
            encoding="utf-8",
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["artifact_path"] is not None

        saved = json.loads(Path(out_path).read_text(encoding="utf-8"))
        assert saved["artifact_path"] is not None
    finally:
        Path(diff_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)


def test_sdk_compare_requires_two_candidates() -> None:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".diff", delete=False, encoding="utf-8") as f:
        f.write(SAMPLE_DIFF)
        diff_path = f.name
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--diff-file", diff_path, "--json"],
            check=True,
            capture_output=True,
            encoding="utf-8",
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["route_won_vs_single"] is True or payload["route_won_vs_single"] is False
    finally:
        Path(diff_path).unlink(missing_ok=True)
