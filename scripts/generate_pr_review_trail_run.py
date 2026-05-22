#!/usr/bin/env python3
"""Generate a Cognitive Trail Run artifact from the PR Role Market benchmark.

This script turns the existing PR Role Market batch payload into the canonical
`cognitive_trail_run.v0.1` contract used by the LS Cognitive Trail Network.

Default output:
    reports/trails/<timestamp>_pr_review_trail_run.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_pr_role_market_batch import build_batch_payload  # noqa: E402
from run_pr_role_market_demo import (  # noqa: E402
    AVAILABLE_ACTORS,
    COOPERATIVE_ROUTE,
    ROLE_ACTOR_ASSIGNMENTS,
    _load_role_outputs,
)


SCHEMA_VERSION = "cognitive_trail_run.v0.1"
DEFAULT_OUTPUT_DIR = ROOT / "reports" / "trails"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _round4(value: Any) -> float:
    return round(float(value or 0.0), 4)


def _actor_model(actor_id: str) -> str | None:
    actor = AVAILABLE_ACTORS.get(actor_id)
    if not actor:
        return None
    return str(actor.get("model_name") or actor_id)


def _actor_for_role(role: str) -> str:
    assignment = ROLE_ACTOR_ASSIGNMENTS.get(role)
    if assignment:
        return str(assignment["actor_id"])
    return "human_operator"


def _route_from_summary(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a stable PR-review route that contains the reported top role/actor."""

    canonical_roles = [
        ("baseline_reviewer", "codex-self-use", "Provide direct single-pass baseline review signal."),
        ("draft_reviewer", _actor_for_role("draft_reviewer"), "Create the first cooperative draft review pass."),
        ("risk_critic", _actor_for_role("risk_critic"), "Identify merge risks, weak evidence, and unsafe assumptions."),
        ("evidence_verifier", _actor_for_role("evidence_verifier"), "Check that review claims are grounded in available evidence."),
        ("final_reviewer", _actor_for_role("final_reviewer"), "Produce the final human-facing review decision."),
        ("final_authority", "human_operator", "Accept, reject, or edit the route result before reuse."),
    ]

    top_role = str(summary.get("top_role") or "risk_critic")
    top_actor = str(summary.get("top_actor") or _actor_for_role(top_role))

    route = [
        {
            "step": index,
            "role": role,
            "actor": actor,
            **({"model": model} if (model := _actor_model(actor)) else {}),
            "responsibility": responsibility,
        }
        for index, (role, actor, responsibility) in enumerate(canonical_roles, start=1)
    ]

    roles = {step["role"] for step in route}
    actors = {step["actor"] for step in route}

    if top_role not in roles:
        route.append(
            {
                "step": len(route) + 1,
                "role": top_role,
                "actor": top_actor,
                **({"model": model} if (model := _actor_model(top_actor)) else {}),
                "responsibility": "Recorded top contributing role from the PR Role Market batch summary.",
            }
        )
        actors.add(top_actor)

    if top_actor not in actors:
        route.append(
            {
                "step": len(route) + 1,
                "role": f"{top_role}_assigned_actor",
                "actor": top_actor,
                **({"model": model} if (model := _actor_model(top_actor)) else {}),
                "responsibility": "Recorded top actor from the PR Role Market batch summary.",
            }
        )

    return route


def _evidence_from_batch(batch: dict[str, Any]) -> list[dict[str, Any]]:
    summary = batch["summary"]
    analyzed = int(summary.get("analyzed") or 0)
    errors = int(summary.get("errors") or 0)
    positive_lift = int(summary.get("positive_reward_lift") or 0)
    top_role = str(summary.get("top_role") or "risk_critic")
    top_actor = str(summary.get("top_actor") or _actor_for_role(top_role))

    evidence = [
        {
            "kind": "diff_signal",
            "description": f"PR Role Market batch analyzed {analyzed} run(s) from git history with {errors} error(s).",
            "strength": "medium" if analyzed else "weak",
            "source": "scripts/run_pr_role_market_batch.py",
        },
        {
            "kind": "risk_found",
            "description": f"The top contributing role was {top_role}; assigned top actor was {top_actor}.",
            "strength": "medium" if analyzed else "weak",
            "role": top_role,
            "actor": top_actor,
            "source": "PR Role Market batch summary",
        },
        {
            "kind": "diff_signal",
            "description": f"Positive reward lift was observed in {positive_lift}/{analyzed} analyzed run(s).",
            "strength": "strong" if analyzed and positive_lift == analyzed else "medium",
            "source": "PR Role Market batch summary",
        },
        {
            "kind": "human_decision",
            "description": "The generated trail run remains a local research artifact and does not claim a global model ranking.",
            "strength": "strong",
            "actor": "human_operator",
            "source": "docs/COGNITIVE_TRAIL_RUN_CONTRACT.md",
        },
    ]

    if errors:
        evidence.append(
            {
                "kind": "other",
                "description": f"{errors} batch row(s) failed and should be inspected before treating this route as validated.",
                "strength": "medium",
                "source": "PR Role Market batch rows",
            }
        )

    return evidence


def build_trail_run_from_batch(batch: dict[str, Any], *, task_id: str | None = None) -> dict[str, Any]:
    summary = batch["summary"]
    analyzed = int(summary.get("analyzed") or 0)
    errors = int(summary.get("errors") or 0)
    baseline_reward = _round4(summary.get("avg_baseline_reward"))
    cooperative_reward = _round4(summary.get("avg_cooperative_reward"))
    lift = round(cooperative_reward - baseline_reward, 4)
    positive_lift = lift > 0
    top_role = str(summary.get("top_role") or "risk_critic")
    top_actor = str(summary.get("top_actor") or _actor_for_role(top_role))
    positive_contributors = [
        actor_id
        for actor_id, count in sorted((summary.get("actor_counts") or {}).items())
        if int(count) > 0
    ]
    if "human_operator" not in positive_contributors:
        positive_contributors.append("human_operator")

    should_repeat = analyzed > 0 and positive_lift
    needs_more_runs = analyzed < 10 or errors > 0

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": task_id or f"pr-role-market-trail-run-{_timestamp()}",
        "task_type": "pr_review",
        "status": "local_research_mvp",
        "input_ref": {
            "kind": "git_diff",
            "description": f"Generated from PR Role Market batch over {analyzed} analyzed git-history run(s).",
            "repo": str(batch.get("repo") or ROOT),
            "commit": str(batch.get("head") or "HEAD"),
            "path": "reports/trails",
        },
        "route": _route_from_summary(summary),
        "evidence": _evidence_from_batch(batch),
        "result": {
            "baseline_reward": baseline_reward,
            "cooperative_reward": cooperative_reward,
            "lift": lift,
            "positive_lift": positive_lift,
            "top_role": top_role,
            "top_actor": top_actor,
            "route_key": COOPERATIVE_ROUTE,
            "decision": "repeat_with_more_diffs" if should_repeat else "do_not_prefer_without_more_evidence",
        },
        "contribution_summary": {
            "top_role": top_role,
            "top_actor": top_actor,
            "positive_contributors": positive_contributors,
            "noisy_actors": [],
            "notes": (
                "Generated from PR Role Market batch summary. This is contribution attribution inside "
                "a local PR-review route, not a global actor or model ranking."
            ),
        },
        "repeatability": {
            "should_repeat_route": should_repeat,
            "needs_more_runs": needs_more_runs,
            "reason": _repeatability_reason(analyzed, errors, lift, should_repeat, needs_more_runs),
            "next_route_hint": "Run more PR diffs with real role outputs, CI/test signals, and human review outcomes.",
        },
    }


def _repeatability_reason(
    analyzed: int,
    errors: int,
    lift: float,
    should_repeat: bool,
    needs_more_runs: bool,
) -> str:
    if not analyzed:
        return "No successful PR Role Market rows were analyzed, so the route should not be repeated yet."
    if errors:
        return f"The route produced lift {lift:+.4f}, but {errors} row(s) failed and need inspection."
    if should_repeat and needs_more_runs:
        return f"The cooperative route produced positive lift {lift:+.4f}, but the sample is still small."
    if should_repeat:
        return f"The cooperative route produced positive lift {lift:+.4f} over the analyzed sample."
    return f"The cooperative route did not produce positive lift; observed lift was {lift:+.4f}."


def _default_output_path(output_dir: Path) -> Path:
    return output_dir / f"{_timestamp()}_pr_review_trail_run.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Cognitive Trail Run JSON artifact from the LS PR Role Market batch benchmark."
    )
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository path.")
    parser.add_argument("--head", default="HEAD", help="Head revision to walk from.")
    parser.add_argument("--last", type=int, default=10, help="Number of first-parent commits to analyze.")
    parser.add_argument("--role-outputs", type=Path, default=None, help="Attach JSON role outputs to each run.")
    parser.add_argument("--max-diff-chars", type=int, default=6000, help="Max diff excerpt used by each source artifact.")
    parser.add_argument("--output", type=Path, default=None, help="Write trail-run JSON to this path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for default output path.")
    parser.add_argument("--task-id", default=None, help="Override generated task_id.")
    parser.add_argument("--json", action="store_true", help="Print the generated trail run JSON.")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    repo = args.repo.resolve()
    role_outputs = _load_role_outputs(args.role_outputs)
    batch = build_batch_payload(
        repo=repo,
        head=args.head,
        last=args.last,
        role_outputs=role_outputs,
        max_diff_chars=args.max_diff_chars,
    )
    trail_run = build_trail_run_from_batch(batch, task_id=args.task_id)

    output_path = args.output or _default_output_path(args.output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(trail_run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(trail_run, ensure_ascii=False, indent=2))
    else:
        result = trail_run["result"]
        repeatability = trail_run["repeatability"]
        print("Generated LS Cognitive Trail Run")
        print(f"Output: {output_path}")
        print(f"Task: {trail_run['task_id']}")
        print(f"Baseline reward: {result['baseline_reward']:.4f}")
        print(f"Cooperative reward: {result['cooperative_reward']:.4f}")
        print(f"Lift: {result['lift']:+.4f}")
        print(f"Top role: {result['top_role']}")
        print(f"Top actor: {result['top_actor']}")
        print(f"Repeat route: {str(repeatability['should_repeat_route']).lower()}")
        print(f"Needs more runs: {str(repeatability['needs_more_runs']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
