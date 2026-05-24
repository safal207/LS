from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_depth_economy_demo_routes_depth_by_pressure() -> None:
    script = ROOT / "scripts" / "run_depth_economy_demo.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    payload = json.loads(result.stdout)
    evaluations = {item["scenario_id"]: item for item in payload["evaluations"]}

    assert payload["metric_version"] == "depth_economy.v0.1"
    assert evaluations["low_risk_fix"]["selected_depth"]["level"] == 1
    assert evaluations["low_risk_fix"]["interaction_math"] == "1+1=2"
    assert evaluations["product_route_design"]["selected_depth"]["level"] >= 2
    assert evaluations["product_route_design"]["interaction_math"] in {"1+1=3", "1+1=n"}
    assert evaluations["high_stakes_memory_or_action"]["selected_depth"]["level"] == 4
    assert evaluations["high_stakes_memory_or_action"]["interaction_math"] == "1+1=n"
    assert evaluations["high_stakes_memory_or_action"]["decision"] == "hold_until_human_review"
    assert "human_review" in evaluations["high_stakes_memory_or_action"]["required_roles"]
