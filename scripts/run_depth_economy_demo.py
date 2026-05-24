from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


DEPTH_METRIC_VERSION = "depth_economy.v0.1"


@dataclass(frozen=True)
class DepthLevel:
    level: int
    name: str
    customer: str
    consumer: str
    question: str


DEPTH_LEVELS = [
    DepthLevel(
        1,
        "direct_task",
        "immediate_request_owner",
        "immediate_user",
        "Can this be executed correctly now?",
    ),
    DepthLevel(
        2,
        "product_value",
        "product_or_workflow_owner",
        "workflow_user_or_team",
        "Will this improve the user's real workflow?",
    ),
    DepthLevel(
        3,
        "systemic_impact",
        "system_steward",
        "affected_community_or_ecosystem",
        "What second-order effects does this create?",
    ),
    DepthLevel(
        4,
        "long_horizon_stewardship",
        "long_horizon_steward",
        "future_maintainers_and_downstream_users",
        "Should this change be allowed to shape future behavior?",
    ),
]


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "low_risk_fix",
        "label": "small deterministic fix",
        "task_importance": 0.25,
        "risk_pressure": 0.12,
        "uncertainty": 0.18,
        "care_expansion": 0.20,
        "evidence_gap": 0.10,
        "reversibility": 0.90,
        "amygdala_pressure": 0.12,
    },
    {
        "id": "product_route_design",
        "label": "workflow design decision",
        "task_importance": 0.55,
        "risk_pressure": 0.35,
        "uncertainty": 0.45,
        "care_expansion": 0.50,
        "evidence_gap": 0.35,
        "reversibility": 0.62,
        "amygdala_pressure": 0.34,
    },
    {
        "id": "high_stakes_memory_or_action",
        "label": "high-stakes memory/action decision",
        "task_importance": 0.88,
        "risk_pressure": 0.80,
        "uncertainty": 0.65,
        "care_expansion": 0.84,
        "evidence_gap": 0.62,
        "reversibility": 0.24,
        "amygdala_pressure": 0.76,
    },
]


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _round(value: float) -> float:
    return round(float(value), 4)


def _depth_level(depth_pressure: float) -> DepthLevel:
    if depth_pressure >= 0.72:
        return DEPTH_LEVELS[3]
    if depth_pressure >= 0.52:
        return DEPTH_LEVELS[2]
    if depth_pressure >= 0.30:
        return DEPTH_LEVELS[1]
    return DEPTH_LEVELS[0]


def _interaction_math(level: int) -> str:
    if level <= 1:
        return "1+1=2"
    if level == 2:
        return "1+1=3"
    return "1+1=n"


def _required_roles(level: int, hold_for_human: bool) -> list[str]:
    roles = ["customer", "consumer", "executor", "verifier"]
    if level >= 2:
        roles.insert(2, "designer")
        roles.insert(4, "critic")
    if level >= 3:
        roles.insert(2, "higher_order_customer")
        roles.insert(3, "higher_order_consumer")
        roles.append("evidence_gate")
    if level >= 4:
        roles.append("operator")
        roles.append("memory_governor")
    if hold_for_human:
        roles.append("human_review")
    return roles


def evaluate_depth(scenario: dict[str, Any]) -> dict[str, Any]:
    importance = _clamp(scenario["task_importance"])
    risk = _clamp(scenario["risk_pressure"])
    uncertainty = _clamp(scenario["uncertainty"])
    care = _clamp(scenario["care_expansion"])
    evidence_gap = _clamp(scenario["evidence_gap"])
    reversibility = _clamp(scenario["reversibility"])
    amygdala = _clamp(scenario["amygdala_pressure"])
    irreversibility = 1.0 - reversibility

    execution_clarity = _round(1.0 - ((uncertainty + evidence_gap) / 2.0))
    design_synergy_pressure = _round((importance + uncertainty + care) / 3.0)
    customer_consumer_depth_pressure = _round(
        (importance + risk + care + evidence_gap + irreversibility + amygdala) / 6.0
    )
    depth_pressure = _round(
        (0.20 * importance)
        + (0.18 * risk)
        + (0.16 * uncertainty)
        + (0.18 * care)
        + (0.12 * evidence_gap)
        + (0.10 * irreversibility)
        + (0.06 * amygdala)
    )
    selected = _depth_level(depth_pressure)

    hold_for_human = amygdala >= 0.72 and (risk >= 0.65 or evidence_gap >= 0.55)
    if hold_for_human:
        amygdala_action = "hold_and_request_human_review"
    elif amygdala >= 0.62:
        amygdala_action = "deepen_and_slow_down"
    elif care - risk >= 0.24:
        amygdala_action = "expand_stakeholder_radius"
    elif risk - care >= 0.24:
        amygdala_action = "narrow_to_evidence_and_execution"
    else:
        amygdala_action = "maintain_middle_path"

    if hold_for_human:
        decision = "hold_until_human_review"
    elif selected.level >= 3:
        decision = "deepen_customer_consumer_pair"
    elif selected.level == 2:
        decision = "design_for_synergy"
    else:
        decision = "execute_directly"

    return {
        "scenario_id": str(scenario["id"]),
        "label": str(scenario["label"]),
        "metric_version": DEPTH_METRIC_VERSION,
        "input": {
            "task_importance": importance,
            "risk_pressure": risk,
            "uncertainty": uncertainty,
            "care_expansion": care,
            "evidence_gap": evidence_gap,
            "reversibility": reversibility,
            "amygdala_pressure": amygdala,
        },
        "signals": {
            "execution_clarity": execution_clarity,
            "design_synergy_pressure": design_synergy_pressure,
            "customer_consumer_depth_pressure": customer_consumer_depth_pressure,
            "depth_pressure": depth_pressure,
            "amygdala_action": amygdala_action,
        },
        "selected_depth": asdict(selected),
        "interaction_math": _interaction_math(selected.level),
        "required_roles": _required_roles(selected.level, hold_for_human),
        "decision": decision,
        "non_claim": "Depth Economy is a decision-routing proxy, not a claim of consciousness or moral authority.",
    }


def build_demo_payload() -> dict[str, Any]:
    evaluations = [evaluate_depth(scenario) for scenario in SCENARIOS]
    return {
        "demo": "ls_depth_economy",
        "metric_version": DEPTH_METRIC_VERSION,
        "thesis": "Executor checks 1+1=2, designer seeks 1+1=3, customer-consumer depth asks when 1+1=n.",
        "evaluations": evaluations,
        "summary": {
            "min_depth": min(item["selected_depth"]["level"] for item in evaluations),
            "max_depth": max(item["selected_depth"]["level"] for item in evaluations),
            "held_for_human_review": [
                item["scenario_id"]
                for item in evaluations
                if item["decision"] == "hold_until_human_review"
            ],
        },
        "non_claim": "This is an architectural probe for coordination depth, not a formal economic theorem.",
    }


def _print_text(payload: dict[str, Any]) -> None:
    print("LS Depth Economy demo")
    print(f"Metric version: {payload['metric_version']}")
    print(payload["thesis"])
    print()
    for item in payload["evaluations"]:
        depth = item["selected_depth"]
        print(
            "{scenario}: depth=L{level} {name}, math={math}, decision={decision}, amygdala={amygdala}".format(
                scenario=item["scenario_id"],
                level=depth["level"],
                name=depth["name"],
                math=item["interaction_math"],
                decision=item["decision"],
                amygdala=item["signals"]["amygdala_action"],
            )
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic LS Depth Economy demo.")
    parser.add_argument("--json", action="store_true", help="Print the full JSON payload.")
    args = parser.parse_args()

    payload = build_demo_payload()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
