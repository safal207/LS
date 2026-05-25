from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = ROOT / "scripts"
PYTHON_ROOT = ROOT / "python"
for path in (SCRIPTS_ROOT, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from run_conductor_noise_robustness_demo import build_demo_payload  # noqa: E402


def _aggregate_by_noise(payload: dict) -> dict[float, dict]:
    return {float(item["noise_level"]): item for item in payload["aggregates"]}


def test_conductor_noise_robustness_supports_moderate_noise() -> None:
    payload = build_demo_payload(cycles=6, seeds=12, noise_levels=[0.0, 0.1, 0.25, 0.4])
    by_noise = _aggregate_by_noise(payload)

    assert payload["metric_version"] == "conductor_noise_robustness.v0.1"
    assert payload["source_metric_version"] == "network_trajectory.v0.2"
    assert payload["summary"]["decision"] == "robust_under_moderate_noise"
    assert payload["summary"]["moderate_supported"] is True
    assert by_noise[0.0]["pass_rate"] == 1.0
    assert by_noise[0.1]["pass_rate"] >= 0.8
    assert by_noise[0.25]["pass_rate"] >= 0.8
    assert by_noise[0.25]["avg_fresh_minus_stale"] > 0


def test_conductor_noise_robustness_degrades_with_higher_noise() -> None:
    payload = build_demo_payload(cycles=6, seeds=12, noise_levels=[0.0, 0.25, 0.4])
    by_noise = _aggregate_by_noise(payload)

    assert payload["summary"]["high_noise_degrades"] is True
    assert by_noise[0.4]["avg_fresh_minus_stale"] <= by_noise[0.25]["avg_fresh_minus_stale"]


def test_conductor_noise_robustness_handles_high_noise_only() -> None:
    payload = build_demo_payload(cycles=6, seeds=6, noise_levels=[0.4])
    by_noise = _aggregate_by_noise(payload)

    assert payload["summary"]["decision"] == "needs_more_robustness_evidence"
    assert payload["summary"]["moderate_supported"] is False
    assert payload["summary"]["high_noise_degrades"] is False
    assert 0 <= by_noise[0.4]["pass_rate"] <= 1
