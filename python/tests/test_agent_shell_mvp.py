from pathlib import Path
import json

from ls.agent_shell.runtime.task_manager import TaskManager
from typer.testing import CliRunner

from ls.agent_shell import cli
from ls.agent_shell.cli import app


def test_plan_only_creates_steps(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task, plan = manager.plan_only("Сделай investor opening slide для LS", mode="safe-write")

    assert task.id.startswith("task-")
    assert len(plan) == 5
    assert any(step["needs_approval"] for step in plan)
    assert all(step["id"].startswith(task.id) for step in plan)


def test_two_tasks_in_same_db_have_unique_step_ids(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")

    first, first_plan = manager.plan_only("Task one", mode="safe-write")
    second, second_plan = manager.plan_only("Task two", mode="safe-write")

    assert first.id != second.id
    first_ids = {step["id"] for step in first_plan}
    second_ids = {step["id"] for step in second_plan}
    assert first_ids.isdisjoint(second_ids)


def test_run_waits_for_approval_and_can_resume(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task_id = manager.run_task("Проверь PR #387 и дай review", mode="safe-write")

    status = manager.get_status(task_id)
    assert status["status"] == "waiting_approval"
    blocked_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    manager.approve(task_id, blocked_step["id"])

    resumed = manager.get_status(task_id)
    assert resumed["status"] == "completed"
    artifacts = manager.list_artifacts(task_id)
    assert artifacts


def test_reject_moves_to_blocked(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task_id = manager.run_task("Draft docs", mode="safe-write")
    status = manager.get_status(task_id)
    blocked_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    manager.reject(task_id, blocked_step["id"], "Need diff first")

    status_after = manager.get_status(task_id)
    assert status_after["status"] == "blocked"


def test_reject_then_resume_is_blocked(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task_id = manager.run_task("Draft docs", mode="safe-write")
    status = manager.get_status(task_id)
    blocked_step = next(step for step in status["steps"] if step["status"] == "waiting_approval")

    manager.reject(task_id, blocked_step["id"], "Need diff first")

    try:
        manager.resume_task(task_id)
        assert False, "resume_task should fail for blocked tasks"
    except ValueError as exc:
        assert "cannot be resumed" in str(exc)


def test_read_only_never_schedules_mutating_steps(tmp_path: Path) -> None:
    manager = TaskManager(db_path=tmp_path / "runtime.db", artifacts_root=tmp_path / "artifacts")
    task, plan = manager.plan_only("Проверь PR #387 и дай review", mode="read-only")

    mutating = {"write", "git", "browser", "tool", "artifact"}
    assert task.id.startswith("task-")
    assert plan
    assert not any(step["type"] in mutating for step in plan)


def test_council_cycle_cli_emits_ledger_artifact(tmp_path: Path) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "council-ledger"

    result = runner.invoke(
        app,
        [
            "council-cycle",
            "Help the operator align the council response",
            "--llm-mode",
            "dry-run",
            "--artifact-dir",
            str(artifact_dir),
            "--orientation",
            "test-coordination",
        ],
    )

    assert result.exit_code == 0
    assert "Council cycle:" in result.stdout
    assert "Risk:" in result.stdout
    assert "Suggested action:" in result.stdout
    assert "Ledger artifact:" in result.stdout
    artifacts = list(artifact_dir.glob("*.json"))
    assert artifacts


def test_council_cycle_cli_can_publish_to_liminalqa(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "council-ledger"

    def fake_publish(ledger: dict) -> tuple[int, object]:
        assert ledger["cycle_id"]
        return 200, {"ok": True, "message": "published"}

    monkeypatch.setattr(cli, "publish_council_ledger_to_liminalqa", fake_publish)

    result = runner.invoke(
        app,
        [
            "council-cycle",
            "Publish this council cycle",
            "--llm-mode",
            "dry-run",
            "--artifact-dir",
            str(artifact_dir),
            "--publish-to-liminalqa",
        ],
    )

    assert result.exit_code == 0
    assert "LiminalQA publish:" in result.stdout
    assert "HTTP 200" in result.stdout
    quality_artifacts = list((tmp_path / "council-quality").glob("*.json"))
    assert quality_artifacts
    quality_payload = json.loads(quality_artifacts[0].read_text(encoding="utf-8"))
    assert quality_payload["liminalqa"]["published"] is True
    assert quality_payload["liminalqa"]["status_code"] == 200
    assert quality_payload["liminalqa"]["response"]["ok"] is True


def test_council_cycle_cli_auto_publishes_incident_for_risky_cycle(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "council-ledger"
    calls: list[str] = []

    class FakeAgent:
        def __init__(self) -> None:
            self._council_ledger_dir = artifact_dir
            self._council_quality_dir = tmp_path / "council-quality"

        def process_text(self, _prompt: str) -> dict:
            self._council_ledger_dir.mkdir(parents=True, exist_ok=True)
            self._council_quality_dir.mkdir(parents=True, exist_ok=True)
            ledger_path = self._council_ledger_dir / "cycle-risky.json"
            quality_path = self._council_quality_dir / "cycle-risky.json"
            ledger = {
                "cycle_id": "cycle-risky",
                "final_decision": {"selected_route": "route-risk"},
                "attribution": {"best_contributor_model_id": "local-council-llm"},
                "outcome": {"success": False},
                "participants": [],
            }
            quality = {
                "cycle_id": "cycle-risky",
                "timestamp": "2026-04-09T11:00:00Z",
                "quality_score": 0.41,
                "council_outcome": {"selected_route": "route-risk", "receiver_resonance_score": 0.22},
                "relational_field": {"recommended_mode": "decompress_and_repair"},
                "operator_guidance": {
                    "risk_state": "repair",
                    "suggested_operator_action": "Pause approval and repair.",
                },
                "liminalqa": {"published": False, "status_code": None},
            }
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            quality_path.write_text(json.dumps(quality), encoding="utf-8")
            return {
                "cycle_id": "cycle-risky",
                "council_contribution_ledger": ledger,
                "council_contribution_ledger_artifact": str(ledger_path),
                "council_quality_artifact": str(quality_path),
                "final_output": "Risky council output",
            }

    def fake_publish(ledger: dict) -> tuple[int, object]:
        calls.append("ledger")
        return 200, {"ok": True, "message": "published"}

    def fake_incident(quality_payload: dict) -> tuple[int, object]:
        calls.append(str((quality_payload.get("operator_guidance") or {}).get("risk_state")))
        return 200, {"ok": True, "message": "incident-published"}

    monkeypatch.setattr(cli, "build_council_agent", lambda orientation="", llm_mode=cli.CouncilLLMMode.AUTO: FakeAgent())
    monkeypatch.setattr(cli, "publish_council_ledger_to_liminalqa", fake_publish)
    monkeypatch.setattr(cli, "publish_council_incident_to_liminalqa", fake_incident)

    result = runner.invoke(
        app,
        [
            "council-cycle",
            "Publish this risky council cycle",
            "--llm-mode",
            "dry-run",
            "--artifact-dir",
            str(artifact_dir),
            "--publish-to-liminalqa",
        ],
    )

    assert result.exit_code == 0
    assert "LiminalQA publish:" in result.stdout
    assert "LiminalQA incident:" in result.stdout
    assert calls[0] == "ledger"
    assert calls[1] in {"repair", "escalate"}
    quality_artifacts = list((tmp_path / "council-quality").glob("*.json"))
    assert quality_artifacts
    quality_payload = json.loads(quality_artifacts[0].read_text(encoding="utf-8"))
    assert quality_payload["liminalqa"]["incident"]["published"] is True
    assert quality_payload["liminalqa"]["incident"]["status_code"] == 200


def test_council_cycle_cli_can_use_local_llm_mode(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    artifact_dir = tmp_path / "council-ledger"

    def fake_llm(_user: str, _system: str) -> str:
        return "Local council answer"

    monkeypatch.setattr(cli, "build_local_council_llm_fn", lambda: fake_llm)

    result = runner.invoke(
        app,
        [
            "council-cycle",
            "Use a real local council cycle",
            "--llm-mode",
            "local",
            "--artifact-dir",
            str(artifact_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Council cycle:" in result.stdout
    assert "Ledger artifact:" in result.stdout
    artifacts = list(artifact_dir.glob("*.json"))
    assert artifacts


def test_council_review_prioritizes_risk_states(tmp_path: Path) -> None:
    runner = CliRunner()
    quality_dir = tmp_path / "council-quality"
    quality_dir.mkdir()
    (quality_dir / "safe.json").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-safe",
                "timestamp": "2026-04-09T10:00:00Z",
                "quality_score": 0.91,
                "council_outcome": {"selected_route": "route-a"},
                "relational_field": {"recommended_mode": "collaborative_progress"},
                "operator_guidance": {
                    "risk_state": "safe",
                    "suggested_operator_action": "Safe to continue.",
                },
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "repair.json").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-repair",
                "timestamp": "2026-04-09T11:00:00Z",
                "relation_adjusted_quality_score": 0.41,
                "council_outcome": {"selected_route": "route-b"},
                "relational_field": {"recommended_mode": "decompress_and_repair"},
                "operator_guidance": {
                    "risk_state": "repair",
                    "suggested_operator_action": "Pause approval and repair.",
                },
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["council-review", "--quality-dir", str(quality_dir)])

    assert result.exit_code == 0
    assert "Council Review Queue" in result.stdout
    assert result.stdout.index("cycle-repair") < result.stdout.index("cycle-safe")


def test_council_review_can_filter_risk_states(tmp_path: Path) -> None:
    runner = CliRunner()
    quality_dir = tmp_path / "council-quality"
    quality_dir.mkdir()
    for cycle_id, risk_state in (("cycle-safe", "safe"), ("cycle-escalate", "escalate")):
        (quality_dir / f"{cycle_id}.json").write_text(
            json.dumps(
                {
                    "cycle_id": cycle_id,
                    "timestamp": "2026-04-09T10:00:00Z",
                    "quality_score": 0.5,
                    "council_outcome": {"selected_route": "route-a"},
                    "relational_field": {"recommended_mode": "observe_and_clarify"},
                    "operator_guidance": {
                        "risk_state": risk_state,
                        "suggested_operator_action": "act",
                    },
                }
            ),
            encoding="utf-8",
        )

    result = runner.invoke(app, ["council-review", "--quality-dir", str(quality_dir), "--only-risk", "escalate"])

    assert result.exit_code == 0
    assert "cycle-escalate" in result.stdout
    assert "cycle-safe" not in result.stdout


def test_council_review_can_emit_json_and_fail_on_risk(tmp_path: Path) -> None:
    runner = CliRunner()
    quality_dir = tmp_path / "council-quality"
    quality_dir.mkdir()
    for cycle_id, risk_state in (("cycle-watch", "watch"), ("cycle-repair", "repair")):
        (quality_dir / f"{cycle_id}.json").write_text(
            json.dumps(
                {
                    "cycle_id": cycle_id,
                    "timestamp": "2026-04-09T10:00:00Z",
                    "quality_score": 0.5,
                    "council_outcome": {"selected_route": "route-a"},
                    "relational_field": {"recommended_mode": "observe_and_clarify"},
                    "operator_guidance": {
                        "risk_state": risk_state,
                        "suggested_operator_action": "act",
                    },
                }
            ),
            encoding="utf-8",
        )

    result = runner.invoke(
        app,
        ["council-review", "--quality-dir", str(quality_dir), "--json", "--fail-on-risk"],
    )

    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["highest_risk"] == "repair"
    assert payload["risk_counts"]["repair"] == 1
    assert payload["items"][0]["cycle_id"] == "cycle-repair"


def test_council_review_json_handles_empty_queue(tmp_path: Path) -> None:
    runner = CliRunner()
    quality_dir = tmp_path / "council-quality"
    quality_dir.mkdir()

    result = runner.invoke(app, ["council-review", "--quality-dir", str(quality_dir), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["total"] == 0
    assert payload["highest_risk"] == "safe"
    assert payload["items"] == []
