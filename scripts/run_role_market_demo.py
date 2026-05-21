from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "python" / "modules"
PYTHON_ROOT = ROOT / "python"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from graph.trail_updater import compute_route_reward  # noqa: E402
from ls.cognition.council_contribution_ledger import (  # noqa: E402
    CouncilDecision,
    CouncilGoal,
    CouncilNetworkContext,
    CouncilOutcome,
    CouncilParticipant,
    CouncilContributionLedger,
)


SINGLE_REVIEWER_QUALITY = {
    "overall": 0.68,
    "relevance": 0.72,
    "thread_relevance": 0.66,
    "coherence": 0.7,
    "goal_alignment_score": 0.64,
    "hallucination_risk": 0.2,
}

COOPERATIVE_QUALITY = {
    "overall": 0.92,
    "relevance": 0.94,
    "thread_relevance": 0.9,
    "coherence": 0.93,
    "goal_alignment_score": 0.9,
    "hallucination_risk": 0.06,
}


def build_role_market_demo_payload() -> dict[str, Any]:
    single_reward = compute_route_reward(SINGLE_REVIEWER_QUALITY, latency_ms=3500)
    cooperative_reward = compute_route_reward(COOPERATIVE_QUALITY, latency_ms=8100)
    synergy_quality = round(COOPERATIVE_QUALITY["overall"] - SINGLE_REVIEWER_QUALITY["overall"], 4)
    synergy_reward = round(cooperative_reward - single_reward, 4)

    route_key = "pr_review>designer>executor>verifier>final"
    participants = [
        CouncilParticipant(
            model_id="customer_maintainer",
            model_type="human",
            proposal_id="need_pr_review",
            proposal_summary="Needs safer PR review before merge.",
            route_hint="pr_review>local",
            confidence=0.82,
            latency_ms=1200,
            selected=False,
            weight_in_final_decision=0.1,
        ),
        CouncilParticipant(
            model_id="route_designer",
            model_type="role",
            proposal_id="design_cooperative_route",
            proposal_summary="Selects draft -> critic -> verifier -> final route.",
            route_hint=route_key,
            confidence=0.91,
            latency_ms=1800,
            selected=True,
            weight_in_final_decision=0.28,
        ),
        CouncilParticipant(
            model_id="executor_draft_reviewer",
            model_type="role",
            proposal_id="draft_review",
            proposal_summary="Summarizes changed surface and likely intent.",
            route_hint=route_key,
            confidence=0.84,
            latency_ms=3200,
            selected=True,
            weight_in_final_decision=0.18,
        ),
        CouncilParticipant(
            model_id="risk_critic",
            model_type="role",
            proposal_id="risk_findings",
            proposal_summary="Finds missing tests and large-diff review risk.",
            route_hint=route_key,
            confidence=0.9,
            latency_ms=4100,
            selected=True,
            weight_in_final_decision=0.22,
        ),
        CouncilParticipant(
            model_id="evidence_verifier",
            model_type="role",
            proposal_id="evidence_check",
            proposal_summary="Verifies findings against diff signals and filters unsupported claims.",
            route_hint=route_key,
            confidence=0.94,
            latency_ms=2600,
            selected=True,
            weight_in_final_decision=0.3,
        ),
        CouncilParticipant(
            model_id="consumer_repo_users",
            model_type="human",
            proposal_id="consumer_acceptance",
            proposal_summary="Benefits from lower merge risk and clearer review evidence.",
            route_hint=route_key,
            confidence=0.78,
            latency_ms=900,
            selected=False,
            weight_in_final_decision=0.12,
        ),
    ]

    ledger = CouncilContributionLedger.build(
        cycle_id="role-market-demo-001",
        task_id="pr-review-role-market-demo",
        goal=CouncilGoal(
            type="cooperative_role_market",
            summary="Measure which role arrangement improves PR review precision.",
        ),
        network_context=CouncilNetworkContext(
            route_candidates=["pr_review>local", route_key],
            active_nodes=[participant.model_id for participant in participants],
            graph_state_version="role-market-demo-v0.1",
        ),
        participants=participants,
        final_decision=CouncilDecision(
            selected_route=route_key,
            decision_summary="Use cooperative PR-review route for next similar task.",
            derived_from_proposals=[
                "design_cooperative_route",
                "draft_review",
                "risk_findings",
                "evidence_check",
            ],
        ),
        outcome=CouncilOutcome(
            success=True,
            path_quality=COOPERATIVE_QUALITY["overall"],
            network_improvement=synergy_quality,
            operator_intervention_required=False,
            operator_feedback_score=0.86,
            drift_detected=False,
            receiver_type="maintainer",
            receiver_resonance_score=0.88,
            receiver_acceptance_label="accepted_with_conditions",
        ),
    )
    breakdown = sorted(
        ledger.attribution.contribution_breakdown,
        key=lambda item: item.total_contribution_score,
        reverse=True,
    )
    best = breakdown[0]
    role_reasons = {
        "route_designer": "designed the cooperative route that improved the result",
        "executor_draft_reviewer": "created the first review surface",
        "risk_critic": "found the concrete review risks",
        "evidence_verifier": "checked evidence and filtered unsupported claims",
        "customer_maintainer": "defined the demand and constraints",
        "consumer_repo_users": "confirmed the value target",
    }

    return {
        "demo": "ls_cooperative_role_market",
        "task_type": "github_pr_review",
        "need": "Safer pull-request review before merge.",
        "role_chain": [
            "customer",
            "consumer",
            "designer",
            "executor",
            "verifier",
            "operator",
        ],
        "baseline": {
            "route": "pr_review>local",
            "quality": SINGLE_REVIEWER_QUALITY["overall"],
            "reward": single_reward,
        },
        "cooperative": {
            "route": route_key,
            "quality": COOPERATIVE_QUALITY["overall"],
            "reward": cooperative_reward,
        },
        "synergy": {
            "quality_lift": synergy_quality,
            "reward_lift": synergy_reward,
            "formula": "cooperative_result - best_single_result",
        },
        "best_role_contributor": {
            "role": best.model_id,
            "score": best.total_contribution_score,
            "reason": role_reasons.get(best.model_id, "highest verified contribution score"),
        },
        "role_scores": [item.__dict__ for item in breakdown],
        "ledger": ledger.to_dict(),
        "next_step": "attach role outputs to real PR review artifacts and score verified contributions by role",
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run the LS Cooperative Role Market demo.")
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON artifact output path.")
    parser.add_argument("--json", action="store_true", help="Print full JSON payload.")
    args = parser.parse_args()

    payload = build_role_market_demo_payload()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        best = payload["best_role_contributor"]
        print("LS Cooperative Role Market demo")
        print(f"Need: {payload['need']}")
        print(f"Best route: {payload['cooperative']['route']}")
        print(f"Baseline quality: {payload['baseline']['quality']:.2f}")
        print(f"Cooperative quality: {payload['cooperative']['quality']:.2f}")
        print(f"Synergy quality lift: +{payload['synergy']['quality_lift']:.2f}")
        print(f"Best role contribution: {best['role']} score={best['score']:.4f}")
        print(f"Reason: {best['reason']}")
        print("Decision: use cooperative role route next time")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
