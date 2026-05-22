from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_nash_route_stability_demo_marks_full_route_stable() -> None:
    script = ROOT / "scripts" / "run_nash_route_stability_demo.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["metric_version"] == "nash_route_stability.v0.1"
    assert payload["interpretation_boundary"].startswith("Nash-style route stability proxy")
    assert payload["stability"]["decision"] == "stable_candidate"
    assert payload["stability"]["nash_style_stable"] is True
    assert payload["stability"]["coalition_gain"] > 0
    assert payload["stability"]["stability_margin"] > 0
    assert payload["full_route"]["reward"] > payload["baseline_route"]["reward"]
    assert all(
        item["marginal_contribution"] > 0
        for item in payload["participant_marginal_contributions"]
    )
