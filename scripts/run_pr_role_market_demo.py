from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MODULES = ROOT / "python" / "modules"
PYTHON_ROOT = ROOT / "python"
for path in (SCRIPTS, MODULES, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from graph.trail_updater import compute_route_reward  # noqa: E402
from ls.cognition.council_contribution_ledger import (  # noqa: E402
    CouncilContributionLedger,
    CouncilDecision,
    CouncilGoal,
    CouncilNetworkContext,
    CouncilOutcome,
    CouncilParticipant,
)
from run_pr_review_trail_artifact import build_pr_review_artifact  # noqa: E402


COOPERATIVE_ROUTE = "pr_review>draft_reviewer>risk_critic>evidence_verifier>final_reviewer"
BASELINE_ROUTE = "pr_review>direct_single_reviewer"

AVAILABLE_ACTORS = {
    "codex-self-use": {
        "actor_type": "agent",
        "provider": "codex",
        "model_name": "codex-self-use",
        "execution_mode": "codex_adapter",
        "source": "scripts/codex_self_use_adapter_demo.py",
    },
    "local-qwen": {
        "actor_type": "local_model",
        "provider": "ollama",
        "model_name": "qwen2.5:7b",
        "execution_mode": "local_ollama",
        "source": "python/modules/config.py",
    },
    "local-qwen-light": {
        "actor_type": "local_model",
        "provider": "ollama",
        "model_name": "qwen2.5:1.5b",
        "execution_mode": "local_ollama_fallback",
        "source": "python/modules/config.py",
    },
    "gonka": {
        "actor_type": "configured_backend",
        "provider": "gonka",
        "model_name": "qwen/qwen3-235b-a22b-instruct-2507-fp8",
        "execution_mode": "configured_backend_requires_key",
        "source": "python/modules/config.py",
    },
    "mimo": {
        "actor_type": "configured_backend",
        "provider": "mimo",
        "model_name": "mimo-v2-flash",
        "execution_mode": "configured_backend_requires_key",
        "source": "python/modules/config.py",
    },
    "human_operator": {
        "actor_type": "human",
        "provider": "human",
        "model_name": "operator",
        "execution_mode": "human_review",
        "source": "CouncilContributionLedger",
    },
}

ROLE_ACTOR_ASSIGNMENTS = {
    "maintainer_customer": {
        "actor_id": "human_operator",
        "reason": "sets the need, constraints, and acceptance boundary",
    },
    "route_planner": {
        "actor_id": "codex-self-use",
        "reason": "plans the LS role route inside the current Codex workflow",
    },
    "draft_reviewer": {
        "actor_id": "local-qwen",
        "reason": "uses the local Qwen path already present in LS",
    },
    "risk_critic": {
        "actor_id": "gonka",
        "reason": "uses the configured critic-style backend already present in LS",
    },
    "evidence_verifier": {
        "actor_id": "local-qwen-light",
        "reason": "uses the lightweight local Qwen fallback for grounded checks",
    },
    "final_reviewer": {
        "actor_id": "mimo",
        "reason": "uses the configured compressor/finalizer backend already present in LS",
    },
    "direct_single_reviewer": {
        "actor_id": "local-qwen",
        "reason": "baseline single-pass local review",
    },
}


def _clamp(value: float, *, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _signal_pressure(signals: list[dict[str, Any]]) -> float:
    weights = {
        "low": 0.01,
        "medium": 0.04,
        "human_review": 0.11,
        "hold": 0.16,
    }
    return round(min(0.32, sum(weights.get(str(signal.get("severity", "")), 0.03) for signal in signals)), 4)


def _baseline_quality_from_artifact(artifact: dict[str, Any]) -> dict[str, float]:
    quality = artifact["quality"]
    signals = artifact.get("signals") or []
    files = artifact.get("files") or []
    pressure = _signal_pressure(signals)
    file_pressure = min(0.08, max(0, len(files) - 4) * 0.01)

    return {
        "overall": round(_clamp(float(quality["overall"]) - 0.10 - pressure - file_pressure, low=0.25), 4),
        "relevance": round(_clamp(float(quality["relevance"]) - 0.05, low=0.25), 4),
        "thread_relevance": round(_clamp(float(quality["thread_relevance"]) - 0.08 - file_pressure, low=0.25), 4),
        "coherence": round(_clamp(float(quality["coherence"]) - 0.10 - (pressure / 2), low=0.25), 4),
        "goal_alignment_score": round(
            _clamp(float(quality["goal_alignment_score"]) - 0.10 - (pressure / 2), low=0.25),
            4,
        ),
        "hallucination_risk": round(_clamp(float(quality["hallucination_risk"]) + 0.12 + pressure), 4),
    }


def _compact_source_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": artifact.get("artifact_type"),
        "diff_source": artifact.get("diff_source"),
        "decision": artifact.get("decision"),
        "files": artifact.get("files"),
        "file_summary": artifact.get("file_summary"),
        "signals": artifact.get("signals"),
        "quality": artifact.get("quality"),
        "route_reward": artifact.get("route_reward"),
        "selected_route": artifact.get("selected_route"),
        "human_summary": artifact.get("human_summary"),
        "stat": artifact.get("stat"),
    }


def _role_reason(role: str, signals: list[dict[str, Any]]) -> str:
    signal_codes = {str(signal.get("code")) for signal in signals}
    if role == "risk_critic" and signal_codes:
        return "found the concrete review risks in the real diff"
    if role == "evidence_verifier":
        return "kept findings tied to visible diff evidence"
    if role == "route_planner":
        return "split the review into specialized roles"
    if role == "draft_reviewer":
        return "created the first review surface"
    if role == "final_reviewer":
        return "turned role outputs into a human-facing decision"
    if role == "maintainer_customer":
        return "provided the need and acceptance boundary"
    return "highest verified role contribution score"


def _actor_for_role(role: str) -> dict[str, Any]:
    assignment = ROLE_ACTOR_ASSIGNMENTS.get(role, {"actor_id": "human_operator", "reason": "manual fallback"})
    actor = AVAILABLE_ACTORS[assignment["actor_id"]]
    return {
        "role": role,
        "actor_id": assignment["actor_id"],
        "assignment_reason": assignment["reason"],
        **actor,
    }


def _role_actor_assignments() -> list[dict[str, Any]]:
    return [_actor_for_role(role) for role in ROLE_ACTOR_ASSIGNMENTS]


def _actor_by_role() -> dict[str, dict[str, Any]]:
    return {assignment["role"]: assignment for assignment in _role_actor_assignments()}


def _participants_for_artifact(artifact: dict[str, Any]) -> list[CouncilParticipant]:
    signals = artifact.get("signals") or []
    has_risk_signals = bool(signals)
    risk_weight = 0.42 if has_risk_signals else 0.2
    verifier_weight = 0.34 if has_risk_signals else 0.26
    route_weight = 0.18 if has_risk_signals else 0.28

    return [
        CouncilParticipant(
            model_id="maintainer_customer",
            model_type="human",
            proposal_id="review_need",
            proposal_summary="Needs a safer PR review before merge.",
            route_hint=BASELINE_ROUTE,
            confidence=0.84,
            latency_ms=900,
            selected=False,
            weight_in_final_decision=0.1,
        ),
        CouncilParticipant(
            model_id="route_planner",
            model_type="role",
            proposal_id="split_review_route",
            proposal_summary="Splits direct review into draft, risk, evidence, and final review roles.",
            route_hint=COOPERATIVE_ROUTE,
            confidence=0.88,
            latency_ms=1400,
            selected=True,
            weight_in_final_decision=route_weight,
        ),
        CouncilParticipant(
            model_id="draft_reviewer",
            model_type="role",
            proposal_id="diff_surface_summary",
            proposal_summary="Summarizes changed files, likely intent, and uncertainty.",
            route_hint=COOPERATIVE_ROUTE,
            confidence=0.84,
            latency_ms=2100,
            selected=True,
            weight_in_final_decision=0.16,
        ),
        CouncilParticipant(
            model_id="risk_critic",
            model_type="role",
            proposal_id="risk_signal_review",
            proposal_summary="Finds missing tests, large diff pressure, unsafe operations, or hold signals.",
            route_hint=COOPERATIVE_ROUTE,
            confidence=0.92,
            latency_ms=2700,
            selected=True,
            weight_in_final_decision=risk_weight,
        ),
        CouncilParticipant(
            model_id="evidence_verifier",
            model_type="role",
            proposal_id="evidence_check",
            proposal_summary="Checks whether findings are grounded in the diff and route artifact.",
            route_hint=COOPERATIVE_ROUTE,
            confidence=0.94,
            latency_ms=2400,
            selected=True,
            weight_in_final_decision=verifier_weight,
        ),
        CouncilParticipant(
            model_id="final_reviewer",
            model_type="role",
            proposal_id="human_decision_summary",
            proposal_summary="Produces the final human-facing review decision.",
            route_hint=COOPERATIVE_ROUTE,
            confidence=0.86,
            latency_ms=1300,
            selected=True,
            weight_in_final_decision=0.18,
        ),
        CouncilParticipant(
            model_id="direct_single_reviewer",
            model_type="baseline",
            proposal_id="direct_review",
            proposal_summary="Reviews the PR in one unsplit pass.",
            route_hint=BASELINE_ROUTE,
            confidence=0.72,
            latency_ms=3500,
            selected=False,
            weight_in_final_decision=0.0,
        ),
    ]


def build_pr_role_market_payload(
    *,
    repo: Path,
    base: str,
    head: str,
    diff_file: Path | None,
    store_path: Path,
    max_diff_chars: int,
) -> dict[str, Any]:
    artifact = build_pr_review_artifact(
        repo=repo,
        base=base,
        head=head,
        diff_file=diff_file,
        store_path=store_path,
        max_diff_chars=max_diff_chars,
    )

    baseline_quality = _baseline_quality_from_artifact(artifact)
    cooperative_quality = artifact["quality"]
    baseline_latency_ms = 3500.0
    cooperative_latency_ms = float(artifact.get("updated_route", {}).get("avg_latency_ms") or 6000.0)
    baseline_reward = compute_route_reward(baseline_quality, baseline_latency_ms)
    cooperative_reward = compute_route_reward(cooperative_quality, cooperative_latency_ms)
    synergy_quality = round(float(cooperative_quality["overall"]) - float(baseline_quality["overall"]), 4)
    synergy_reward = round(cooperative_reward - baseline_reward, 4)

    participants = _participants_for_artifact(artifact)
    decision = artifact.get("decision", "unknown")
    operator_intervention_required = decision in {"hold_until_diff", "human_review"}
    receiver_resonance = 0.86 if decision != "hold_until_diff" else 0.55

    ledger = CouncilContributionLedger.build(
        cycle_id="pr-role-market-demo-001",
        task_id=f"pr-role-market:{artifact['diff_source']}",
        goal=CouncilGoal(
            type="real_pr_role_market",
            summary="Measure which cooperative role improved a real PR-review route.",
        ),
        network_context=CouncilNetworkContext(
            route_candidates=[BASELINE_ROUTE, COOPERATIVE_ROUTE],
            active_nodes=[participant.model_id for participant in participants],
            graph_state_version="pr-role-market-demo-v0.1",
        ),
        participants=participants,
        final_decision=CouncilDecision(
            selected_route=COOPERATIVE_ROUTE,
            decision_summary=f"Use cooperative PR-review route; LS decision is {decision}.",
            derived_from_proposals=[
                "split_review_route",
                "diff_surface_summary",
                "risk_signal_review",
                "evidence_check",
                "human_decision_summary",
            ],
        ),
        outcome=CouncilOutcome(
            success=decision != "hold_until_diff",
            path_quality=float(cooperative_quality["overall"]),
            network_improvement=synergy_quality,
            operator_intervention_required=operator_intervention_required,
            operator_feedback_score=0.84 if artifact.get("signals") else 0.9,
            drift_detected=False,
            receiver_type="maintainer",
            receiver_resonance_score=receiver_resonance,
            receiver_acceptance_label="review_with_conditions" if artifact.get("signals") else "accepted",
        ),
    )
    breakdown = sorted(
        ledger.attribution.contribution_breakdown,
        key=lambda item: item.total_contribution_score,
        reverse=True,
    )
    best = breakdown[0]
    actor_map = _actor_by_role()
    best_actor = actor_map.get(best.model_id, _actor_for_role("maintainer_customer"))

    return {
        "artifact_type": "ls.pr_role_market.v0.1",
        "demo": "ls_real_pr_role_market",
        "live_model_calls": False,
        "model_roster_source": "checked-in LS adapters and config defaults only",
        "available_actor_roster": [
            {"actor_id": actor_id, **actor}
            for actor_id, actor in AVAILABLE_ACTORS.items()
        ],
        "role_actor_assignments": _role_actor_assignments(),
        "source_artifact": _compact_source_artifact(artifact),
        "baseline": {
            "route": BASELINE_ROUTE,
            "quality": baseline_quality,
            "reward": baseline_reward,
            "latency_ms": baseline_latency_ms,
        },
        "cooperative": {
            "route": COOPERATIVE_ROUTE,
            "quality": cooperative_quality,
            "reward": cooperative_reward,
            "latency_ms": cooperative_latency_ms,
        },
        "synergy": {
            "quality_lift": synergy_quality,
            "reward_lift": synergy_reward,
            "formula": "cooperative_role_route - direct_single_reviewer",
        },
        "best_role_contributor": {
            "role": best.model_id,
            "score": best.total_contribution_score,
            "reason": _role_reason(best.model_id, artifact.get("signals") or []),
        },
        "best_actor_contributor": {
            "role": best.model_id,
            "actor_id": best_actor["actor_id"],
            "provider": best_actor["provider"],
            "model_name": best_actor["model_name"],
            "execution_mode": best_actor["execution_mode"],
            "score": best.total_contribution_score,
            "note": "Actor assignment is from the current LS roster; this demo does not live-call models.",
        },
        "role_scores": [
            {
                **item.__dict__,
                "actor_id": actor_map.get(item.model_id, {}).get("actor_id", "unknown"),
                "provider": actor_map.get(item.model_id, {}).get("provider", "unknown"),
                "model_name": actor_map.get(item.model_id, {}).get("model_name", "unknown"),
            }
            for item in breakdown
        ],
        "ledger": ledger.to_dict(),
        "next_step": "attach real role outputs from Codex, local models, or humans and compare contribution scores over many PRs",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    source = payload["source_artifact"]
    best = payload["best_role_contributor"]
    best_actor = payload.get("best_actor_contributor") or {}
    lines = [
        "# LS PR Role Market Report",
        "",
        "This report scores a cooperative role route over a real PR-style git diff.",
        "",
        f"- Live model calls: `{str(payload.get('live_model_calls', False)).lower()}`",
        f"- Model roster source: `{payload.get('model_roster_source', 'unknown')}`",
        "",
        "## Source",
        "",
        f"- Diff source: `{source['diff_source']}`",
        f"- Decision: `{source['decision']}`",
        f"- Files changed: `{len(source.get('files') or [])}`",
        f"- Signals: `{', '.join(signal['code'] for signal in source.get('signals') or []) or 'none'}`",
        "",
        "## Result",
        "",
        f"- Baseline route: `{payload['baseline']['route']}`",
        f"- Baseline reward: `{payload['baseline']['reward']}`",
        f"- Cooperative route: `{payload['cooperative']['route']}`",
        f"- Cooperative reward: `{payload['cooperative']['reward']}`",
        f"- Quality lift: `+{payload['synergy']['quality_lift']}`",
        f"- Reward lift: `+{payload['synergy']['reward_lift']}`",
        f"- Best role contribution: `{best['role']}` score `{best['score']}`",
        f"- Best actor/model: `{best_actor.get('actor_id', 'unknown')}` / `{best_actor.get('model_name', 'unknown')}`",
        f"- Reason: {best['reason']}",
        "",
        "## Actor Roster",
        "",
        "| Actor | Provider | Model | Mode |",
        "| --- | --- | --- | --- |",
    ]
    for actor in payload.get("available_actor_roster") or []:
        lines.append(
            f"| {actor['actor_id']} | {actor['provider']} | {actor['model_name']} | {actor['execution_mode']} |"
        )
    lines.extend(
        [
            "",
            "## Role Assignments",
            "",
            "| Role | Actor | Model | Reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    for assignment in payload.get("role_actor_assignments") or []:
        lines.append(
            "| {role} | {actor_id} | {model_name} | {assignment_reason} |".format(**assignment)
        )
    lines.extend(
        [
            "",
            "## Role Scores",
            "",
            "| Role | Actor | Model | Score | Adoption | Outcome lift | Stability | Cost efficiency |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for score in payload["role_scores"]:
        lines.append(
            "| {model_id} | {actor_id} | {model_name} | {total_contribution_score} | {adoption_score} | "
            "{outcome_lift} | {stability_impact} | {cost_efficiency} |".format(**score)
        )
    lines.extend(
        [
            "",
            "## Signals",
            "",
        ]
    )
    for signal in source.get("signals") or []:
        lines.append(f"- `{signal['severity']}` `{signal['code']}`: {signal['message']}")
    if not source.get("signals"):
        lines.append("- `low` `none`: No review signals detected.")
    lines.extend(
        [
            "",
            "## Why This Matters",
            "",
            "The score is contextual: it credits the role that improved this review route, not a hidden global rank of people.",
            "Over many PRs, LS can learn which cooperative routes make the network more precise.",
            "Model identity is limited to actors already present in this LS repository/config.",
        ]
    )
    return "\n".join(lines) + "\n"


def _signal_codes(source: dict[str, Any]) -> str:
    codes = [str(signal.get("code")) for signal in source.get("signals") or []]
    return ", ".join(codes) if codes else "none"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Score cooperative roles over a real LS PR-review artifact.")
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository path.")
    parser.add_argument("--base", default="HEAD~1", help="Base revision. Default reviews the latest commit.")
    parser.add_argument("--head", default="HEAD", help="Head revision.")
    parser.add_argument("--diff-file", type=Path, default=None, help="Read a saved diff instead of running git diff.")
    parser.add_argument("--store-path", type=Path, default=None, help="Route stats JSON path.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON role-market artifact.")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Write Markdown role-market report.")
    parser.add_argument("--max-diff-chars", type=int, default=12000, help="Max diff excerpt used by source artifact.")
    parser.add_argument("--json", action="store_true", help="Print full JSON payload.")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-pr-role-market-") as tmp:
            payload = build_pr_role_market_payload(
                repo=repo,
                base=args.base,
                head=args.head,
                diff_file=args.diff_file,
                store_path=Path(tmp) / "routes.json",
                max_diff_chars=args.max_diff_chars,
            )
    else:
        payload = build_pr_role_market_payload(
            repo=repo,
            base=args.base,
            head=args.head,
            diff_file=args.diff_file,
            store_path=args.store_path,
            max_diff_chars=args.max_diff_chars,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(payload), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        source = payload["source_artifact"]
        best = payload["best_role_contributor"]
        best_actor = payload["best_actor_contributor"]
        print("LS PR Role Market demo")
        print(f"Diff source: {source['diff_source']}")
        print(f"Files changed: {len(source.get('files') or [])}")
        print(f"Decision: {source['decision']}")
        print(f"Signals: {_signal_codes(source)}")
        print(f"Live model calls: {str(payload['live_model_calls']).lower()}")
        print(f"Baseline route: {payload['baseline']['route']}")
        print(f"Cooperative route: {payload['cooperative']['route']}")
        print(f"Baseline reward: {payload['baseline']['reward']:.4f}")
        print(f"Cooperative reward: {payload['cooperative']['reward']:.4f}")
        print(f"Synergy quality lift: +{payload['synergy']['quality_lift']:.4f}")
        print(f"Best role contribution: {best['role']} score={best['score']:.4f}")
        print(
            "Best actor/model: "
            f"{best_actor['actor_id']} provider={best_actor['provider']} model={best_actor['model_name']}"
        )
        print(f"Reason: {best['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
