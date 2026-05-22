from __future__ import annotations

from scripts.generate_pr_review_trail_run import build_trail_run_from_batch


def test_build_trail_run_from_batch_contract_shape() -> None:
    batch = {
        "artifact_type": "ls.pr_role_market_batch.v0.1",
        "repo": "/tmp/LS",
        "head": "HEAD",
        "last": 3,
        "attached_role_outputs": True,
        "summary": {
            "requested": 3,
            "analyzed": 3,
            "errors": 0,
            "positive_reward_lift": 3,
            "avg_baseline_reward": 0.5943,
            "avg_cooperative_reward": 0.7233,
            "avg_reward_lift": 0.129,
            "avg_quality_lift": 0.21,
            "top_role": "risk_critic",
            "top_role_count": 3,
            "top_actor": "gonka",
            "top_actor_count": 3,
            "role_counts": {"risk_critic": 3},
            "actor_counts": {"gonka": 3},
        },
        "rows": [],
    }

    artifact = build_trail_run_from_batch(batch, task_id="test-trail-run")

    assert artifact["schema_version"] == "cognitive_trail_run.v0.1"
    assert artifact["task_id"] == "test-trail-run"
    assert artifact["task_type"] == "pr_review"
    assert artifact["status"] == "local_research_mvp"
    assert artifact["result"]["baseline_reward"] == 0.5943
    assert artifact["result"]["cooperative_reward"] == 0.7233
    assert artifact["result"]["lift"] == 0.129
    assert artifact["result"]["positive_lift"] is True
    assert artifact["result"]["top_role"] == "risk_critic"
    assert artifact["result"]["top_actor"] == "gonka"
    assert artifact["contribution_summary"]["top_role"] == artifact["result"]["top_role"]
    assert artifact["contribution_summary"]["top_actor"] == artifact["result"]["top_actor"]
    assert artifact["repeatability"]["should_repeat_route"] is True
    assert artifact["repeatability"]["needs_more_runs"] is True
    assert [step["step"] for step in artifact["route"]] == list(range(1, len(artifact["route"]) + 1))
    assert "risk_critic" in {step["role"] for step in artifact["route"]}
    assert "gonka" in {step["actor"] for step in artifact["route"]}


def test_build_trail_run_from_batch_handles_no_positive_lift() -> None:
    batch = {
        "artifact_type": "ls.pr_role_market_batch.v0.1",
        "repo": "/tmp/LS",
        "head": "HEAD",
        "last": 2,
        "attached_role_outputs": False,
        "summary": {
            "requested": 2,
            "analyzed": 2,
            "errors": 0,
            "positive_reward_lift": 0,
            "avg_baseline_reward": 0.75,
            "avg_cooperative_reward": 0.7,
            "avg_reward_lift": -0.05,
            "avg_quality_lift": -0.02,
            "top_role": "risk_critic",
            "top_role_count": 1,
            "top_actor": "gonka",
            "top_actor_count": 1,
            "role_counts": {"risk_critic": 1},
            "actor_counts": {"gonka": 1},
        },
        "rows": [],
    }

    artifact = build_trail_run_from_batch(batch, task_id="negative-lift")

    assert artifact["result"]["lift"] == -0.05
    assert artifact["result"]["positive_lift"] is False
    assert artifact["repeatability"]["should_repeat_route"] is False
    assert artifact["result"]["decision"] == "do_not_prefer_without_more_evidence"
