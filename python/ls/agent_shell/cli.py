from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from ls.agent_shell.runtime.task_manager import TaskManager

app = typer.Typer(help="LS Agent Shell MVP CLI")
console = Console()


def manager() -> TaskManager:
    base = Path(".ls_agent")
    return TaskManager(db_path=base / "runtime.db", artifacts_root=base / "artifacts")


@app.command("run")
def run_task(prompt: str, approval: str = typer.Option("safe-write", "--approval")) -> None:
    task_id = manager().run_task(prompt=prompt, mode=approval)
    console.print(f"[green]Task started:[/green] {task_id}")


@app.command("plan")
def plan_task(prompt: str, mode: str = typer.Option("read-only", "--mode")) -> None:
    task, plan = manager().plan_only(prompt=prompt, mode=mode)
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
def status_task(task_id: str) -> None:
    data = manager().get_status(task_id)
    console.print(f"[bold]{task_id}[/bold] status={data['status']} mode={data['mode']}")
    steps = Table(title="Steps")
    steps.add_column("id")
    steps.add_column("title")
    steps.add_column("type")
    steps.add_column("status")
    for step in data["steps"]:
        steps.add_row(step["id"], step["title"], step["type"], step["status"])
    console.print(steps)


@app.command("resume")
def resume_task(task_id: str) -> None:
    manager().resume_task(task_id)
    console.print(f"[green]Resumed[/green] {task_id}")


@app.command("approve")
def approve_task(task_id: str, step_id: str) -> None:
    manager().approve(task_id, step_id)
    console.print(f"[green]Approved[/green] {step_id} for {task_id}")


@app.command("reject")
def reject_task(task_id: str, step_id: str, reason: str = typer.Option("No reason provided", "--reason")) -> None:
    manager().reject(task_id, step_id, reason)
    console.print(f"[yellow]Rejected[/yellow] {step_id} for {task_id}")


@app.command("artifacts")
def list_artifacts(task_id: str) -> None:
    artifacts = manager().list_artifacts(task_id)
    table = Table(title=f"Artifacts for {task_id}")
    table.add_column("id")
    table.add_column("title")
    table.add_column("type")
    table.add_column("path")
    for artifact in artifacts:
        table.add_row(artifact["id"], artifact["title"], artifact["type"], artifact["path_or_url"])
    console.print(table)


@app.command("trace")
def trace_task(task_id: str) -> None:
    logs = manager().get_trace(task_id)
    table = Table(title=f"Trace for {task_id}")
    table.add_column("time")
    table.add_column("level")
    table.add_column("step")
    table.add_column("message")
    for row in logs:
        table.add_row(row["created_at"], row["level"], row["step_id"] or "-", row["message"])
    console.print(table)


@app.command("list")
def list_tasks() -> None:
    tasks = manager().list_tasks()
    table = Table(title="Tasks")
    table.add_column("id")
    table.add_column("title")
    table.add_column("mode")
    table.add_column("status")
    for task in tasks:
        table.add_row(task["id"], task["title"], task["mode"], task["status"])
    console.print(table)


if __name__ == "__main__":
    app()
