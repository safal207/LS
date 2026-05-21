from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_pr_role_market_demo import _baseline_quality_from_artifact, _role_actor_assignments, render_markdown  # noqa: E402


def test_baseline_quality_penalizes_unsplit_risky_review():
    artifact = {
        "quality": {
            "overall": 0.74,
            "relevance": 0.92,
            "thread_relevance": 0.9,
            "coherence": 0.72,
            "goal_alignment_score": 0.7,
            "hallucination_risk": 0.18,
        },
        "signals": [
            {"code": "missing_tests", "severity": "medium", "message": "Tests are missing."},
            {"code": "large_diff", "severity": "medium", "message": "Diff is large."},
        ],
        "files": ["README.md", "scripts/example.py", "docs/example.md", "docs/other.md", "docs/third.md"],
    }

    baseline = _baseline_quality_from_artifact(artifact)

    assert baseline["overall"] < artifact["quality"]["overall"]
    assert baseline["thread_relevance"] < artifact["quality"]["thread_relevance"]
    assert baseline["hallucination_risk"] > artifact["quality"]["hallucination_risk"]


def test_markdown_report_keeps_role_score_contextual():
    payload = {
        "source_artifact": {
            "diff_source": "HEAD~1..HEAD",
            "decision": "review_with_conditions",
            "files": ["scripts/example.py"],
            "signals": [
                {"code": "missing_tests", "severity": "medium", "message": "Tests are missing."},
            ],
        },
        "baseline": {"route": "pr_review>direct_single_reviewer", "reward": 0.5167},
        "cooperative": {
            "route": "pr_review>draft_reviewer>risk_critic>evidence_verifier>final_reviewer",
            "reward": 0.6639,
        },
        "synergy": {"quality_lift": 0.19, "reward_lift": 0.1472},
        "best_role_contributor": {
            "role": "risk_critic",
            "score": 0.8915,
            "reason": "found the concrete review risks in the real diff",
        },
        "best_actor_contributor": {
            "role": "risk_critic",
            "actor_id": "gonka",
            "provider": "gonka",
            "model_name": "qwen/qwen3-235b-a22b-instruct-2507-fp8",
            "execution_mode": "configured_backend_requires_key",
            "score": 0.8915,
        },
        "live_model_calls": False,
        "model_roster_source": "checked-in LS adapters and config defaults only",
        "available_actor_roster": [
            {
                "actor_id": "gonka",
                "provider": "gonka",
                "model_name": "qwen/qwen3-235b-a22b-instruct-2507-fp8",
                "execution_mode": "configured_backend_requires_key",
            }
        ],
        "role_actor_assignments": [
            {
                "role": "risk_critic",
                "actor_id": "gonka",
                "model_name": "qwen/qwen3-235b-a22b-instruct-2507-fp8",
                "assignment_reason": "uses the configured critic-style backend already present in LS",
            }
        ],
        "role_scores": [
            {
                "model_id": "risk_critic",
                "actor_id": "gonka",
                "model_name": "qwen/qwen3-235b-a22b-instruct-2507-fp8",
                "total_contribution_score": 0.8915,
                "adoption_score": 0.884,
                "outcome_lift": 0.7195,
                "stability_impact": 0.94,
                "cost_efficiency": 0.8625,
            }
        ],
    }

    markdown = render_markdown(payload)

    assert "risk_critic" in markdown
    assert "gonka" in markdown
    assert "not a hidden global rank of people" in markdown


def test_role_actor_assignments_use_existing_ls_roster_only():
    assignments = _role_actor_assignments()
    actor_ids = {item["actor_id"] for item in assignments}

    assert "gonka" in actor_ids
    assert "mimo" in actor_ids
    assert "local-qwen" in actor_ids
    assert "codex-self-use" in actor_ids
    assert "claude" not in actor_ids
    assert "kimi" not in actor_ids
