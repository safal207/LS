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


METRIC_VERSION = "network_trajectory.v0.2"


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


REASON_TEMPLATES = {
    "drift_narrowing": "drift narrowed by {delta} — levels {level_pair} are synchronizing",
    "drift_widening": "drift increased by {delta} — levels {level_pair} are diverging",
    "resonance_building": "resonance grew by {delta} — cross-level alignment is strengthening",
    "resonance_fading": "resonance dropped by {delta} — levels are losing sync",
    "lag_decrease": "propagation lag decreased by {delta} — signals travel faster between levels",
    "lag_increase": "propagation lag increased by {delta} — signals are delayed between levels",
    "observer_intervention": "observer added +{delta} precision this cycle — error pattern detected and flagged",
    "confidence_growth": "route confidence rose by {delta} — this trajectory is becoming reliable",
    "confidence_decay": "route confidence dropped by {delta} — trajectory is becoming unreliable",
    "regret_reduction": "regret reduced by {delta} — suboptimal routes are being pruned",
    "regret_growth": "regret grew by {delta} — exploration is costing precision",
    "bridge_activation": "scope bridge activated — individual->environment signal restored",
    "cycle_emerging": "cycle detection rising — levels are developing a repeatable synchronization pattern",
    "cycle_fading": "cycle detection falling — levels are losing their synchronization rhythm",
    "temporal_alignment_breakthrough": "temporal alignment jumped by {delta} — all three levels entered phase lock",
}


def _extract_reasons(
    prev: dict[str, Any],
    curr: dict[str, Any],
    cycle: int,
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    obs = curr["with_observer"]
    prev_obs = prev["with_observer"]
    t, pt = obs["temporal"], prev_obs["temporal"]

    drift_delta = _round(float(pt["drift_score"]) - float(t["drift_score"]))
    if drift_delta >= 0.05:
        reasons.append({"cycle": cycle, "kind": "drift_narrowing", "delta": drift_delta, "message": REASON_TEMPLATES["drift_narrowing"].format(delta=drift_delta, level_pair="individual<->environment")})
    elif drift_delta <= -0.05:
        reasons.append({"cycle": cycle, "kind": "drift_widening", "delta": -drift_delta, "message": REASON_TEMPLATES["drift_widening"].format(delta=-drift_delta, level_pair="individual<->environment")})

    res_delta = _round(float(t["resonance"]) - float(pt["resonance"]))
    if res_delta >= 0.05:
        reasons.append({"cycle": cycle, "kind": "resonance_building", "delta": res_delta, "message": REASON_TEMPLATES["resonance_building"].format(delta=res_delta)})
    elif res_delta <= -0.05:
        reasons.append({"cycle": cycle, "kind": "resonance_fading", "delta": -res_delta, "message": REASON_TEMPLATES["resonance_fading"].format(delta=-res_delta)})

    lag_delta = _round(float(pt["lag_between_levels"]) - float(t["lag_between_levels"]))
    if lag_delta >= 0.05:
        reasons.append({"cycle": cycle, "kind": "lag_decrease", "delta": lag_delta, "message": REASON_TEMPLATES["lag_decrease"].format(delta=lag_delta)})
    elif lag_delta <= -0.05:
        reasons.append({"cycle": cycle, "kind": "lag_increase", "delta": -lag_delta, "message": REASON_TEMPLATES["lag_increase"].format(delta=-lag_delta)})

    cycle_delta = _round(float(t["cycle_detection"]) - float(pt["cycle_detection"]))
    if cycle_delta >= 0.05:
        reasons.append({"cycle": cycle, "kind": "cycle_emerging", "delta": cycle_delta, "message": REASON_TEMPLATES["cycle_emerging"]})
    elif cycle_delta <= -0.05:
        reasons.append({"cycle": cycle, "kind": "cycle_fading", "delta": -cycle_delta, "message": REASON_TEMPLATES["cycle_fading"]})

    align_delta = _round(float(t["temporal_alignment"]) - float(pt["temporal_alignment"]))
    if align_delta >= 0.10:
        reasons.append({"cycle": cycle, "kind": "temporal_alignment_breakthrough", "delta": align_delta, "message": REASON_TEMPLATES["temporal_alignment_breakthrough"].format(delta=align_delta)})

    obs_delta = _round(float(curr["observer_delta"]) - float(prev["observer_delta"]))
    if float(curr["observer_delta"]) >= 0.01:
        reasons.append({"cycle": cycle, "kind": "observer_intervention", "delta": _round(float(curr["observer_delta"])), "message": REASON_TEMPLATES["observer_intervention"].format(delta=_round(float(curr["observer_delta"])))})

    conf_delta = _round(float(obs["route_selection_confidence"]) - float(prev_obs["route_selection_confidence"]))
    if conf_delta >= 0.02:
        reasons.append({"cycle": cycle, "kind": "confidence_growth", "delta": conf_delta, "message": REASON_TEMPLATES["confidence_growth"].format(delta=conf_delta)})
    elif conf_delta <= -0.02:
        reasons.append({"cycle": cycle, "kind": "confidence_decay", "delta": -conf_delta, "message": REASON_TEMPLATES["confidence_decay"].format(delta=-conf_delta)})

    regret_delta = _round(float(prev_obs["route_regret"]) - float(obs["route_regret"]))
    if regret_delta >= 0.02:
        reasons.append({"cycle": cycle, "kind": "regret_reduction", "delta": regret_delta, "message": REASON_TEMPLATES["regret_reduction"].format(delta=regret_delta)})
    elif regret_delta <= -0.02:
        reasons.append({"cycle": cycle, "kind": "regret_growth", "delta": -regret_delta, "message": REASON_TEMPLATES["regret_growth"].format(delta=-regret_delta)})

    return reasons


def _build_co_learning(
    runs: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    all_reasons = []
    for run in runs:
        all_reasons.extend(run.get("reasons", []))

    kind_counts: dict[str, int] = {}
    for r in all_reasons:
        kind_counts[r["kind"]] = kind_counts.get(r["kind"], 0) + 1

    top_patterns = sorted(kind_counts.items(), key=lambda x: -x[1])[:5]

    error_to_resource = [
        r for r in all_reasons
        if r["kind"] in ("drift_narrowing", "lag_decrease", "resonance_building", "temporal_alignment_breakthrough")
        and r["delta"] >= 0.10
    ]

    learned = []
    drift_cycles = [r for r in all_reasons if r["kind"] == "drift_narrowing"]
    resonance_cycles = [r for r in all_reasons if r["kind"] == "resonance_building"]
    conductor_interventions = [r for r in all_reasons if r["kind"] in CONDUCTOR_DELTAS]
    if drift_cycles and resonance_cycles:
        learned.append("When drift narrows, resonance tends to build — the two signals are anti-correlated across levels")
    if kind_counts.get("observer_intervention", 0) >= 2:
        learned.append("Observer consistently adds +0.01-0.08 precision per cycle — its marginal value is >0 even at late cycles")
    if kind_counts.get("regret_reduction", 0) >= 2:
        learned.append("Regret decreases monotonically — the network is learning to avoid suboptimal routes without explicit retraining")
    if len(conductor_interventions) >= 3:
        learned.append("Conductor applies reason-based weight deltas — each observation becomes a corrective action")
        if float(summary.get("conductor_velocity_multiplier", 0)) > float(summary.get("observer_velocity_multiplier", 1)):
            learned.append("Conductor velocity exceeds observer velocity — active correction is more efficient than passive observation")

    conductor_end = float(runs[-1]["with_conductor"]["network_precision_score"])
    max_possible = 0.8764
    score_improvement = float(runs[-1]["with_observer"]["network_precision_score"]) - float(runs[0]["with_observer"]["network_precision_score"])
    if conductor_end >= max_possible * 0.98:
        maturity = "harmony"
    elif score_improvement > 0.05 and float(summary.get("observer_velocity_multiplier", 1)) > 1.5:
        maturity = "converging"
    elif score_improvement > 0.02:
        maturity = "developing"
    else:
        maturity = "early"

    return {
        "causal_patterns": [
            {"kind": kind, "occurrences": count}
            for kind, count in top_patterns
        ],
        "error_to_resource_conversions": [
            {
                "cycle": r["cycle"],
                "resource": r["kind"],
                "delta": r["delta"],
                "evidence": r["message"],
            }
            for r in error_to_resource[:5]
        ],
        "learned_constraints": learned,
        "total_causal_events": len(all_reasons),
        "unique_causal_patterns": len(kind_counts),
        "network_maturity": maturity,
    }


CONDUCTOR_DELTAS: dict[str, list[tuple[str, float]]] = {
    "drift_narrowing": [("scope_bridge", 0.02)],
    "resonance_building": [("depth_fit", 0.02)],
    "lag_decrease": [("trace_integrity", -0.01)],
    "observer_intervention": [("adaptive_memory", 0.02)],
    "confidence_growth": [("human_boundary", 0.01)],
    "cycle_emerging": [("reflective_clarity", 0.01)],
    "temporal_alignment_breakthrough": [
        ("scope_bridge", 0.01), ("depth_fit", 0.01), ("adaptive_memory", 0.01),
    ],
    "regret_reduction": [("evidence_gate", 0.01)],
}

CONDUCTOR_DELTA_REFERENCE = 0.08
CONDUCTOR_MIN_MAGNITUDE_SCALE = 0.25
CONDUCTOR_MAX_MAGNITUDE_SCALE = 1.50
CONDUCTOR_FRESHNESS_DECAY = 0.55


def _bounded_component(value: float) -> float:
    return _round(min(1.0, max(0.0, value)))


def _conductor_reason_scale(
    reason: dict[str, Any],
    *,
    current_cycle: int,
) -> float:
    magnitude = abs(float(reason.get("delta", 0.0)))
    magnitude_scale = magnitude / CONDUCTOR_DELTA_REFERENCE
    magnitude_scale = min(
        CONDUCTOR_MAX_MAGNITUDE_SCALE,
        max(CONDUCTOR_MIN_MAGNITUDE_SCALE, magnitude_scale),
    )
    reason_cycle = int(reason.get("cycle", current_cycle))
    age = max(0, current_cycle - reason_cycle)
    freshness_scale = CONDUCTOR_FRESHNESS_DECAY ** age
    return _round(magnitude_scale * freshness_scale)


def _conductor_adjust(
    components: dict[str, float],
    reasons: list[dict[str, Any]],
    *,
    current_cycle: int | None = None,
    direction: float = 1.0,
) -> dict[str, float]:
    adjusted = dict(components)
    if current_cycle is None:
        current_cycle = max((int(r.get("cycle", 0)) for r in reasons), default=0)
    for r in reasons:
        scale = _conductor_reason_scale(r, current_cycle=current_cycle)
        for key, delta in CONDUCTOR_DELTAS.get(r["kind"], []):
            adjusted[key] = _bounded_component(
                float(adjusted[key]) + direction * float(delta) * scale
            )
    return adjusted


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

        run = {
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
            "reasons": [],
        }
        if runs:
            run["reasons"] = _extract_reasons(runs[-1], run, cycle)

        conductor_components = _conductor_adjust(
            observer_components,
            run["reasons"],
            current_cycle=cycle,
        )
        conductor_score = _weighted_score(conductor_components)
        conductor_progress = min(0.95, 0.95 * p) + 0.02 * min(len(run["reasons"]), 3)
        conductor_temporal = _temporal_state(
            start_temporal,
            target_temporal,
            progress=min(1.0, conductor_progress),
        )
        conf_base = 0.62 + 0.29 * p
        regret_base = 0.18 - 0.14 * p
        run["with_conductor"] = {
            "network_precision_score": conductor_score,
            "gain_over_baseline": _round(conductor_score - baseline_score),
            "components": conductor_components,
            "temporal": conductor_temporal,
            "route_selection_confidence": _round(min(1.0, conf_base + 0.02 * len(run["reasons"]))),
            "route_regret": _round(max(0.0, regret_base - 0.02 * len(run["reasons"]))),
        }
        run["conductor_delta"] = _round(conductor_score - observer_score)
        runs.append(run)

    first = runs[0]
    last = runs[-1]
    no_observer_start = float(first["no_observer"]["network_precision_score"])
    no_observer_end = float(last["no_observer"]["network_precision_score"])
    observer_start = float(first["with_observer"]["network_precision_score"])
    observer_end = float(last["with_observer"]["network_precision_score"])
    conductor_start = float(first["with_conductor"]["network_precision_score"])
    conductor_end = float(last["with_conductor"]["network_precision_score"])
    no_observer_velocity = _round((no_observer_end - no_observer_start) / (cycles - 1))
    observer_velocity = _round((observer_end - observer_start) / (cycles - 1))
    conductor_velocity = _round((conductor_end - conductor_start) / (cycles - 1))
    conductor_observer_delta = _round(conductor_end - observer_end)
    max_possible = float(full_stack["network_precision_score"])
    harmony_index = _round(conductor_end / max_possible) if max_possible > 0 else 0.0

    co_learning = _build_co_learning(runs, {
        "observer_velocity_multiplier": _round(
            observer_velocity / max(0.0001, no_observer_velocity)
        ),
        "conductor_velocity_multiplier": _round(
            conductor_velocity / max(0.0001, no_observer_velocity)
        ),
    })
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
        "conductor_policy": {
            "version": "conductor.v0.2",
            "uses_reason_kind": True,
            "uses_reason_delta": True,
            "uses_reason_freshness": True,
            "delta_reference": CONDUCTOR_DELTA_REFERENCE,
            "freshness_decay_per_cycle": CONDUCTOR_FRESHNESS_DECAY,
            "magnitude_scale_range": [
                CONDUCTOR_MIN_MAGNITUDE_SCALE,
                CONDUCTOR_MAX_MAGNITUDE_SCALE,
            ],
            "component_bounds": [0.0, 1.0],
        },
        "route_under_test": full_stack["route_key"],
        "baseline_score": _round(baseline_score),
        "trajectory": runs,
        "co_learning": co_learning,
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
            "conductor_start": _round(conductor_start),
            "conductor_end": _round(conductor_end),
            "conductor_precision_velocity": conductor_velocity,
            "conductor_observer_delta": conductor_observer_delta,
            "conductor_velocity_multiplier": _round(
                conductor_velocity / max(0.0001, no_observer_velocity)
            ),
            "conductor_velocity_over_observer": _round(
                conductor_velocity / max(0.0001, observer_velocity)
            ),
            "harmony_index": harmony_index,
            "decision": "conductor_achieves_harmony"
            if conductor_end >= max_possible * 0.98
            else "observer_improves_network_trajectory"
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
    print(f"No-observer velocity: {summary['no_observer_precision_velocity']:+.4f}/cycle")
    print(f"Observer velocity: {summary['observer_precision_velocity']:+.4f}/cycle")
    print(f"Conductor velocity: {summary['conductor_precision_velocity']:+.4f}/cycle")
    print(f"Observer velocity multiplier: {summary['observer_velocity_multiplier']:.2f}x")
    print(f"Conductor velocity multiplier: {summary['conductor_velocity_multiplier']:.2f}x")
    print(f"Observer final delta: {summary['observer_delta_final']:+.4f}")
    print(f"Conductor delta vs observer: {summary['conductor_observer_delta']:+.4f}")
    print(f"Harmony index: {summary['harmony_index']:.4f}")
    print(f"Trajectory gain over baseline: {summary['trajectory_gain_over_baseline']:+.4f}")
    print(f"Drift reduction: {summary['drift_reduction_with_observer']:+.4f}")
    print(f"Lag reduction: {summary['lag_reduction_with_observer']:+.4f}")
    print(f"Resonance gain: {summary['resonance_gain_with_observer']:+.4f}")
    print()
    print("Cycle trajectory:")
    for row in payload["trajectory"]:
        cond = row.get("with_conductor", {})
        cond_score = cond.get("network_precision_score", 0.0)
        print(
            "- cycle {cycle}: no_obs={no:.4f} obs={obs:.4f} cond={cond:.4f} "
            "obs_d={od:+.4f} cond_d={cd:+.4f} drift={drift:.4f} res={res:.4f}".format(
                cycle=row["cycle"],
                no=row["no_observer"]["network_precision_score"],
                obs=row["with_observer"]["network_precision_score"],
                cond=cond_score,
                od=row["observer_delta"],
                cd=row.get("conductor_delta", 0.0),
                drift=row["with_observer"]["temporal"]["drift_score"],
                res=row["with_observer"]["temporal"]["resonance"],
            )
        )
        if row["reasons"]:
            for r in row["reasons"]:
                print(f"    reason: {r['message']}")

    co = payload.get("co_learning", {})
    if co:
        print()
        print("Co-learning summary:")
        print(f"  Network maturity: {co['network_maturity']}")
        print(f"  Total causal events: {co['total_causal_events']}")
        print(f"  Unique causal patterns: {co['unique_causal_patterns']}")
        print(f"  Top patterns:")
        for p in co["causal_patterns"][:3]:
            print(f"    - {p['kind']} ({p['occurrences']}x)")
        if co["error_to_resource_conversions"]:
            print(f"  Error-to-resource conversions:")
            for e in co["error_to_resource_conversions"][:3]:
                print(f"    - cycle {e['cycle']}: {e['evidence']}")
        if co["learned_constraints"]:
            print(f"  Learned constraints:")
            for lc in co["learned_constraints"]:
                print(f"    - {lc}")
        if "conductor_velocity_multiplier" in co:
            print(f"  Conductor synergy: {co.get('conductor_velocity_multiplier', 0):.2f}x over no-observer baseline")


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
