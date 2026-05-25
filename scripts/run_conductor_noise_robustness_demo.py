from __future__ import annotations

import argparse
import json
import random
import sys
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

from run_network_trajectory_demo import (  # noqa: E402
    CONDUCTOR_DELTAS,
    METRIC_VERSION as TRAJECTORY_METRIC_VERSION,
    _conductor_adjust,
    _round,
    _weighted_score,
    build_demo_payload as build_trajectory_payload,
)


METRIC_VERSION = "conductor_noise_robustness.v0.1"
DEFAULT_NOISE_LEVELS = [0.0, 0.10, 0.25, 0.40]
DEFAULT_SEEDS = 12
MODERATE_NOISE_CEILING = 0.25


def _parse_noise_levels(raw: str) -> list[float]:
    levels = [_round(float(item.strip())) for item in raw.split(",") if item.strip()]
    if not levels:
        raise ValueError("at least one noise level is required")
    if any(level < 0 or level > 1 for level in levels):
        raise ValueError("noise levels must be between 0.0 and 1.0")
    return levels


def _noisy_reasons(
    reasons: list[dict[str, Any]],
    *,
    rng: random.Random,
    noise_level: float,
) -> list[dict[str, Any]]:
    if noise_level <= 0:
        return [dict(reason) for reason in reasons]

    noisy: list[dict[str, Any]] = []
    reason_kinds = sorted(CONDUCTOR_DELTAS)
    drop_probability = min(0.35, noise_level * 0.35)
    mislabel_probability = min(0.25, noise_level * 0.25)

    for reason in reasons:
        if rng.random() < drop_probability:
            continue
        mutated = dict(reason)
        if rng.random() < mislabel_probability:
            mutated["kind"] = rng.choice(reason_kinds)
        delta = abs(float(mutated.get("delta", 0.0)))
        # Measurement noise changes signal strength but keeps it non-negative:
        # the probe is about noisy causal evidence, not adversarial sign flips.
        delta *= max(0.0, 1.0 + rng.uniform(-noise_level, noise_level))
        mutated["delta"] = _round(delta)
        mutated["noise_level"] = noise_level
        noisy.append(mutated)
    return noisy


def _mode_score(
    source_rows: list[dict[str, Any]],
    *,
    noisy_reasons_by_index: list[list[dict[str, Any]]],
    label: str,
    selector: str,
    direction: float,
) -> dict[str, Any]:
    rows = []
    for index, row in enumerate(source_rows):
        observer = row["with_observer"]
        if selector == "fresh":
            reasons = noisy_reasons_by_index[index]
        elif selector == "stale":
            reasons = noisy_reasons_by_index[index - 1] if index > 0 else []
        elif selector == "none":
            reasons = []
        else:
            raise ValueError(f"unknown selector: {selector}")

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
            }
        )

    start = float(rows[0]["network_precision_score"])
    end = float(rows[-1]["network_precision_score"])
    observer_end = float(source_rows[-1]["with_observer"]["network_precision_score"])
    return {
        "label": label,
        "start": _round(start),
        "end": _round(end),
        "final_delta_vs_observer": _round(end - observer_end),
        "rows": rows,
    }


def _sample(
    source: dict[str, Any],
    *,
    seed: int,
    noise_level: float,
) -> dict[str, Any]:
    rng = random.Random(seed)
    source_rows = source["trajectory"]
    noisy_reasons = [
        _noisy_reasons(
            row.get("reasons", []),
            rng=rng,
            noise_level=noise_level,
        )
        for row in source_rows
    ]
    modes = [
        _mode_score(
            source_rows,
            noisy_reasons_by_index=noisy_reasons,
            label="fresh_noisy_reason_conductor",
            selector="fresh",
            direction=1.0,
        ),
        _mode_score(
            source_rows,
            noisy_reasons_by_index=noisy_reasons,
            label="stale_noisy_reason_conductor",
            selector="stale",
            direction=1.0,
        ),
        _mode_score(
            source_rows,
            noisy_reasons_by_index=noisy_reasons,
            label="no_reason_conductor",
            selector="none",
            direction=1.0,
        ),
        _mode_score(
            source_rows,
            noisy_reasons_by_index=noisy_reasons,
            label="inverted_noisy_reason_conductor",
            selector="fresh",
            direction=-1.0,
        ),
    ]
    by_label = {mode["label"]: mode for mode in modes}
    fresh = by_label["fresh_noisy_reason_conductor"]
    stale = by_label["stale_noisy_reason_conductor"]
    no_reason = by_label["no_reason_conductor"]
    inverted = by_label["inverted_noisy_reason_conductor"]
    fresh_gain = float(fresh["final_delta_vs_observer"])
    stale_gain = float(stale["final_delta_vs_observer"])
    no_reason_gain = float(no_reason["final_delta_vs_observer"])
    inverted_gain = float(inverted["final_delta_vs_observer"])
    supported = (
        fresh_gain > stale_gain > no_reason_gain > inverted_gain
    )
    return {
        "seed": seed,
        "noise_level": noise_level,
        "supported": supported,
        "fresh_minus_stale": _round(fresh_gain - stale_gain),
        "fresh_gain": _round(fresh_gain),
        "stale_gain": _round(stale_gain),
        "inverted_penalty": _round(no_reason_gain - inverted_gain),
        "modes": modes,
    }


def _aggregate(samples: list[dict[str, Any]], *, noise_level: float) -> dict[str, Any]:
    count = len(samples)
    if count == 0:
        raise ValueError("cannot aggregate empty samples")

    pass_count = sum(1 for sample in samples if sample["supported"])
    avg_fresh_minus_stale = _round(
        sum(float(sample["fresh_minus_stale"]) for sample in samples) / count
    )
    avg_fresh_gain = _round(sum(float(sample["fresh_gain"]) for sample in samples) / count)
    avg_stale_gain = _round(sum(float(sample["stale_gain"]) for sample in samples) / count)
    avg_inverted_penalty = _round(
        sum(float(sample["inverted_penalty"]) for sample in samples) / count
    )
    return {
        "noise_level": noise_level,
        "samples": count,
        "pass_count": pass_count,
        "pass_rate": _round(pass_count / count),
        "avg_fresh_minus_stale": avg_fresh_minus_stale,
        "avg_fresh_gain": avg_fresh_gain,
        "avg_stale_gain": avg_stale_gain,
        "avg_inverted_penalty": avg_inverted_penalty,
    }


def build_demo_payload(
    *,
    cycles: int = 6,
    seeds: int = DEFAULT_SEEDS,
    noise_levels: list[float] | None = None,
) -> dict[str, Any]:
    if seeds < 1:
        raise ValueError("seeds must be at least 1")
    if cycles < 2:
        raise ValueError("cycles must be at least 2")

    levels = noise_levels or DEFAULT_NOISE_LEVELS
    source = build_trajectory_payload(cycles=cycles)
    all_samples: list[dict[str, Any]] = []
    aggregates = []
    for noise_level in levels:
        level_samples = [
            _sample(source, seed=seed, noise_level=noise_level)
            for seed in range(1, seeds + 1)
        ]
        all_samples.extend(level_samples)
        aggregates.append(_aggregate(level_samples, noise_level=noise_level))

    moderate = [
        item for item in aggregates
        if float(item["noise_level"]) <= MODERATE_NOISE_CEILING
    ]
    moderate_supported = bool(moderate) and all(
        float(item["pass_rate"]) >= 0.80 and float(item["avg_fresh_minus_stale"]) > 0
        for item in moderate
    )
    high_noise = [
        item for item in aggregates
        if float(item["noise_level"]) > MODERATE_NOISE_CEILING
    ]
    high_noise_degrades = bool(moderate) and bool(high_noise) and any(
        float(item["pass_rate"]) < float(moderate[0]["pass_rate"])
        or float(item["avg_fresh_minus_stale"]) < float(moderate[-1]["avg_fresh_minus_stale"])
        for item in high_noise
    )

    return {
        "demo": "ls_conductor_noise_robustness",
        "metric_version": METRIC_VERSION,
        "source_metric_version": TRAJECTORY_METRIC_VERSION,
        "interpretation_boundary": (
            "This is a deterministic robustness probe over synthetic noise and seeds. "
            "It does not prove live model learning or production safety."
        ),
        "cycles": cycles,
        "seeds": seeds,
        "noise_levels": levels,
        "aggregates": aggregates,
        "samples": all_samples,
        "summary": {
            "decision": "robust_under_moderate_noise"
            if moderate_supported
            else "needs_more_robustness_evidence",
            "moderate_noise_ceiling": MODERATE_NOISE_CEILING,
            "moderate_supported": moderate_supported,
            "high_noise_degrades": high_noise_degrades,
            "ordering_under_test": (
                "fresh noisy reasons > stale noisy reasons > no reasons > inverted noisy reasons"
            ),
        },
    }


def _print_text(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    print("LS Conductor noise robustness demo")
    print(f"Metric version: {payload['metric_version']}")
    print(f"Cycles: {payload['cycles']}")
    print(f"Seeds: {payload['seeds']}")
    print(f"Decision: {summary['decision']}")
    print(f"Ordering: {summary['ordering_under_test']}")
    print()
    print("Noise levels:")
    for item in payload["aggregates"]:
        print(
            "- noise={noise:.2f}: pass_rate={rate:.2f} "
            "fresh-stale={delta:+.4f} fresh_gain={fresh:+.4f} "
            "stale_gain={stale:+.4f} inverted_penalty={penalty:+.4f}".format(
                noise=item["noise_level"],
                rate=item["pass_rate"],
                delta=item["avg_fresh_minus_stale"],
                fresh=item["avg_fresh_gain"],
                stale=item["avg_stale_gain"],
                penalty=item["avg_inverted_penalty"],
            )
        )
    print()
    print(f"Moderate supported: {summary['moderate_supported']}")
    print(f"High noise degrades: {summary['high_noise_degrades']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run LS conductor noise robustness demo.")
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--seeds", type=int, default=DEFAULT_SEEDS)
    parser.add_argument(
        "--noise-levels",
        default=",".join(str(level) for level in DEFAULT_NOISE_LEVELS),
        help="Comma-separated noise levels between 0.0 and 1.0.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = build_demo_payload(
        cycles=args.cycles,
        seeds=args.seeds,
        noise_levels=_parse_noise_levels(args.noise_levels),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
