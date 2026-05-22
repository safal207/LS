from __future__ import annotations

from copy import deepcopy
import json

from scripts.generate_pr_review_trail_run import build_trail_run_from_batch, render_trail_run_markdown
from scripts.validate_cognitive_trail_runs import DEFAULT_SCHEMA, validate_files


def _positive_batch() -> dict:
    return {
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


def _write_artifact(tmp_path, name: str, artifact: dict) -> object:
    output_path = tmp_path / name
    output_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def test_build_trail_run_from_batch_contract_shape() -> None:
    artifact = build_trail_run_from_batch(_positive_batch(), task_id="test-trail-run")

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


def test_generated_trail_run_validates_against_contract(tmp_path) -> None:
    artifact = build_trail_run_from_batch(_positive_batch(), task_id="validated-trail-run")
    output_path = _write_artifact(tmp_path, "validated_trail_run.json", artifact)

    assert validate_files(DEFAULT_SCHEMA, [output_path]) == 0


def test_invalid_trail_run_rejects_unknown_schema_fields(tmp_path, capsys) -> None:
    artifact = build_trail_run_from_batch(_positive_batch(), task_id="schema-invalid-trail-run")
    invalid_artifact = deepcopy(artifact)
    invalid_artifact["unexpected_reviewer_claim"] = "this field must not be accepted silently"
    output_path = _write_artifact(tmp_path, "schema_invalid_trail_run.json", invalid_artifact)

    assert validate_files(DEFAULT_SCHEMA, [output_path]) == 1

    stderr = capsys.readouterr().err
    assert "schema error at <root>" in stderr
    assert "Additional properties are not allowed" in stderr
    assert "unexpected_reviewer_claim" in stderr


def test_invalid_trail_run_rejects_inconsistent_lift(tmp_path, capsys) -> None:
    artifact = build_trail_run_from_batch(_positive_batch(), task_id="semantic-invalid-trail-run")
    invalid_artifact = deepcopy(artifact)
    invalid_artifact["result"]["lift"] = 999.0
    output_path = _write_artifact(tmp_path, "semantic_invalid_trail_run.json", invalid_artifact)

    assert validate_files(DEFAULT_SCHEMA, [output_path]) == 1

    stderr = capsys.readouterr().err
    assert "result.lift must equal cooperative_reward - baseline_reward" in stderr
    assert "got 999.0" in stderr


def test_invalid_trail_run_rejects_contribution_summary_mismatch(tmp_path, capsys) -> None:
    artifact = build_trail_run_from_batch(_positive_batch(), task_id="contribution-mismatch-trail-run")
    invalid_artifact = deepcopy(artifact)
    invalid_artifact["contribution_summary"]["top_role"] = "unsupported_role"
    invalid_artifact["contribution_summary"]["top_actor"] = "unsupported_actor"
    output_path = _write_artifact(tmp_path, "contribution_mismatch_trail_run.json", invalid_artifact)

    assert validate_files(DEFAULT_SCHEMA, [output_path]) == 1

    stderr = capsys.readouterr().err
    assert "contribution_summary.top_role must match result.top_role" in stderr
    assert "contribution_summary.top_actor must match result.top_actor" in stderr


def test_generated_trail_run_markdown_report_contains_reviewer_sections(tmp_path) -> None:
    artifact = build_trail_run_from_batch(_positive_batch(), task_id="markdown-trail-run")
    json_output_path = tmp_path / "markdown_trail_run.json"
    markdown = render_trail_run_markdown(artifact, json_output_path=json_output_path)

    assert "# LS Cognitive Trail Run Report" in markdown
    assert "Task ID: `markdown-trail-run`" in markdown
    assert "| Baseline reward | `0.5943` |" in markdown
    assert "| Cooperative reward | `0.7233` |" in markdown
    assert "| Lift | `+0.1290` |" in markdown
    assert "| Top role | `risk_critic` |" in markdown
    assert "| Top actor | `gonka` |" in markdown
    assert "## Route" in markdown
    assert "## Evidence" in markdown
    assert "## Repeatability" in markdown
    assert "## Non-Claims" in markdown
    assert "global model ranking" in markdown
    assert str(json_output_path) in markdown
