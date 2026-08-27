from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_observed_coordination_pilot.py"


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


def _success(*args: str) -> subprocess.CompletedProcess[str]:
    completed = _run(*args)
    assert completed.returncode == 0, (
        f"command failed: {' '.join(args)}\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
    return completed


def _write_evidence(run_dir: Path, names: Iterable[str]) -> None:
    evidence_dir = run_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        (evidence_dir / name).write_text(
            json.dumps({"evidence": name, "status": "observed"}) + "\n",
            encoding="utf-8",
        )


def _execute_runtime(run_dir: Path, *, include_premature: bool) -> None:
    _success(
        "init",
        "--run-dir",
        str(run_dir),
        "--run-id",
        "observed-runtime-test",
    )
    _write_evidence(
        run_dir,
        (
            "migration-change.json",
            "endpoint-health.json",
            "database-action.json",
            "search-action.json",
            "dashboard-action.json",
        ),
    )

    for session_id in (
        "migration",
        "database",
        "search",
        "dashboard",
        "coordinator",
    ):
        _success(
            "start",
            "--run-dir",
            str(run_dir),
            "--session-id",
            session_id,
            "--instance-id",
            f"{session_id}-instance-1",
        )

    if include_premature:
        _success(
            "attempt-action",
            "--run-dir",
            str(run_dir),
            "--session-id",
            "database",
        )

    _success(
        "interrupt",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "search",
        "--kind",
        "compaction",
    )
    _success(
        "recover",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "search",
        "--instance-id",
        "search-instance-2",
    )
    _success(
        "interrupt",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "dashboard",
        "--kind",
        "replacement",
    )
    _success(
        "recover",
        "--run-dir",
        str(run_dir),
        "--session-id",
        "dashboard",
        "--instance-id",
        "dashboard-instance-2",
    )

    _success(
        "publish-valid",
        "--run-dir",
        str(run_dir),
        "--evidence-ref",
        "evidence/migration-change.json",
    )
    _success("inject-failures", "--run-dir", str(run_dir))

    for session_id in ("database", "search", "dashboard"):
        _success(
            "consume",
            "--run-dir",
            str(run_dir),
            "--session-id",
            session_id,
        )
        _success(
            "replan",
            "--run-dir",
            str(run_dir),
            "--session-id",
            session_id,
        )

    _success(
        "verify-receipt",
        "--run-dir",
        str(run_dir),
        "--evidence-ref",
        "evidence/endpoint-health.json",
    )
    _success("release", "--run-dir", str(run_dir))

    for session_id in ("database", "search", "dashboard"):
        _success(
            "attempt-action",
            "--run-dir",
            str(run_dir),
            "--session-id",
            session_id,
            "--evidence-ref",
            f"evidence/{session_id}-action.json",
        )

    for session_id in (
        "migration",
        "database",
        "search",
        "dashboard",
        "coordinator",
    ):
        _success(
            "finish",
            "--run-dir",
            str(run_dir),
            "--session-id",
            session_id,
        )


def test_full_observed_runtime_proves_global_order(tmp_path: Path) -> None:
    run_dir = tmp_path / "observed-pass"
    _execute_runtime(run_dir, include_premature=True)

    completed = _run("verify-observed", "--run-dir", str(run_dir))

    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads(
        (run_dir / "observed-result.json").read_text(encoding="utf-8")
    )
    assert result["verdict"] == "PASS_OBSERVED_RUNTIME_CONFIRMED"
    assert result["evidence_mode"] == "OBSERVED_RUNTIME_BOUND_TRACE"
    assert result["metrics"]["transport_record_count"] == 4
    assert result["metrics"]["premature_blocked_action_count"] == 1
    assert result["metrics"]["executed_action_count"] == 3


def test_base_safe_trace_without_premature_proof_is_rejected(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "missing-premature"
    _execute_runtime(run_dir, include_premature=False)

    completed = _run("verify-observed", "--run-dir", str(run_dir))

    assert completed.returncode == 1
    result = json.loads(
        (run_dir / "observed-result.json").read_text(encoding="utf-8")
    )
    assert result["verdict"] == "FAIL_OBSERVED_RUNTIME_EVIDENCE"
    assert "premature blocked action" in result["violations"][0]
    assert (
        result["base_result"]["verdict"]
        == "PASS_SAFE_ROUTE_CONFIRMED"
    )


def test_transport_hash_tampering_is_rejected(tmp_path: Path) -> None:
    run_dir = tmp_path / "tampered-transport"
    _execute_runtime(run_dir, include_premature=True)
    path = run_dir / "transport" / "events.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["event"]["payload"]["new_value"] = "203.0.113.200"
    lines[0] = json.dumps(first, sort_keys=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    completed = _run("verify-observed", "--run-dir", str(run_dir))

    assert completed.returncode == 1
    result = json.loads(
        (run_dir / "observed-result.json").read_text(encoding="utf-8")
    )
    assert result["verdict"] == "FAIL_OBSERVED_RUNTIME_EVIDENCE"
    assert "record_hash mismatch" in result["violations"][0]


def test_trace_claim_without_audit_binding_is_rejected(tmp_path: Path) -> None:
    run_dir = tmp_path / "unbound-trace"
    _execute_runtime(run_dir, include_premature=True)
    path = run_dir / "traces" / "database.jsonl"
    records = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    accepted = next(
        item for item in records if item["record_type"] == "EVENT_ACCEPTED"
    )
    accepted["details"].pop("audit_hash")
    path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )

    completed = _run("verify-observed", "--run-dir", str(run_dir))

    assert completed.returncode == 1
    result = json.loads(
        (run_dir / "observed-result.json").read_text(encoding="utf-8")
    )
    assert result["verdict"] == "FAIL_OBSERVED_RUNTIME_EVIDENCE"
    assert "audit binding mismatch" in result["violations"][0]
