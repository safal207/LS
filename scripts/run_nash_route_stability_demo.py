from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for path in (PYTHON_ROOT, MODULES_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from ls.agent_shell.trail_network import METRIC_VERSION, TrailNetworkBridge  # noqa: E402


NASH_METRIC_VERSION = "nash_route_stability.v0.1"
MIN_COALITION_GAIN = 0.10
MIN_STABILITY_MARGIN = 0.05
MIN_MARGINAL_CONTRIBUTION = 0.05


SCENARIOS: list[dict[str, Any]] = [
    {
        "label": "full_cooperative_route",
        "route_key": "pr_review>local>gonka>mimo",
        "kind": "full",
        "task_id": "nash-full",
        "evidence_coverage": 0.90,
        "false_positive_rate": 0.05,
        "human_accepted": True,
        "ci_passed": True,
        "useful_findings": 3,
        "unsupported_claims": 0,
        "latency_ms": 1200,
    },
    {
        "label": "single_route",
        "route_key": "pr_review>local",
        "kind": "baseline",
        "task_id": "nash-single",
        "evidence_coverage": 0.25,
        "false_positive_rate": 0.70,
        "human_accepted": False,
        "ci_passed": False,
        "useful_findings": 1,
        "unsupported_claims": 3,
        "latency_ms": 9000,
    },
    {
        "label": "without_gonka",
        "route_key": "pr_review>local>mimo",
        "kind": "ablation",
        "removed_participant": "gonka",
        "task_id": "nash-without-gonka",
        "evidence_coverage": 0.62,
        "false_positive_rate": 0.28,
        "human_accepted": True,
        "ci_passed": False,
        "useful_findings": 1,
        "unsupported_claims": 1,
        "latency_ms": 4000,
    },
    {
        "label": "without_mimo",
        "route_key": "pr_review>local>gonka",
        "kind": "ablation",
        "removed_participant": "mimo",
        "task_id": "nash-without-mimo",
        "evidence_coverage": 0.72,
        "false_positive_rate": 0.24,
        "human_accepted": True,
        "ci_passed": False,
        "useful_findings": 2,
        "unsupported_claims": 1,
        "latency_ms": 3000,
    },
    {
        "label": "without_local",
        "route_key": "pr_review>gonka>mimo",
        "kind": "ablation",
        "removed_participant": "local",
        "task_id": "nash-without-local",
        "evidence_coverage": 0.58,
        "false_positive_rate": 0.32,
        "human_accepted": True,
        "ci_passed": False,
        "useful_findings": 2,
        "unsupported_claims": 2,
        "latency_ms": 5000,
    },
    {
        "label": "reordered_route",
        "route_key": "pr_review>mimo>gonka>local",
        "kind": "deviation",
        "task_id": "nash-reordered",
        "evidence_coverage": 0.52,
        "false_positive_rate": 0.34,
        "human_accepted": False,
        "ci_passed": False,
        "useful_findings": 1,
        "unsupported_claims": 2,
        "latency_ms": 7000,
    },
]


def _round(value: float) -> float:
    return round(float(value), 4)


def _record_scenario(bridge: TrailNetworkBridge, scenario: dict[str, Any]) -> dict[str, Any]:
    outcome = bridge.record_outcome(
        {
            "route_key": scenario["route_key"],
            "task_id": scenario["task_id"],
            "task_text": "Nash-style route stability probe for PR review cooperation.",
            "evidence_coverage": scenario["evidence_coverage"],
            "false_positive_rate": scenario["false_positive_rate"],
            "human_accepted": scenario["human_accepted"],
            "ci_passed": scenario["ci_passed"],
            "useful_findings": scenario["useful_findings"],
            "unsupported_claims": scenario["unsupported_claims"],
            "latency_ms": scenario["latency_ms"],
        }
    )
    return {
        "label": scenario["label"],
        "route_key": scenario["route_key"],
        "kind": scenario["kind"],
        "removed_participant": scenario.get("removed_participant"),
        "reward": outcome["reward"],
        "outcome_success": outcome["outcome_success"],
        "decision": outcome["decision"],
        "repeatability_score": outcome["route_stats"]["repeatability_score"],
        "success_rate": outcome["route_stats"]["success_rate"],
        "route_health": outcome["route_stats"]["route_health"],
    }


def build_demo_payload(route_store_path: Path, event_log_path: Path) -> dict[str, Any]:
    bridge = TrailNetworkBridge(route_store_path=route_store_path, event_log_path=event_log_path)
    outcomes = [_record_scenario(bridge, scenario) for scenario in SCENARIOS]

    full = next(item for item in outcomes if item["kind"] == "full")
    baseline = next(item for item in outcomes if item["kind"] == "baseline")
    counterfactuals = [item for item in outcomes if item["kind"] != "full"]
    ablations = [item for item in outcomes if item["kind"] == "ablation"]

    full_reward = float(full["reward"])
    best_counterfactual = max(counterfactuals, key=lambda item: float(item["reward"]))
    coalition_gain = _round(full_reward - float(baseline["reward"]))
    stability_margin = _round(full_reward - float(best_counterfactual["reward"]))

    marginal_contributions = [
        {
            "participant": str(item["removed_participant"]),
            "without_route": item["route_key"],
            "without_reward": item["reward"],
            "marginal_contribution": _round(full_reward - float(item["reward"])),
        }
        for item in ablations
    ]
    min_marginal = min(item["marginal_contribution"] for item in marginal_contributions)
    nash_style_stable = (
        bool(full["outcome_success"])
        and coalition_gain >= MIN_COALITION_GAIN
        and stability_margin >= MIN_STABILITY_MARGIN
        and min_marginal >= MIN_MARGINAL_CONTRIBUTION
    )

    return {
        "demo": "ls_nash_route_stability",
        "metric_version": NASH_METRIC_VERSION,
        "trail_metric_version": METRIC_VERSION,
        "interpretation_boundary": "Nash-style route stability proxy, not a formal proof of Nash equilibrium.",
        "thresholds": {
            "min_coalition_gain": MIN_COALITION_GAIN,
            "min_stability_margin": MIN_STABILITY_MARGIN,
            "min_marginal_contribution": MIN_MARGINAL_CONTRIBUTION,
        },
        "full_route": full,
        "baseline_route": baseline,
        "counterfactuals": counterfactuals,
        "participant_marginal_contributions": marginal_contributions,
        "stability": {
            "nash_style_stable": nash_style_stable,
            "decision": "stable_candidate" if nash_style_stable else "not_stable_yet",
            "coalition_gain": coalition_gain,
            "best_counterfactual_route": best_counterfactual["route_key"],
            "best_counterfactual_reward": best_counterfactual["reward"],
            "stability_margin": stability_margin,
            "minimum_marginal_contribution": _round(min_marginal),
            "needs_more_runs": True,
        },
        "ranking": bridge.query_best_trails({"route_prefix": "pr_review", "limit": 10})["routes"],
    }


def _print_text(payload: dict[str, Any]) -> None:
    stability = payload["stability"]
    print("LS Nash Route Stability demo")
    print(f"Metric version: {payload['metric_version']}")
    print(f"Decision: {stability['decision']}")
    print(f"Nash-style stable: {str(stability['nash_style_stable']).lower()}")
    print(f"Coalition gain over single route: {stability['coalition_gain']:+.4f}")
    print(f"Stability margin vs best counterfactual: {stability['stability_margin']:+.4f}")
    print()
    print("Participant marginal contribution:")
    for item in payload["participant_marginal_contributions"]:
        print(
            "- {participant}: +{delta:.4f} vs {route}".format(
                participant=item["participant"],
                delta=item["marginal_contribution"],
                route=item["without_route"],
            )
        )
    print()
    print("Routes:")
    for item in [payload["full_route"], *payload["counterfactuals"]]:
        print(
            "- {label}: reward={reward:.4f} success={success} health={health} route={route}".format(
                label=item["label"],
                reward=item["reward"],
                success=str(item["outcome_success"]).lower(),
                health=item["route_health"],
                route=item["route_key"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic LS Nash-style route stability probe.")
    parser.add_argument("--store-path", type=Path, default=None, help="Optional route stats JSON path.")
    parser.add_argument("--events-path", type=Path, default=None, help="Optional trail event JSONL path.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-nash-route-stability-") as tmp:
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
