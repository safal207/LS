from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_model_roster_depth_probe_lists_existing_ls_actors() -> None:
    script = ROOT / "scripts" / "run_model_roster_depth_probe.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    payload = json.loads(result.stdout)
    actor_ids = {item["actor_id"] for item in payload["roster"]}
    assignments = {item["role"]: item["actor_id"] for item in payload["role_actor_assignments"]}

    assert payload["metric_version"] == "model_roster_depth_probe.v0.1"
    assert payload["live_probe"]["enabled"] is False
    assert {
        "codex-self-use",
        "local-qwen",
        "local-qwen-light",
        "gonka",
        "mimo",
        "human_operator",
    }.issubset(actor_ids)
    assert assignments["risk_critic"] == "gonka"
    assert assignments["final_reviewer"] == "mimo"
    assert assignments["evidence_verifier"] == "local-qwen-light"


def test_model_roster_depth_probe_keeps_live_call_opt_in() -> None:
    script = ROOT / "scripts" / "run_model_roster_depth_probe.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["live_probe"]["reason"] == "pass --live to call the configured LLM route"
    assert "backend_status" in payload["configured_route"]
