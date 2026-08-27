from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from pathlib import Path

from ls.coordination_benchmark import (
    build_manifest,
    generate_safe_dry_run,
    verify_pilot,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_multi_session_coordination_pilot.py"
SCENARIO = (
    ROOT
    / "experiments"
    / "multi-session-coordination"
    / "canonical-five-session-scenario.json"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_dry_run_writes_explicit_non_observed_result(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "dry-run"

    completed = _run(
        "dry-run",
        "--run-dir",
        str(run_dir),
        "--run-id",
        "pilot-cli-dry-run",
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(
        (run_dir / "pilot-result.json").read_text(encoding="utf-8")
    )
    assert result["verdict"] == "PASS_SAFE_ROUTE_CONFIRMED"
    assert (
        result["evidence_mode"]
        == "DETERMINISTIC_DRY_RUN_NOT_OBSERVED"
    )
    assert len(list((run_dir / "traces").glob("*.jsonl"))) == 5


def test_cli_preserves_inconclusive_result_for_invalid_json(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "invalid-json"
    initialized = _run(
        "init",
        "--run-dir",
        str(run_dir),
        "--run-id",
        "pilot-cli-invalid",
    )
    assert initialized.returncode == 0, initialized.stderr
    (run_dir / "traces" / "database.jsonl").write_text(
        "{not-json}\n",
        encoding="utf-8",
    )

    completed = _run("verify", "--run-dir", str(run_dir))

    assert completed.returncode == 1
    result = json.loads(
        (run_dir / "pilot-result.json").read_text(encoding="utf-8")
    )
    assert result["verdict"] == "INCONCLUSIVE_UNBOUND_TRACE"
    assert result["evidence_mode"] == "OBSERVED_SESSION_TRACE"
    assert "not valid JSON" in result["violations"][0]


def test_action_must_bind_exact_receipt_and_release_records() -> None:
    scenario = json.loads(SCENARIO.read_text(encoding="utf-8"))
    manifest = build_manifest(scenario, run_id="pilot-binding-test")
    traces = generate_safe_dry_run(manifest)
    records = [
        copy.deepcopy(record)
        for session_records in traces.values()
        for record in session_records
    ]
    action = next(
        record
        for record in records
        if record["session_id"] == "database"
        and record["record_type"] == "ACTION_EXECUTED"
    )
    action["details"]["receipt_record_id"] = "coordinator:99:FAKE"

    result = verify_pilot(manifest, records)

    assert result["verdict"] == "FAIL_UNVERIFIED_RELEASE"
    assert "exact receipt/release binding" in result["violations"][0]
