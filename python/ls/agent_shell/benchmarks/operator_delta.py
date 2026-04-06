from __future__ import annotations

from dataclasses import asdict, dataclass
import gc
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

from ls.agent_shell.runtime.task_manager import TaskManager


TASK_ID_RE = re.compile(r"task-[0-9a-f]{8}")


@dataclass
class ScenarioMeasurement:
    name: str
    seconds: float
    commands: int
    tasks_reviewed: int
    notes: str


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def default_ltp_repo_root() -> Path:
    configured = os.getenv("LS_LTP_REPO_ROOT")
    if configured:
        return Path(configured)
    return repo_root().parent / "_lthread_proto"


def parse_task_ids(list_stdout: str) -> list[str]:
    task_ids: list[str] = []
    for match in TASK_ID_RE.findall(list_stdout):
        if match not in task_ids:
            task_ids.append(match)
    return task_ids


def seed_waiting_tasks(runtime_root: Path, queue_size: int) -> list[str]:
    manager = TaskManager(db_path=runtime_root / "runtime.db", artifacts_root=runtime_root / "artifacts")
    task_ids: list[str] = []
    for index in range(queue_size):
        task_ids.append(manager.run_task(f"Operator delta benchmark task {index}", mode="safe-write"))
    return task_ids


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = "python" if not existing else f"python{os.pathsep}{existing}"
    return env


def _run_cli(args: list[str], *, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ls.agent_shell.cli", *args],
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )


def measure_manual_review(runtime_root: Path, *, env: dict[str, str]) -> ScenarioMeasurement:
    start = time.perf_counter()
    list_result = _run_cli(["list", "--status", "waiting_approval", "--runtime-root", str(runtime_root)], env=env)
    task_ids = parse_task_ids(list_result.stdout)
    for task_id in task_ids:
        _run_cli(["inspect", task_id, "--runtime-root", str(runtime_root)], env=env)
        _run_cli(["approvals", "--task-id", task_id, "--runtime-root", str(runtime_root)], env=env)
    elapsed = time.perf_counter() - start
    return ScenarioMeasurement(
        name="manual_cli_review",
        seconds=round(elapsed, 4),
        commands=1 + (len(task_ids) * 2),
        tasks_reviewed=len(task_ids),
        notes="Queue review through list + inspect + approvals per task.",
    )


def measure_manual_ltp(runtime_root: Path, *, env: dict[str, str], ltp_repo_root: Path) -> ScenarioMeasurement:
    list_result = _run_cli(["list", "--status", "waiting_approval", "--runtime-root", str(runtime_root)], env=env)
    task_ids = parse_task_ids(list_result.stdout)
    start = time.perf_counter()
    for task_id in task_ids:
        _run_cli(
            [
                "ltp-inspect",
                task_id,
                "--runtime-root",
                str(runtime_root),
                "--ltp-repo-root",
                str(ltp_repo_root),
            ],
            env=env,
        )
    elapsed = time.perf_counter() - start
    return ScenarioMeasurement(
        name="manual_ltp_review",
        seconds=round(elapsed, 4),
        commands=len(task_ids),
        tasks_reviewed=len(task_ids),
        notes="One LTP replay/inspect call per waiting task.",
    )


def measure_batch_ltp(runtime_root: Path, *, env: dict[str, str], ltp_repo_root: Path) -> ScenarioMeasurement:
    list_result = _run_cli(["list", "--status", "waiting_approval", "--runtime-root", str(runtime_root)], env=env)
    task_ids = parse_task_ids(list_result.stdout)
    start = time.perf_counter()
    _run_cli(
        [
            "ltp-inspect-all",
            "--status",
            "waiting_approval",
            "--runtime-root",
            str(runtime_root),
            "--ltp-repo-root",
            str(ltp_repo_root),
        ],
        env=env,
    )
    elapsed = time.perf_counter() - start
    return ScenarioMeasurement(
        name="batch_ltp_review",
        seconds=round(elapsed, 4),
        commands=1,
        tasks_reviewed=len(task_ids),
        notes="One queue-wide LTP replay/inspect pass for waiting approvals.",
    )


def build_snapshot(
    *,
    queue_size: int,
    ltp_repo_root: Path,
    manual_review: ScenarioMeasurement,
    manual_ltp: ScenarioMeasurement,
    batch_ltp: ScenarioMeasurement,
) -> dict[str, Any]:
    batch_speedup_pct = round(
        ((manual_ltp.seconds - batch_ltp.seconds) / manual_ltp.seconds) * 100.0,
        2,
    ) if manual_ltp.seconds else 0.0
    command_reduction_pct = round(
        ((manual_review.commands - batch_ltp.commands) / manual_review.commands) * 100.0,
        2,
    ) if manual_review.commands else 0.0
    return {
        "benchmark_name": "ls-agent-shell-operator-delta",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": {
            "platform": sys.platform,
            "python": sys.version.split()[0],
            "queue_size": queue_size,
            "ltp_repo_root": str(ltp_repo_root),
        },
        "scenarios": [asdict(manual_review), asdict(manual_ltp), asdict(batch_ltp)],
        "summary": {
            "tasks_reviewed": batch_ltp.tasks_reviewed,
            "seconds_saved_vs_manual_ltp": round(manual_ltp.seconds - batch_ltp.seconds, 4),
            "batch_speedup_vs_manual_ltp_pct": batch_speedup_pct,
            "manual_review_commands": manual_review.commands,
            "batch_review_commands": batch_ltp.commands,
            "command_reduction_pct": command_reduction_pct,
        },
        "investor_takeaway": {
            "with_ls": "One queue-wide replayable review path for waiting approvals.",
            "without_ls": "Operator hops across per-task review commands and ad-hoc handoff.",
            "legal_and_audit": [
                "Replayable task traces can be re-run outside the original agent session.",
                "Approval records remain attached to each task and step.",
                "Batch queue scan gives counsel/compliance a faster evidence pass before approval.",
            ],
            "disclaimer": "This is a local benchmark snapshot on one development machine, not a universal latency claim or legal opinion.",
        },
    }


def run_benchmark(*, queue_size: int = 5, ltp_repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root()
    runtime_root = Path(tempfile.mkdtemp(prefix="ls-agent-operator-delta-"))

    ltp_root = ltp_repo_root or default_ltp_repo_root()
    if not ltp_root.exists():
        raise FileNotFoundError(f"LTP repo root not found: {ltp_root}")

    previous_cwd = Path.cwd()
    os.chdir(root)
    try:
        seed_waiting_tasks(runtime_root, queue_size)
        env = _cli_env()
        manual_review = measure_manual_review(runtime_root, env=env)
        manual_ltp = measure_manual_ltp(runtime_root, env=env, ltp_repo_root=ltp_root)
        batch_ltp = measure_batch_ltp(runtime_root, env=env, ltp_repo_root=ltp_root)
        return build_snapshot(
            queue_size=queue_size,
            ltp_repo_root=ltp_root,
            manual_review=manual_review,
            manual_ltp=manual_ltp,
            batch_ltp=batch_ltp,
        )
    finally:
        os.chdir(previous_cwd)
        gc.collect()
        if runtime_root.exists():
            for _ in range(3):
                try:
                    shutil.rmtree(runtime_root)
                    break
                except PermissionError:
                    time.sleep(0.25)


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    output_path = repo_root() / "ghostgpt-ls-landing" / "src" / "data" / "operatorDeltaBenchmark.json"
    queue_size = 5
    if args:
        output_path = Path(args[0])
    if len(args) > 1:
        queue_size = int(args[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot = run_benchmark(queue_size=queue_size)
    output_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rendered = str(output_path).encode(sys.stdout.encoding or "utf-8", errors="backslashreplace").decode(
        sys.stdout.encoding or "utf-8"
    )
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
