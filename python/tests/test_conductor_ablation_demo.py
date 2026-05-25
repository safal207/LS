from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
PYTHON_ROOT = ROOT / "python"
for path in (SCRIPTS_ROOT, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_conductor_ablation_demo import build_demo_payload as build_ablation_payload  # noqa: E402
from run_network_trajectory_demo import build_demo_payload as build_trajectory_payload  # noqa: E402


def _modes(payload: dict) -> dict[str, dict]:
    return {mode["label"]: mode for mode in payload["modes"]}


def test_conductor_v02_orders_reason_ablation_modes_across_cycles() -> None:
    for cycles in (6, 10, 20):
        payload = build_ablation_payload(cycles=cycles)
        modes = _modes(payload)

        assert payload["metric_version"] == "conductor_ablation.v0.2"
        assert payload["source_metric_version"] == "network_trajectory.v0.2"
        assert payload["summary"]["decision"] == "reason_aware_conductor_supported"
        assert payload["summary"]["stale_reason_retained_share"] < 1.0

        fresh = modes["reason_aware_conductor"]
        stale = modes["stale_reason_conductor"]
        no_reason = modes["no_reason_conductor"]
        inverted = modes["inverted_reason_conductor"]

        assert fresh["end"] > stale["end"] > no_reason["end"] > inverted["end"]
        assert fresh["final_delta_vs_observer"] > stale["final_delta_vs_observer"] > 0
        assert no_reason["final_delta_vs_observer"] == 0
        assert inverted["final_delta_vs_observer"] < 0


def test_conductor_v02_policy_is_explicit_and_bounded() -> None:
    payload = build_trajectory_payload(cycles=6)
    policy = payload["conductor_policy"]
    summary = payload["summary"]

    assert payload["metric_version"] == "network_trajectory.v0.2"
    assert policy["version"] == "conductor.v0.2"
    assert policy["uses_reason_kind"] is True
    assert policy["uses_reason_delta"] is True
    assert policy["uses_reason_freshness"] is True
    assert policy["component_bounds"] == [0.0, 1.0]
    assert summary["conductor_observer_delta"] > 0
    assert summary["conductor_velocity_multiplier"] > summary["observer_velocity_multiplier"]

    for row in payload["trajectory"]:
        for value in row["with_conductor"]["components"].values():
            assert 0.0 <= value <= 1.0
