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

from run_nash_route_stability_demo import build_demo_payload as build_nash_payload  # noqa: E402


METRIC_VERSION = "network_precision_gain.v0.1"

WEIGHTS = {
    "route_reward": 0.40,
    "evidence_gate": 0.16,
    "trace_integrity": 0.12,
    "adaptive_memory": 0.12,
    "reflective_clarity": 0.10,
    "human_boundary": 0.06,
    "depth_fit": 0.04,
}

SIX_PATHS = [
    {
        "path": "TTM DB",
        "role": "immutable_trace",
        "question": "What happened and which transition became irreversible?",
    },
    {
        "path": "LiminalDB",
        "role": "adaptive_living_memory",
        "question": "Which routes should grow, decay, synchronize, or be replayed?",
    },
    {
        "path": "PythiaLabs",
        "role": "evidence_action_gate",
        "question": "Is this route or action backed by enough evidence to proceed?",
    },
    {
        "path": "LS",
        "role": "cooperative_route_scoring",
        "question": "Which role route made the task more precise?",
    },
    {
        "path": "RINSE",
        "role": "reflective_interpretation",
        "question": "What did this experience mean and what should be tried next?",
    },
    {
        "path": "Human Operator",
        "role": "goal_consent_meaning",
        "question": "What is the real goal, boundary, consent, and acceptance test?",
    },
]


def _round(value: float) -> float:
    return round(float(value), 4)


def _weighted_score(components: dict[str, float]) -> float:
    return _round(sum(float(components[key]) * weight for key, weight in WEIGHTS.items()))


def _variant(label: str, route_key: str, components: dict[str, float], *, boundary: str) -> dict[str, Any]:
    return {
        "label": label,
        "route_key": route_key,
        "boundary": boundary,
        "components": {key: _round(value) for key, value in components.items()},
        "network_precision_score": _weighted_score(components),
    }


def build_demo_payload(route_store_path: Path, event_log_path: Path) -> dict[str, Any]:
    nash = build_nash_payload(route_store_path, event_log_path)
    full_route = nash["full_route"]
    baseline_route = nash["baseline_route"]
    stability = nash["stability"]

    baseline_reward = float(baseline_route["reward"])
    cooperative_reward = float(full_route["reward"])
    cooperative_repeatability = float(full_route["repeatability_score"])
    measured_route_reward_gain = _round(cooperative_reward - baseline_reward)

    baseline = _variant(
        "single_answer_baseline",
        str(baseline_route["route_key"]),
        {
            "route_reward": baseline_reward,
            "evidence_gate": 0.20,
            "trace_integrity": 0.20,
            "adaptive_memory": 0.20,
            "reflective_clarity": 0.10,
            "human_boundary": 0.20,
            "depth_fit": 0.25,
        },
        boundary="single route has weak evidence, weak reflection, and little reusable memory",
    )
    cooperative = _variant(
        "cooperative_route",
        str(full_route["route_key"]),
        {
            "route_reward": cooperative_reward,
            "evidence_gate": 0.70,
            "trace_integrity": 0.50,
            "adaptive_memory": cooperative_repeatability,
            "reflective_clarity": 0.40,
            "human_boundary": 0.90,
            "depth_fit": 0.65,
        },
        boundary="role cooperation is measured, but the full cross-stack bridge is still a proxy",
    )
    full_stack = _variant(
        "cooperative_precision_stack",
        "ttm>ls>pythia>liminaldb>rinse>human",
        {
            "route_reward": cooperative_reward,
            "evidence_gate": 0.95,
            "trace_integrity": 1.00,
            "adaptive_memory": cooperative_repeatability,
            "reflective_clarity": 0.72,
            "human_boundary": 0.95,
            "depth_fit": 0.88,
        },
        boundary="modeled stack score: immutable trace, gate, living memory, reflection, and human boundary",
    )

    variants = [baseline, cooperative, full_stack]
    network_precision_gain = _round(full_stack["network_precision_score"] - baseline["network_precision_score"])
    cooperative_gain = _round(cooperative["network_precision_score"] - baseline["network_precision_score"])
    stack_added_gain = _round(full_stack["network_precision_score"] - cooperative["network_precision_score"])

    return {
        "demo": "ls_network_precision_gain",
        "metric_version": METRIC_VERSION,
        "source_metric": {
            "demo": nash["demo"],
            "metric_version": nash["metric_version"],
            "interpretation_boundary": nash["interpretation_boundary"],
        },
        "interpretation_boundary": (
            "Network precision gain is a deterministic proxy that combines measured route reward "
            "with evidence, trace, adaptive-memory, reflection, depth, and human-boundary support. "
            "It is not a proof of general intelligence or production readiness."
        ),
        "six_paths": SIX_PATHS,
        "weights": WEIGHTS,
        "variants": variants,
        "measured_route_reward_gain": measured_route_reward_gain,
        "network_precision": {
            "baseline_score": baseline["network_precision_score"],
            "cooperative_score": cooperative["network_precision_score"],
            "full_stack_score": full_stack["network_precision_score"],
            "cooperative_gain_over_baseline": cooperative_gain,
            "stack_added_gain_over_cooperation": stack_added_gain,
            "network_precision_gain_over_baseline": network_precision_gain,
            "score_ratio_vs_baseline": _round(
                full_stack["network_precision_score"] / max(0.0001, baseline["network_precision_score"])
            ),
            "decision": "use_stack_for_repeatable_routes"
            if network_precision_gain > 0 and measured_route_reward_gain > 0
            else "needs_more_evidence",
        },
        "route_stability": {
            "decision": stability["decision"],
            "coalition_gain": stability["coalition_gain"],
            "stability_margin": stability["stability_margin"],
            "minimum_marginal_contribution": stability["minimum_marginal_contribution"],
        },
        "plain_ru": [
            "Измеренный route reward gain показывает, что кооперативный маршрут лучше одиночного ответа.",
            "Network precision gain показывает, сколько добавляет вся сеть: след, ворота, память, осмысление и человек.",
            "Это proxy для архитектурного решения, а не утверждение, что система уже стала автономно умнее.",
        ],
    }


def _print_text(payload: dict[str, Any]) -> None:
    precision = payload["network_precision"]
    print("LS Network Precision Gain demo")
    print(f"Metric version: {payload['metric_version']}")
    print(f"Decision: {precision['decision']}")
    print(f"Measured route reward gain: {payload['measured_route_reward_gain']:+.4f}")
    print(f"Network precision gain: {precision['network_precision_gain_over_baseline']:+.4f}")
    print(f"Stack added gain over cooperation: {precision['stack_added_gain_over_cooperation']:+.4f}")
    print(f"Score ratio vs baseline: {precision['score_ratio_vs_baseline']:.4f}x")
    print()
    for variant in payload["variants"]:
        print(
            "{label}: score={score:.4f} route_reward={reward:.4f} route={route}".format(
                label=variant["label"],
                score=variant["network_precision_score"],
                reward=variant["components"]["route_reward"],
                route=variant["route_key"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic LS network precision gain demo.")
    parser.add_argument("--store-path", type=Path, default=None, help="Optional route stats JSON path.")
    parser.add_argument("--events-path", type=Path, default=None, help="Optional trail event JSONL path.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-network-precision-") as tmp:
            tmp_path = Path(tmp)
            payload = build_demo_payload(
                tmp_path / "routes.json",
                args.events_path or tmp_path / "trail_events.jsonl",
            )
    else:
        payload = build_demo_payload(
            args.store_path,
            args.events_path or args.store_path.with_name("trail_events.jsonl"),
        )

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
