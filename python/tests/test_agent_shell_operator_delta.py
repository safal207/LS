from pathlib import Path

from ls.agent_shell.benchmarks.operator_delta import build_snapshot, parse_task_ids, ScenarioMeasurement


def test_parse_task_ids_deduplicates_cli_table_output() -> None:
    table = """
    | task-11111111 | Example A |
    | task-22222222 | Example B |
    | task-11111111 | Example A |
    """

    assert parse_task_ids(table) == ["task-11111111", "task-22222222"]


def test_build_snapshot_derives_speedup_and_command_reduction() -> None:
    snapshot = build_snapshot(
        queue_size=5,
        ltp_repo_root=Path("C:/tmp/_lthread_proto"),
        manual_review=ScenarioMeasurement(
            name="manual_cli_review",
            seconds=12.0,
            commands=11,
            tasks_reviewed=5,
            notes="manual",
        ),
        manual_ltp=ScenarioMeasurement(
            name="manual_ltp_review",
            seconds=34.0,
            commands=5,
            tasks_reviewed=5,
            notes="manual ltp",
        ),
        batch_ltp=ScenarioMeasurement(
            name="batch_ltp_review",
            seconds=30.0,
            commands=1,
            tasks_reviewed=5,
            notes="batch",
        ),
    )

    assert snapshot["summary"]["tasks_reviewed"] == 5
    assert snapshot["summary"]["seconds_saved_vs_manual_ltp"] == 4.0
    assert snapshot["summary"]["batch_speedup_vs_manual_ltp_pct"] == 11.76
    assert snapshot["summary"]["manual_review_commands"] == 11
    assert snapshot["summary"]["batch_review_commands"] == 1
    assert snapshot["summary"]["command_reduction_pct"] == 90.91
