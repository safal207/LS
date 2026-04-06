from __future__ import annotations

from enum import Enum
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ls.agent_shell.mcp_http import run_http_server
from ls.agent_shell.mcp_server import run_stdio_server
from ls.agent_shell.runtime.task_manager import TaskManager

app = typer.Typer(help="LS Agent Shell MVP CLI")
console = Console()


class AccessMode(str, Enum):
    READ_ONLY = "read-only"
    SAFE_WRITE = "safe-write"
    FULL_AGENT = "full-agent"


class Transport(str, Enum):
    STDIO = "stdio"
    HTTP = "http"


def manager(runtime_root: Path) -> TaskManager:
    return TaskManager(
        db_path=runtime_root / "runtime.db",
        artifacts_root=runtime_root / "artifacts",
    )


def runtime_root_option() -> Path:
    return typer.Option(Path(".ls_agent"), "--runtime-root", help="Runtime state/artifact root.")


def _status_summary(data: dict) -> None:
    task_id = data.get("task_id") or data.get("id") or "unknown-task"
    console.print(
        f"[bold]{_safe_console_text(str(task_id))}[/bold] status={data['status']} mode={data['mode']}"
    )
    waiting_step = next((step for step in data["steps"] if step["status"] == "waiting_approval"), None)
    if waiting_step is not None:
        console.print(
            f"[yellow]Waiting approval:[/yellow] "
            f"{_safe_console_text(str(waiting_step['id']))} "
            f"({_safe_console_text(str(waiting_step['title']))})"
        )
    if data.get("summary"):
        console.print(f"[cyan]Summary:[/cyan] {_safe_console_text(str(data['summary']))}")

    steps = Table(title="Steps")
    steps.add_column("id")
    steps.add_column("title")
    steps.add_column("type")
    steps.add_column("status")
    for step in data["steps"]:
        steps.add_row(step["id"], step["title"], step["type"], step["status"])
    console.print(steps)


def _approval_table(approvals: list[dict], *, title: str) -> None:
    table = Table(title=title)
    table.add_column("id")
    table.add_column("task_id")
    table.add_column("step_id")
    table.add_column("action")
    table.add_column("status")
    table.add_column("reason")
    for approval in approvals:
        table.add_row(
            approval["id"],
            approval["task_id"],
            approval["step_id"],
            approval["action_type"],
            approval["status"],
            approval["reason"],
        )
    console.print(table)


def _open_path(target: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(target))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(target)], check=True)
        return
    subprocess.run(["xdg-open", str(target)], check=True)


def _safe_console_text(value: str) -> str:
    encoding = getattr(console.file, "encoding", None) or sys.stdout.encoding or "utf-8"
    try:
        value.encode(encoding)
        return value
    except UnicodeEncodeError:
        return value.encode(encoding, errors="backslashreplace").decode(encoding)


def _safe_path_text(path: Path) -> str:
    return _safe_console_text(str(path))


def _ltp_decision_from_event(task_status: str, event: dict[str, Any]) -> str:
    level = str(event.get("level") or "info")
    message = str(event.get("message") or "")
    if level == "error" or "rejected" in message.lower() or task_status in {"failed", "blocked"}:
        return "rejected"
    if level == "warning":
        return "drift"
    return "admissible"


def _build_ltp_trace_records(task: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    task_id = task.get("id") or task.get("task_id") or "unknown-task"
    prompt = str(task.get("prompt") or task.get("title") or "")
    task_status = str(task.get("status") or "unknown")
    records: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        step_id = event.get("step_id")
        anchors = [f"task:{task_id}", f"status:{task_status}"]
        if step_id:
            anchors.append(f"step:{step_id}")
        records.append(
            {
                "timestamp": event.get("created_at"),
                "input": prompt if index == 0 else f"task:{task_id}",
                "output": event.get("message"),
                "anchors": anchors,
                "decision": _ltp_decision_from_event(task_status, event),
            }
        )
    if not records:
        records.append(
            {
                "timestamp": None,
                "input": prompt,
                "output": f"No trace events available for {task_id}",
                "anchors": [f"task:{task_id}", f"status:{task_status}"],
                "decision": "drift",
            }
        )
    return records


def _write_ltp_trace_file(task: dict[str, Any], events: list[dict[str, Any]], destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    records = _build_ltp_trace_records(task, events)
    payload = "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
    destination.write_text(payload, encoding="utf-8")
    return destination


def _task_id_of(task: dict[str, Any]) -> str:
    return str(task.get("id") or task.get("task_id") or "unknown-task")


def _resolve_ltp_repo_root() -> Path:
    configured = os.getenv("LS_LTP_REPO_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4] / "_lthread_proto"


def _run_ltp_inspect(trace_file: Path, *, ltp_repo_root: Path) -> subprocess.CompletedProcess[str]:
    node = shutil.which("node")
    if not node:
        raise FileNotFoundError("node was not found in PATH; install Node.js to use ltp-inspect")
    ts_node_bin = ltp_repo_root / "node_modules" / "ts-node" / "dist" / "bin.js"
    inspect_script = ltp_repo_root / "tools" / "ltp-inspect" / "inspect.ts"
    if not ts_node_bin.exists():
        raise FileNotFoundError(
            f"LTP toolchain is missing at {_safe_path_text(ts_node_bin)}; run pnpm install in {_safe_path_text(ltp_repo_root)}"
        )
    if not inspect_script.exists():
        raise FileNotFoundError(
            f"LTP inspect script was not found at {_safe_path_text(inspect_script)}"
        )
    args = [
        node,
        str(ts_node_bin),
        str(inspect_script),
        "trace",
        "--phase",
        "two_phase",
        "--trace",
        str(trace_file),
        "--replay",
    ]
    return subprocess.run(
        args,
        cwd=str(ltp_repo_root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


@app.command("run")
def run_task(
    prompt: str,
    approval: AccessMode = typer.Option(AccessMode.SAFE_WRITE, "--approval"),
    runtime_root: Path = runtime_root_option(),
) -> None:
    task_id = manager(runtime_root).run_task(prompt=prompt, mode=approval.value)
    console.print(f"[green]Task started:[/green] {_safe_console_text(task_id)}")


@app.command("plan")
def plan_task(
    prompt: str,
    mode: AccessMode = typer.Option(AccessMode.READ_ONLY, "--mode"),
    runtime_root: Path = runtime_root_option(),
) -> None:
    task, plan = manager(runtime_root).plan_only(prompt=prompt, mode=mode.value)
    console.print(f"[cyan]Task:[/cyan] {_safe_console_text(task.id)}")
    table = Table(title="Execution Plan")
    table.add_column("Step")
    table.add_column("Type")
    table.add_column("Needs approval")
    table.add_column("Reason")
    for step in plan:
        table.add_row(step["id"], step["type"], str(step["needs_approval"]), step["reason"])
    console.print(table)


@app.command("status")
def status_task(task_id: str, runtime_root: Path = runtime_root_option()) -> None:
    _status_summary(manager(runtime_root).get_status(task_id))


@app.command("inspect")
def inspect_task(task_id: str, runtime_root: Path = runtime_root_option()) -> None:
    task_manager = manager(runtime_root)
    data = task_manager.get_status(task_id)
    _status_summary(data)

    trace = task_manager.get_trace(task_id)[-5:]
    trace_table = Table(title="Recent Trace")
    trace_table.add_column("time")
    trace_table.add_column("level")
    trace_table.add_column("step")
    trace_table.add_column("message")
    for row in trace:
        trace_table.add_row(row["created_at"], row["level"], row["step_id"] or "-", row["message"])
    console.print(trace_table)

    approvals = [step for step in data["steps"] if step["needs_approval"]]
    if approvals:
        approvals_table = Table(title="Approvals")
        approvals_table.add_column("step_id")
        approvals_table.add_column("title")
        approvals_table.add_column("status")
        for step in approvals:
            approvals_table.add_row(step["id"], step["title"], step["status"])
        console.print(approvals_table)

    artifacts = task_manager.list_artifacts(task_id)
    artifacts_table = Table(title="Artifacts")
    artifacts_table.add_column("id")
    artifacts_table.add_column("title")
    artifacts_table.add_column("type")
    artifacts_table.add_column("path")
    for artifact in artifacts:
        artifacts_table.add_row(
            artifact["id"],
            artifact["title"],
            artifact["type"],
            artifact["path_or_url"],
        )
    console.print(artifacts_table)


@app.command("resume")
def resume_task(task_id: str, runtime_root: Path = runtime_root_option()) -> None:
    manager(runtime_root).resume_task(task_id)
    console.print(f"[green]Resumed[/green] {_safe_console_text(task_id)}")


@app.command("approve")
def approve_task(task_id: str, step_id: str, runtime_root: Path = runtime_root_option()) -> None:
    manager(runtime_root).approve(task_id, step_id)
    console.print(
        f"[green]Approved[/green] {_safe_console_text(step_id)} for {_safe_console_text(task_id)}"
    )


@app.command("reject")
def reject_task(
    task_id: str,
    step_id: str,
    reason: str = typer.Option("No reason provided", "--reason"),
    runtime_root: Path = runtime_root_option(),
) -> None:
    manager(runtime_root).reject(task_id, step_id, reason)
    console.print(
        f"[yellow]Rejected[/yellow] {_safe_console_text(step_id)} for {_safe_console_text(task_id)}"
    )


@app.command("artifacts")
def list_artifacts(task_id: str, runtime_root: Path = runtime_root_option()) -> None:
    artifacts = manager(runtime_root).list_artifacts(task_id)
    table = Table(title=f"Artifacts for {task_id}")
    table.add_column("id")
    table.add_column("title")
    table.add_column("type")
    table.add_column("path")
    for artifact in artifacts:
        table.add_row(artifact["id"], artifact["title"], artifact["type"], artifact["path_or_url"])
    console.print(table)


@app.command("artifact")
def show_artifact(artifact_id: str, runtime_root: Path = runtime_root_option()) -> None:
    artifact = manager(runtime_root).get_artifact(artifact_id)
    console.print(
        f"[bold]{_safe_console_text(str(artifact['id']))}[/bold] "
        f"task={_safe_console_text(str(artifact['task_id']))} type={artifact['type']}"
    )
    console.print(f"[cyan]Title:[/cyan] {_safe_console_text(str(artifact['title']))}")
    console.print(f"[cyan]Path:[/cyan] {_safe_console_text(str(artifact['path_or_url']))}")


@app.command("artifact-open")
def open_artifact(artifact_id: str, runtime_root: Path = runtime_root_option()) -> None:
    artifact = manager(runtime_root).get_artifact(artifact_id)
    target = Path(artifact["path_or_url"])
    if not target.exists():
        raise typer.BadParameter(f"Artifact path does not exist: {target}")
    _open_path(target)
    console.print(f"[green]Opened[/green] {_safe_path_text(target)}")


@app.command("ltp-export")
def ltp_export(
    task_id: str,
    runtime_root: Path = runtime_root_option(),
    output: Path | None = typer.Option(None, "--output", help="Destination JSONL path."),
) -> None:
    task_manager = manager(runtime_root)
    task = task_manager.get_status(task_id)
    events = task_manager.get_trace(task_id)
    destination = output or (runtime_root / "ltp" / f"{task_id}.trace.jsonl")
    trace_file = _write_ltp_trace_file(task, events, destination)
    console.print(f"[green]LTP trace exported[/green] {_safe_path_text(trace_file)}")


@app.command("ltp-export-all")
def ltp_export_all(
    runtime_root: Path = runtime_root_option(),
    status: str | None = typer.Option(None, "--status", help="Filter tasks by status before export."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Destination directory for JSONL traces."),
) -> None:
    task_manager = manager(runtime_root)
    tasks = task_manager.list_tasks_filtered(status=status)
    if not tasks:
        console.print("[yellow]No tasks matched export filter.[/yellow]")
        raise typer.Exit(0)

    destination_root = output_dir or (runtime_root / "ltp" / "batch")
    destination_root.mkdir(parents=True, exist_ok=True)
    exported = 0
    for task in tasks:
        task_id = _task_id_of(task)
        task_detail = task_manager.get_status(task_id)
        events = task_manager.get_trace(task_id)
        trace_file = _write_ltp_trace_file(
            task_detail,
            events,
            destination_root / f"{task_id}.trace.jsonl",
        )
        console.print(
            f"[green]Exported[/green] {_safe_console_text(task_id)} -> {_safe_path_text(trace_file)}"
        )
        exported += 1
    console.print(f"[cyan]Batch export complete:[/cyan] {exported} trace file(s)")


@app.command("ltp-inspect")
def ltp_inspect_task(
    task_id: str,
    runtime_root: Path = runtime_root_option(),
    ltp_repo_root: Path | None = typer.Option(None, "--ltp-repo-root", help="Path to L-THREAD repo root."),
) -> None:
    task_manager = manager(runtime_root)
    task = task_manager.get_status(task_id)
    events = task_manager.get_trace(task_id)
    with tempfile.TemporaryDirectory(prefix="ls-agent-ltp-") as temp_dir:
        trace_file = _write_ltp_trace_file(task, events, Path(temp_dir) / f"{task_id}.trace.jsonl")
        repo_root = ltp_repo_root or _resolve_ltp_repo_root()
        if not repo_root.exists():
            raise typer.BadParameter(f"LTP repo root not found: {repo_root}")
        try:
            result = _run_ltp_inspect(trace_file, ltp_repo_root=repo_root)
        except FileNotFoundError as exc:
            raise typer.BadParameter(str(exc)) from exc
        if result.stdout:
            console.print(_safe_console_text(result.stdout.rstrip()))
        if result.returncode != 0:
            message = result.stderr.strip() or f"LTP inspect failed with exit code {result.returncode}"
            message = _safe_console_text(message)
            raise typer.BadParameter(message)


@app.command("trace")
def trace_task(task_id: str, runtime_root: Path = runtime_root_option()) -> None:
    logs = manager(runtime_root).get_trace(task_id)
    table = Table(title=f"Trace for {task_id}")
    table.add_column("time")
    table.add_column("level")
    table.add_column("step")
    table.add_column("message")
    for row in logs:
        table.add_row(row["created_at"], row["level"], row["step_id"] or "-", row["message"])
    console.print(table)


@app.command("list")
def list_tasks(
    runtime_root: Path = runtime_root_option(),
    status: str | None = typer.Option(None, "--status", help="Filter tasks by status."),
) -> None:
    tasks = manager(runtime_root).list_tasks_filtered(status=status)
    table = Table(title="Tasks")
    table.add_column("id")
    table.add_column("title")
    table.add_column("mode")
    table.add_column("status")
    for task in tasks:
        table.add_row(task["id"], task["title"], task["mode"], task["status"])
    console.print(table)


@app.command("approvals")
def approvals(
    task_id: str | None = typer.Option(None, "--task-id", help="Filter approvals by task id."),
    runtime_root: Path = runtime_root_option(),
) -> None:
    items = manager(runtime_root).list_approvals(task_id=task_id)
    title = f"Approvals for {task_id}" if task_id else "Approvals"
    _approval_table(items, title=title)


@app.command("serve")
def serve(
    transport: Transport = typer.Option(Transport.STDIO, "--transport"),
    runtime_root: Path = runtime_root_option(),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8042, "--port"),
) -> None:
    os.environ["LS_TASK_RUNTIME_ROOT"] = str(runtime_root)
    if transport is Transport.HTTP:
        console.print(f"[green]Serving HTTP MCP[/green] on http://{host}:{port}")
        console.print(f"[cyan]Runtime root:[/cyan] {_safe_path_text(runtime_root)}")
        run_http_server(host=host, port=port)
        return
    console.print("[green]Serving stdio MCP[/green]")
    console.print(f"[cyan]Runtime root:[/cyan] {_safe_path_text(runtime_root)}")
    raise typer.Exit(run_stdio_server())


if __name__ == "__main__":
    app()
