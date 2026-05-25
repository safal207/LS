from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "run_live_model_pilot.py"


def test_live_model_pilot_sample_mode_is_deterministic() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["metric_version"] == "live_model_pilot.v0.2"
    assert payload["mode"] == "sample"
    assert payload["summary"]["decision"] == "sample_pipeline_ready"
    assert payload["route_event"]["durable_state_written"] is False
    assert payload["route_event"]["external_action_allowed"] is False
    assert payload["route_event"]["event_id"].startswith("e6-")
    assert payload["network_context"]["trajectory_metric_version"] == "network_trajectory.v0.2"
    assert payload["network_context"]["conductor_policy"]["version"] == "conductor.v0.2"
    assert payload["summary"]["pilot_precision_proxy"] > 0
    assert payload["multi_actor_route"] is None
    assert payload["route_memory"]["version"] == "route_memory.v0"
    assert payload["route_memory"]["used"] is False
    assert payload["route_memory"]["durable_state_written"] is False


def test_live_model_pilot_keeps_live_opt_in() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["actor"]["live_call"] is False
    assert payload["response"]["provider"] == "sample"
    assert payload["summary"]["next_step"].startswith("Run with --live")
