from __future__ import annotations

from enum import Enum
import os
from pathlib import Path

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
    console.print(f"[bold]{task_id}[/bold] status={data['status']} mode={data['mode']}")
    waiting_step = next((step for step in data["steps"] if step["status"] == "waiting_approval"), None)
    if waiting_step is not None:
        console.print(f"[yellow]Waiting approval:[/yellow] {waiting_step['id']} ({waiting_step['title']})")
    if data.get("summary"):
        console.print(f"[cyan]Summary:[/cyan] {data['summary']}")

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


@app.command("run")
def run_task(
    prompt: str,
    approval: AccessMode = typer.Option(AccessMode.SAFE_WRITE, "--approval"),
    runtime_root: Path = runtime_root_option(),
) -> None:
    task_id = manager(runtime_root).run_task(prompt=prompt, mode=approval.value)
    console.print(f"[green]Task started:[/green] {task_id}")


@app.command("plan")
def plan_task(
    prompt: str,
    mode: AccessMode = typer.Option(AccessMode.READ_ONLY, "--mode"),
    runtime_root: Path = runtime_root_option(),
) -> None:
    task, plan = manager(runtime_root).plan_only(prompt=prompt, mode=mode.value)
    console.print(f"[cyan]Task:[/cyan] {task.id}")
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
    console.print(f"[green]Resumed[/green] {task_id}")


@app.command("approve")
def approve_task(task_id: str, step_id: str, runtime_root: Path = runtime_root_option()) -> None:
    manager(runtime_root).approve(task_id, step_id)
    console.print(f"[green]Approved[/green] {step_id} for {task_id}")


@app.command("reject")
def reject_task(
    task_id: str,
    step_id: str,
    reason: str = typer.Option("No reason provided", "--reason"),
    runtime_root: Path = runtime_root_option(),
) -> None:
    manager(runtime_root).reject(task_id, step_id, reason)
    console.print(f"[yellow]Rejected[/yellow] {step_id} for {task_id}")


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
    console.print(f"[bold]{artifact['id']}[/bold] task={artifact['task_id']} type={artifact['type']}")
    console.print(f"[cyan]Title:[/cyan] {artifact['title']}")
    console.print(f"[cyan]Path:[/cyan] {artifact['path_or_url']}")


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
        run_http_server(host=host, port=port)
        return
    console.print("[green]Serving stdio MCP[/green]")
    raise typer.Exit(run_stdio_server())


if __name__ == "__main__":
    app()
