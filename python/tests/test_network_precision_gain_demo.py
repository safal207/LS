from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _run_demo_payload() -> dict:
    script = ROOT / "scripts" / "run_network_precision_gain_demo.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    return json.loads(result.stdout)


def test_network_precision_gain_orders_baseline_cooperation_and_stack() -> None:
    payload = _run_demo_payload()
    variants = {item["label"]: item for item in payload["variants"]}
    precision = payload["network_precision"]

    assert payload["metric_version"] == "network_precision_gain.v0.1"
    assert payload["demo"] == "ls_network_precision_gain"
    assert payload["measured_route_reward_gain"] > 0
    assert variants["cooperative_route"]["network_precision_score"] > variants[
        "single_answer_baseline"
    ]["network_precision_score"]
    assert variants["cooperative_precision_stack"]["network_precision_score"] > variants[
        "cooperative_route"
    ]["network_precision_score"]
    assert precision["network_precision_gain_over_baseline"] > 0
    assert precision["stack_added_gain_over_cooperation"] > 0
    assert precision["decision"] == "use_stack_for_repeatable_routes"


def test_network_precision_gain_includes_six_path_stack_roles() -> None:
    payload = _run_demo_payload()
    roles = {item["role"] for item in payload["six_paths"]}

    assert roles == {
        "immutable_trace",
        "adaptive_living_memory",
        "evidence_action_gate",
        "cooperative_route_scoring",
        "reflective_interpretation",
        "goal_consent_meaning",
    }
    assert set(payload["weights"]) == {
        "route_reward",
        "evidence_gate",
        "trace_integrity",
        "adaptive_memory",
        "reflective_clarity",
        "human_boundary",
        "depth_fit",
    }
