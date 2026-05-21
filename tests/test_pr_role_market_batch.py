from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_pr_role_market_batch import render_markdown, summarize_rows  # noqa: E402


def test_summarize_rows_counts_lift_roles_and_actors():
    rows = [
        {
            "status": "ok",
            "best_role": "risk_critic",
            "best_actor_id": "gonka",
            "baseline_reward": 0.5,
            "cooperative_reward": 0.7,
            "reward_lift": 0.2,
            "quality_lift": 0.15,
        },
        {
            "status": "ok",
            "best_role": "evidence_verifier",
            "best_actor_id": "local-qwen-light",
            "baseline_reward": 0.6,
            "cooperative_reward": 0.66,
            "reward_lift": 0.06,
            "quality_lift": 0.1,
        },
        {
            "status": "error",
            "best_role": "n/a",
            "best_actor_id": "n/a",
            "baseline_reward": 0,
            "cooperative_reward": 0,
            "reward_lift": 0,
            "quality_lift": 0,
        },
    ]

    summary = summarize_rows(rows)

    assert summary["requested"] == 3
    assert summary["analyzed"] == 2
    assert summary["errors"] == 1
    assert summary["positive_reward_lift"] == 2
    assert summary["avg_reward_lift"] == 0.13
    assert summary["top_role"] == "risk_critic"
    assert summary["top_actor"] == "gonka"


def test_render_markdown_keeps_batch_contextual():
    payload = {
        "repo": "repo",
        "head": "HEAD",
        "last": 1,
        "attached_role_outputs": True,
        "summary": {
            "analyzed": 1,
            "errors": 0,
            "avg_baseline_reward": 0.5,
            "avg_cooperative_reward": 0.7,
            "avg_reward_lift": 0.2,
            "avg_quality_lift": 0.15,
            "positive_reward_lift": 1,
            "top_role": "risk_critic",
            "top_role_count": 1,
            "top_actor": "gonka",
            "top_actor_count": 1,
        },
        "rows": [
            {
                "status": "ok",
                "short_commit": "abcdef12",
                "decision": "review_with_conditions",
                "signals": ["large_diff"],
                "baseline_reward": 0.5,
                "cooperative_reward": 0.7,
                "reward_lift": 0.2,
                "best_role": "risk_critic",
                "best_actor_id": "gonka",
                "best_actor_model": "qwen/qwen3-235b-a22b-instruct-2507-fp8",
            }
        ],
    }

    markdown = render_markdown(payload)

    assert "LS PR Role Market Batch Report" in markdown
    assert "risk_critic" in markdown
    assert "not a global ranking of people or models" in markdown
