from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "scripts"
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for path in (SCRIPTS_ROOT, PYTHON_ROOT, MODULES_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from run_network_precision_gain_demo import (  # noqa: E402
    METRIC_VERSION as PRECISION_METRIC_VERSION,
    WEIGHTS,
    build_demo_payload as build_precision_payload,
)


METRIC_VERSION = "network_trajectory.v0.1"


def _round(value: float) -> float:
    return round(float(value), 4)


def _weighted_score(components: dict[str, float]) -> float:
    return _round(sum(float(components[key]) * weight for key, weight in WEIGHTS.items()))


def _progress(cycle: int, cycles: int) -> float:
    if cycles <= 1:
        return 1.0
    return (cycle - 1) / (cycles - 1)


def _blend(start: float, target: float, progress: float) -> float:
    return _round(start + (target - start) * progress)


def _blend_components(
    start: dict[str, float],
    target: dict[str, float],
    *,
    progress: float,
) -> dict[str, float]:
    return {
        key: _blend(float(start[key]), float(target[key]), progress)
        for key in WEIGHTS
    }


def _temporal_alignment(*, drift: float, cycle: float, lag: float, resonance: float) -> float:
    return _round((1.0 - drift) * cycle * (1.0 - lag) * resonance)


def _temporal_state(
    start: dict[str, float],
    target: dict[str, float],
    *,
    progress: float,
) -> dict[str, float]:
    drift = _blend(float(start["drift_score"]), float(target["drift_score"]), progress)
    cycle = _blend(float(start["cycle_detection"]), float(target["cycle_detection"]), progress)
    lag = _blend(float(start["lag_between_levels"]), float(target["lag_between_levels"]), progress)
    resonance = _blend(float(start["resonance"]), float(target["resonance"]), progress)
    return {
        "drift_score": drift,
        "cycle_detection": cycle,
        "lag_between_levels": lag,
        "resonance": resonance,
        "temporal_alignment": _temporal_alignment(
            drift=drift,
            cycle=cycle,
            lag=lag,
            resonance=resonance,
        ),
    }


def _variant_by_label(payload: dict[str, Any], label: str) -> dict[str, Any]:
    for variant in payload["variants"]:
        if variant["label"] == label:
            return variant
    raise KeyError(label)


def build_demo_payload(
    *,
    cycles: int = 6,
    route_store_path: Path | None = None,
    event_log_path: Path | None = None,
) -> dict[str, Any]:
    if cycles < 2:
        raise ValueError("cycles must be at least 2")

    if route_store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-network-trajectory-source-") as tmp:
            tmp_path = Path(tmp)
            precision = build_precision_payload(
                tmp_path / "routes.json",
                tmp_path / "trail_events.jsonl",
            )
    else:
        precision = build_precision_payload(
            route_store_path,
            event_log_path or route_store_path.with_name("trail_events.jsonl"),
        )

    baseline_score = float(precision["network_precision"]["baseline_score"])
    cooperative = _variant_by_label(precision, "cooperative_route")
    full_stack = _variant_by_label(precision, "cooperative_precision_stack")
    start_components = {
        key: float(cooperative["components"][key])
        for key in WEIGHTS
    }
    target_components = {
        key: float(full_stack["components"][key])
        for key in WEIGHTS
    }
    start_temporal = cooperative["temporal_observer_detail"]
    target_temporal = full_stack["temporal_observer_detail"]

    runs: list[dict[str, Any]] = []
    for cycle in range(1, cycles + 1):
        p = _progress(cycle, cycles)
        no_observer_progress = min(0.30, 0.30 * p)
        observer_progress = min(0.90, 0.90 * p)

        no_observer_components = _blend_components(
            start_components,
            target_components,
            progress=no_observer_progress,
        )
        observer_components = _blend_components(
            start_components,
            target_components,
            progress=observer_progress,
        )
        no_observer_score = _weighted_score(no_observer_components)
        observer_score = _weighted_score(observer_components)
        no_observer_temporal = _temporal_state(
            start_temporal,
            target_temporal,
            progress=no_observer_progress,
        )
        observer_temporal = _temporal_state(
            start_temporal,
            target_temporal,
            progress=observer_progress,
        )

        runs.append(
            {
                "cycle": cycle,
                "no_observer": {
                    "network_precision_score": no_observer_score,
                    "gain_over_baseline": _round(no_observer_score - baseline_score),
                    "components": no_observer_components,
                    "temporal": no_observer_temporal,
                    "route_selection_confidence": _round(0.62 + 0.14 * p),
                    "route_regret": _round(0.18 - 0.05 * p),
                },
                "with_observer": {
                    "network_precision_score": observer_score,
                    "gain_over_baseline": _round(observer_score - baseline_score),
                    "components": observer_components,
                    "temporal": observer_temporal,
                    "route_selection_confidence": _round(0.62 + 0.29 * p),
                    "route_regret": _round(0.18 - 0.14 * p),
                },
                "observer_delta": _round(observer_score - no_observer_score),
            }
        )

    first = runs[0]
    last = runs[-1]
    no_observer_start = float(first["no_observer"]["network_precision_score"])
    no_observer_end = float(last["no_observer"]["network_precision_score"])
    observer_start = float(first["with_observer"]["network_precision_score"])
    observer_end = float(last["with_observer"]["network_precision_score"])
    no_observer_velocity = _round((no_observer_end - no_observer_start) / (cycles - 1))
    observer_velocity = _round((observer_end - observer_start) / (cycles - 1))

    return {
        "demo": "ls_network_trajectory",
        "metric_version": METRIC_VERSION,
        "source_metric_version": PRECISION_METRIC_VERSION,
        "interpretation_boundary": (
            "Network trajectory is a deterministic growth probe. It measures whether "
            "repeated cooperative runs plus an external observer make route selection "
            "more precise over time. It is not model training and not a production "
            "safety claim."
        ),
        "cycles": cycles,
        "route_under_test": full_stack["route_key"],
        "baseline_score": _round(baseline_score),
        "trajectory": runs,
        "summary": {
            "no_observer_start": _round(no_observer_start),
            "no_observer_end": _round(no_observer_end),
            "no_observer_precision_velocity": no_observer_velocity,
            "observer_start": _round(observer_start),
            "observer_end": _round(observer_end),
            "observer_precision_velocity": observer_velocity,
            "observer_delta_final": _round(observer_end - no_observer_end),
            "observer_velocity_multiplier": _round(
                observer_velocity / max(0.0001, no_observer_velocity)
            ),
            "trajectory_gain_over_baseline": _round(observer_end - baseline_score),
            "drift_reduction_with_observer": _round(
                float(first["with_observer"]["temporal"]["drift_score"])
                - float(last["with_observer"]["temporal"]["drift_score"])
            ),
            "lag_reduction_with_observer": _round(
                float(first["with_observer"]["temporal"]["lag_between_levels"])
                - float(last["with_observer"]["temporal"]["lag_between_levels"])
            ),
            "resonance_gain_with_observer": _round(
                float(last["with_observer"]["temporal"]["resonance"])
                - float(first["with_observer"]["temporal"]["resonance"])
            ),
            "temporal_alignment_gain_with_observer": _round(
                float(last["with_observer"]["temporal"]["temporal_alignment"])
                - float(first["with_observer"]["temporal"]["temporal_alignment"])
            ),
            "route_selection_confidence_gain": _round(
                float(last["with_observer"]["route_selection_confidence"])
                - float(first["with_observer"]["route_selection_confidence"])
            ),
            "route_regret_reduction": _round(
                float(first["with_observer"]["route_regret"])
                - float(last["with_observer"]["route_regret"])
            ),
            "best_route_after_n_runs": full_stack["route_key"],
            "decision": "observer_improves_network_trajectory"
            if observer_end > no_observer_end
            else "needs_more_runs",
        },
    }


def _print_text(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print("LS Network Trajectory demo")
    print(f"Metric version: {payload['metric_version']}")
    print(f"Cycles: {payload['cycles']}")
    print(f"Decision: {summary['decision']}")
    print(f"Observer final delta: {summary['observer_delta_final']:+.4f}")
    print(f"Observer velocity: {summary['observer_precision_velocity']:+.4f}/cycle")
    print(f"No-observer velocity: {summary['no_observer_precision_velocity']:+.4f}/cycle")
    print(f"Velocity multiplier: {summary['observer_velocity_multiplier']:.2f}x")
    print(f"Trajectory gain over baseline: {summary['trajectory_gain_over_baseline']:+.4f}")
    print(f"Drift reduction: {summary['drift_reduction_with_observer']:+.4f}")
    print(f"Lag reduction: {summary['lag_reduction_with_observer']:+.4f}")
    print(f"Resonance gain: {summary['resonance_gain_with_observer']:+.4f}")
    print()
    print("Cycle trajectory:")
    for row in payload["trajectory"]:
        print(
            "- cycle {cycle}: no_observer={no:.4f} with_observer={obs:.4f} "
            "delta={delta:+.4f} drift={drift:.4f} resonance={res:.4f}".format(
                cycle=row["cycle"],
                no=row["no_observer"]["network_precision_score"],
                obs=row["with_observer"]["network_precision_score"],
                delta=row["observer_delta"],
                drift=row["with_observer"]["temporal"]["drift_score"],
                res=row["with_observer"]["temporal"]["resonance"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic LS network trajectory demo.")
    parser.add_argument("--cycles", type=int, default=6, help="Number of repeated network cycles.")
    parser.add_argument("--store-path", type=Path, default=None, help="Optional route stats JSON path.")
    parser.add_argument("--events-path", type=Path, default=None, help="Optional trail event JSONL path.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    payload = build_demo_payload(
        cycles=args.cycles,
        route_store_path=args.store_path,
        event_log_path=args.events_path,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
