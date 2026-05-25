from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


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

from run_network_trajectory_demo import (  # noqa: E402
    METRIC_VERSION as TRAJECTORY_METRIC_VERSION,
    _conductor_adjust,
    _round,
    _weighted_score,
    build_demo_payload as build_trajectory_payload,
)


METRIC_VERSION = "conductor_ablation.v0.2"
ReasonSelector = Callable[[list[dict[str, Any]], int], list[dict[str, Any]]]


def _mode_trajectory(
    source: dict[str, Any],
    *,
    label: str,
    reason_selector: ReasonSelector,
    direction: float,
) -> dict[str, Any]:
    rows = []
    source_rows = source["trajectory"]
    for index, row in enumerate(source_rows):
        observer = row["with_observer"]
        reasons = reason_selector(source_rows, index)
        components = _conductor_adjust(
            observer["components"],
            reasons,
            current_cycle=int(row["cycle"]),
            direction=direction,
        )
        score = _weighted_score(components)
        rows.append(
            {
                "cycle": row["cycle"],
                "network_precision_score": score,
                "delta_vs_observer": _round(score - float(observer["network_precision_score"])),
                "reason_count": len(reasons),
                "reason_kinds": sorted({reason["kind"] for reason in reasons}),
            }
        )

    start = float(rows[0]["network_precision_score"])
    end = float(rows[-1]["network_precision_score"])
    observer_end = float(source_rows[-1]["with_observer"]["network_precision_score"])
    no_observer_velocity = float(source["summary"]["no_observer_precision_velocity"])
    velocity = _round((end - start) / max(1, len(rows) - 1))
    return {
        "label": label,
        "start": _round(start),
        "end": _round(end),
        "precision_velocity": velocity,
        "velocity_multiplier": _round(velocity / max(0.0001, no_observer_velocity)),
        "final_delta_vs_observer": _round(end - observer_end),
        "rows": rows,
    }


def _current_reasons(rows: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    return list(rows[index].get("reasons", []))


def _no_reasons(rows: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    return []


def _previous_cycle_reasons(rows: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    if index == 0:
        return []
    return list(rows[index - 1].get("reasons", []))


def build_demo_payload(*, cycles: int = 6) -> dict[str, Any]:
    source = build_trajectory_payload(cycles=cycles)
    modes = [
        _mode_trajectory(
            source,
            label="reason_aware_conductor",
            reason_selector=_current_reasons,
            direction=1.0,
        ),
        _mode_trajectory(
            source,
            label="no_reason_conductor",
            reason_selector=_no_reasons,
            direction=1.0,
        ),
        _mode_trajectory(
            source,
            label="stale_reason_conductor",
            reason_selector=_previous_cycle_reasons,
            direction=1.0,
        ),
        _mode_trajectory(
            source,
            label="inverted_reason_conductor",
            reason_selector=_current_reasons,
            direction=-1.0,
        ),
    ]
    by_label = {mode["label"]: mode for mode in modes}
    reason_gain = float(by_label["reason_aware_conductor"]["final_delta_vs_observer"])
    no_reason_gain = float(by_label["no_reason_conductor"]["final_delta_vs_observer"])
    stale_gain = float(by_label["stale_reason_conductor"]["final_delta_vs_observer"])
    inverted_gain = float(by_label["inverted_reason_conductor"]["final_delta_vs_observer"])

    supported = (
        reason_gain > no_reason_gain
        and reason_gain > stale_gain
        and no_reason_gain >= inverted_gain
    )
    return {
        "demo": "ls_conductor_ablation",
        "metric_version": METRIC_VERSION,
        "source_metric_version": TRAJECTORY_METRIC_VERSION,
        "interpretation_boundary": (
            "This is a deterministic ablation probe. It checks whether the conductor "
            "depends on causal reasons, not whether live models learned or whether the "
            "system is production safe."
        ),
        "cycles": cycles,
        "baseline": {
            "no_observer_end": source["summary"]["no_observer_end"],
            "observer_end": source["summary"]["observer_end"],
            "reference_conductor_end": source["summary"]["conductor_end"],
        },
        "modes": modes,
        "summary": {
            "decision": "reason_aware_conductor_supported"
            if supported
            else "conductor_requires_more_evidence",
            "reason_specific_gain": _round(reason_gain - no_reason_gain),
            "stale_reason_retained_share": _round(
                stale_gain / max(0.0001, reason_gain)
            ),
            "inverted_reason_penalty": _round(no_reason_gain - inverted_gain),
            "falsification_rule": (
                "If no_reason, stale_reason, or inverted_reason matches or exceeds "
                "reason_aware_conductor, the reason-aware hypothesis is not supported."
            ),
        },
    }


def _print_text(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print("LS Conductor ablation demo")
    print(f"Metric version: {payload['metric_version']}")
    print(f"Cycles: {payload['cycles']}")
    print(f"Decision: {summary['decision']}")
    print()
    print("Mode comparison:")
    for mode in payload["modes"]:
        print(
            "- {label}: end={end:.4f} velocity={velocity:+.4f}/cycle "
            "multiplier={multiplier:.2f}x delta_vs_observer={delta:+.4f}".format(
                label=mode["label"],
                end=mode["end"],
                velocity=mode["precision_velocity"],
                multiplier=mode["velocity_multiplier"],
                delta=mode["final_delta_vs_observer"],
            )
        )
    print()
    print(f"Reason-specific gain: {summary['reason_specific_gain']:+.4f}")
    print(f"Stale reason retained share: {summary['stale_reason_retained_share']:.2f}")
    print(f"Inverted reason penalty: {summary['inverted_reason_penalty']:+.4f}")
    print(f"Falsification rule: {summary['falsification_rule']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LS conductor reason ablations.")
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_demo_payload(cycles=args.cycles)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
