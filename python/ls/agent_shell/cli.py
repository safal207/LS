from __future__ import annotations

from enum import Enum
from pathlib import Path
import sys

import typer
from rich.console import Console
from rich.table import Table

from ls.agent_shell.runtime.task_manager import TaskManager

ROOT = Path(__file__).resolve().parents[3]
MODULES_ROOT = ROOT / "python" / "modules"
for candidate in (ROOT / "python", MODULES_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

try:
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.resonance_agent import ResonanceAgent

app = typer.Typer(help="LS Agent Shell MVP CLI")
console = Console()


class AccessMode(str, Enum):
    READ_ONLY = "read-only"
    SAFE_WRITE = "safe-write"
    FULL_AGENT = "full-agent"


def manager() -> TaskManager:
    base = Path(".ls_agent")
    return TaskManager(db_path=base / "runtime.db", artifacts_root=base / "artifacts")


def build_council_agent(orientation: str = "") -> ResonanceAgent:
    return ResonanceAgent(anchor=[], llm_fn=None, orientation=orientation or "cli-council-cycle")


@app.command("run")
def run_task(prompt: str, approval: AccessMode = typer.Option(AccessMode.SAFE_WRITE, "--approval")) -> None:
    task_id = manager().run_task(prompt=prompt, mode=approval.value)
    console.print(f"[green]Task started:[/green] {task_id}")


@app.command("plan")
def plan_task(prompt: str, mode: AccessMode = typer.Option(AccessMode.READ_ONLY, "--mode")) -> None:
    task, plan = manager().plan_only(prompt=prompt, mode=mode.value)
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


@app.command("council-cycle")
def council_cycle(
    prompt: str,
    orientation: str = typer.Option("", "--orientation", help="Optional council/orchestration context."),
    artifact_dir: Path = typer.Option(
        Path("artifacts/council-ledger"),
        "--artifact-dir",
        help="Where to write council-ledger JSON artifacts.",
    ),
) -> None:
    agent = build_council_agent(orientation=orientation)
    agent._council_ledger_dir = artifact_dir
    result = agent.process_text(prompt)
    ledger = result.get("council_contribution_ledger") or {}
    artifact_path = result.get("council_contribution_ledger_artifact")
    cycle_id = result.get("cycle_id", "unknown")
    verdict = "success" if ledger.get("outcome", {}).get("success") else "needs-review"
    route = ledger.get("final_decision", {}).get("selected_route", "unknown")
    contributor = (ledger.get("attribution") or {}).get("best_contributor_model_id", "n/a")
    console.print(f"[cyan]Council cycle:[/cyan] {cycle_id}")
    console.print(f"[green]Route:[/green] {route}    [green]Best contributor:[/green] {contributor}")
    console.print(f"[green]Outcome:[/green] {verdict}")
    if artifact_path:
        console.print(f"[bold]Ledger artifact:[/bold] {artifact_path}")
    console.print(result.get("final_output", ""))


if __name__ == "__main__":
    app()
