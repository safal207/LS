from __future__ import annotations

from enum import Enum
from pathlib import Path
import sys
import json
import os
import urllib.error
import urllib.request
import requests

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


def print_plain_safe(text: str) -> None:
    output = str(text or "")
    try:
        console.print(output)
    except UnicodeEncodeError:
        stream = getattr(sys.stdout, "buffer", None)
        safe_bytes = (output + "\n").encode("cp1252", errors="replace")
        if stream is not None:
            stream.write(safe_bytes)
            stream.flush()
        else:
            sys.stdout.write(safe_bytes.decode("cp1252", errors="replace"))


class AccessMode(str, Enum):
    READ_ONLY = "read-only"
    SAFE_WRITE = "safe-write"
    FULL_AGENT = "full-agent"


class CouncilLLMMode(str, Enum):
    AUTO = "auto"
    DRY_RUN = "dry-run"
    LOCAL = "local"


def _council_risk_rank(risk_state: str) -> int:
    order = {
        "escalate": 0,
        "repair": 1,
        "watch": 2,
        "safe": 3,
    }
    return order.get(str(risk_state or "watch"), 2)


def load_council_quality_rows(quality_dir: Path) -> list[dict]:
    rows: list[dict] = []
    if not quality_dir.exists():
        return rows
    for path in quality_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        payload["_path"] = str(path)
        rows.append(payload)
    rows.sort(
        key=lambda item: (
            _council_risk_rank((item.get("operator_guidance") or {}).get("risk_state", "watch")),
            str(item.get("timestamp") or ""),
        )
    )
    return rows


def manager() -> TaskManager:
    base = Path(".ls_agent")
    return TaskManager(db_path=base / "runtime.db", artifacts_root=base / "artifacts")


def build_local_council_llm_fn():
    try:
        from config import OLLAMA_HOST, LLM_MODEL_NAME
    except ImportError:
        from modules.config import OLLAMA_HOST, LLM_MODEL_NAME

    candidate_hosts = []
    for host in ("http://127.0.0.1:11434", OLLAMA_HOST, "http://localhost:11434"):
        if host and host not in candidate_hosts:
            candidate_hosts.append(host.rstrip("/"))

    session = requests.Session()
    working_host = None
    for host in candidate_hosts:
        try:
            response = session.post(
                f"{host}/api/chat",
                json={
                    "model": LLM_MODEL_NAME,
                    "messages": [{"role": "user", "content": "Say only: ok"}],
                    "stream": False,
                    "options": {"temperature": 0.0, "num_predict": 8},
                },
                timeout=15,
            )
            response.raise_for_status()
            working_host = host
            break
        except Exception:
            continue
    if not working_host:
        raise RuntimeError("Local Ollama backend is unavailable.")

    def _call(user_prompt: str, system_prompt: str) -> str:
        payload = {
            "model": LLM_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": 256},
        }
        response = session.post(
            f"{working_host}/api/chat",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        return str((((body or {}).get("message") or {}).get("content")) or "")

    return _call


def build_council_agent(
    orientation: str = "",
    *,
    llm_mode: CouncilLLMMode = CouncilLLMMode.AUTO,
) -> ResonanceAgent:
    llm_fn = None
    if llm_mode is CouncilLLMMode.LOCAL:
        llm_fn = build_local_council_llm_fn()
    elif llm_mode is CouncilLLMMode.AUTO:
        try:
            llm_fn = build_local_council_llm_fn()
        except Exception:
            llm_fn = None
    return ResonanceAgent(anchor=[], llm_fn=llm_fn, orientation=orientation or "cli-council-cycle")


def liminalqa_settings() -> tuple[str, str]:
    return (
        os.environ.get("LIMINALQA_URL", "http://127.0.0.1:8080").rstrip("/"),
        os.environ.get("LIMINALQA_TOKEN", "devtoken"),
    )


def publish_council_ledger_to_liminalqa(ledger: dict) -> tuple[int, object]:
    base_url, token = liminalqa_settings()
    generated_at = ledger.get("timestamp") or "1970-01-01T00:00:00Z"
    cycle_id = str(ledger.get("cycle_id", "unknown"))
    attribution = ledger.get("attribution") or {}
    outcome = ledger.get("outcome") or {}
    final_decision = ledger.get("final_decision") or {}

    tests = []
    signals = []
    for participant in ledger.get("participants", []):
        model_id = str(participant.get("model_id", "unknown"))
        model_type = str(participant.get("model_type", "unknown"))
        selected = bool(participant.get("selected"))
        contribution_score = 0.0
        for item in attribution.get("contribution_breakdown", []):
            if str(item.get("model_id")) == model_id:
                contribution_score = float(item.get("total_contribution_score") or 0.0)
                break
        tests.append(
            {
                "name": model_id,
                "suite": "ls.council.contribution",
                "guidance": model_type,
                "status": "pass" if selected else "skip",
                "duration_ms": participant.get("latency_ms"),
                "started_at": generated_at,
                "completed_at": generated_at,
            }
        )
        signals.append(
            {
                "test_name": model_id,
                "kind": "system",
                "value": contribution_score,
                "meta": {
                    "cycle_id": cycle_id,
                    "model_type": model_type,
                    "selected_route": final_decision.get("selected_route"),
                    "selected": selected,
                    "receiver_resonance_score": outcome.get("receiver_resonance_score"),
                    "network_improvement": outcome.get("network_improvement"),
                    "best_contributor_model_id": attribution.get("best_contributor_model_id"),
                    "source": "ls-agent-shell-cli",
                },
                "at": generated_at,
            }
        )

    payload = {
        "run": {
            "run_id": cycle_id,
            "build_id": cycle_id,
            "plan_name": "ls-council-cycle",
            "env": {
                "CI": "false",
                "SOURCE": "ls-agent-shell-cli",
                "COUNCIL_ROUTE": str(final_decision.get("selected_route", "unknown")),
            },
            "started_at": generated_at,
            "runner_version": "ls-agent-shell-council-v1",
        },
        "tests": tests,
        "signals": signals,
        "artifacts": [],
    }
    request = urllib.request.Request(
        f"{base_url}/ingest/batch",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": body or str(exc)}
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": str(exc)}


def publish_council_incident_to_liminalqa(quality_payload: dict) -> tuple[int, object]:
    base_url, token = liminalqa_settings()
    generated_at = quality_payload.get("timestamp") or "1970-01-01T00:00:00Z"
    cycle_id = str(quality_payload.get("cycle_id", "unknown"))
    outcome = quality_payload.get("council_outcome") or {}
    guidance = quality_payload.get("operator_guidance") or {}
    relational = quality_payload.get("relational_field") or {}
    payload = {
        "run": {
            "run_id": f"{cycle_id}-incident",
            "build_id": f"{cycle_id}-incident",
            "plan_name": "ls-council-incident",
            "env": {
                "CI": "false",
                "SOURCE": "ls-agent-shell-cli",
                "COUNCIL_ROUTE": str(outcome.get("selected_route", "unknown")),
                "COUNCIL_RISK_STATE": str(guidance.get("risk_state", "watch")),
            },
            "started_at": generated_at,
            "runner_version": "ls-agent-shell-council-incident-v1",
        },
        "tests": [
            {
                "name": f"incident:{cycle_id}",
                "suite": "ls.council.incident",
                "guidance": str(guidance.get("suggested_operator_action") or "manual review"),
                "status": "fail",
                "duration_ms": 0,
                "started_at": generated_at,
                "completed_at": generated_at,
            }
        ],
        "signals": [
            {
                "test_name": f"incident:{cycle_id}",
                "kind": "system",
                "value": float(quality_payload.get("relation_adjusted_quality_score") or quality_payload.get("quality_score") or 0.0),
                "meta": {
                    "cycle_id": cycle_id,
                    "risk_state": guidance.get("risk_state"),
                    "recommended_mode": relational.get("recommended_mode"),
                    "selected_route": outcome.get("selected_route"),
                    "receiver_resonance_score": outcome.get("receiver_resonance_score"),
                    "source": "ls-agent-shell-cli-incident",
                },
                "at": generated_at,
            }
        ],
        "artifacts": [],
    }
    request = urllib.request.Request(
        f"{base_url}/ingest/batch",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except Exception:
            return exc.code, {"error": body or str(exc)}
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": str(exc)}


def update_council_quality_artifact_publish_status(
    council_quality_artifact: str | Path | None,
    *,
    status_code: int,
    response: object,
) -> str | None:
    if not council_quality_artifact:
        return None
    path = Path(council_quality_artifact)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    payload["liminalqa"] = {
        "published": 200 <= int(status_code) < 300,
        "status_code": int(status_code),
        "response": response,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def update_council_quality_artifact_incident_status(
    council_quality_artifact: str | Path | None,
    *,
    status_code: int,
    response: object,
) -> str | None:
    if not council_quality_artifact:
        return None
    path = Path(council_quality_artifact)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    liminalqa = payload.get("liminalqa") or {}
    liminalqa["incident"] = {
        "published": 200 <= int(status_code) < 300,
        "status_code": int(status_code),
        "response": response,
    }
    payload["liminalqa"] = liminalqa
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


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


@app.command("council-review")
def council_review(
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read council-quality JSON artifacts.",
    ),
    only_risk: str = typer.Option(
        "",
        "--only-risk",
        help="Comma-separated risk states to include, e.g. escalate,repair.",
    ),
) -> None:
    rows = load_council_quality_rows(quality_dir)
    allowed_risks = {item.strip() for item in only_risk.split(",") if item.strip()}
    if allowed_risks:
        rows = [
            row
            for row in rows
            if str((row.get("operator_guidance") or {}).get("risk_state") or "watch") in allowed_risks
        ]
    if not rows:
        console.print("[yellow]No council-quality artifacts found.[/yellow]")
        raise typer.Exit(code=0)
    table = Table(title="Council Review Queue")
    table.add_column("cycle")
    table.add_column("risk")
    table.add_column("mode")
    table.add_column("route")
    table.add_column("quality")
    table.add_column("action")
    for row in rows:
        guidance = row.get("operator_guidance") or {}
        relational = row.get("relational_field") or {}
        outcome = row.get("council_outcome") or {}
        quality_score = row.get("relation_adjusted_quality_score")
        if quality_score is None:
            quality_score = row.get("quality_score")
        table.add_row(
            str(row.get("cycle_id") or "n/a"),
            str(guidance.get("risk_state") or "watch"),
            str(relational.get("recommended_mode") or "n/a"),
            str(outcome.get("selected_route") or "unknown"),
            "n/a" if quality_score is None else f"{float(quality_score):.4f}",
            str(guidance.get("suggested_operator_action") or "n/a"),
        )
    console.print(table)


@app.command("council-cycle")
def council_cycle(
    prompt: str,
    orientation: str = typer.Option("", "--orientation", help="Optional council/orchestration context."),
    llm_mode: CouncilLLMMode = typer.Option(
        CouncilLLMMode.AUTO,
        "--llm-mode",
        help="Choose whether to use a real local LLM, dry-run mode, or auto fallback.",
    ),
    artifact_dir: Path = typer.Option(
        Path("artifacts/council-ledger"),
        "--artifact-dir",
        help="Where to write council-ledger JSON artifacts.",
    ),
    publish_to_liminalqa: bool = typer.Option(
        False,
        "--publish-to-liminalqa",
        help="Also publish the generated council ledger into LiminalQA ingest.",
    ),
) -> None:
    try:
        agent = build_council_agent(orientation=orientation, llm_mode=llm_mode)
    except Exception as exc:
        console.print(f"[red]Council agent init failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc
    agent._council_ledger_dir = artifact_dir
    agent._council_quality_dir = artifact_dir.parent / "council-quality"
    result = agent.process_text(prompt)
    ledger = result.get("council_contribution_ledger") or {}
    artifact_path = result.get("council_contribution_ledger_artifact")
    council_quality_artifact = result.get("council_quality_artifact")
    quality_payload = {}
    if council_quality_artifact:
        try:
            quality_payload = json.loads(Path(council_quality_artifact).read_text(encoding="utf-8"))
        except Exception:
            quality_payload = {}
    cycle_id = result.get("cycle_id", "unknown")
    verdict = "success" if ledger.get("outcome", {}).get("success") else "needs-review"
    route = ledger.get("final_decision", {}).get("selected_route", "unknown")
    contributor = (ledger.get("attribution") or {}).get("best_contributor_model_id", "n/a")
    guidance = quality_payload.get("operator_guidance") or {}
    relational = quality_payload.get("relational_field") or {}
    console.print(f"[cyan]Council cycle:[/cyan] {cycle_id}")
    console.print(f"[green]Route:[/green] {route}    [green]Best contributor:[/green] {contributor}")
    console.print(f"[green]Outcome:[/green] {verdict}")
    if guidance:
        console.print(
            f"[yellow]Risk:[/yellow] {guidance.get('risk_state', 'watch')}    "
            f"[yellow]Mode:[/yellow] {relational.get('recommended_mode', 'n/a')}"
        )
        console.print(f"[yellow]Suggested action:[/yellow] {guidance.get('suggested_operator_action', 'n/a')}")
    if artifact_path:
        console.print(f"[bold]Ledger artifact:[/bold] {artifact_path}")
    if council_quality_artifact:
        console.print(f"[bold]Quality artifact:[/bold] {council_quality_artifact}")
    if publish_to_liminalqa and ledger:
        status, response = publish_council_ledger_to_liminalqa(ledger)
        updated_quality_artifact = update_council_quality_artifact_publish_status(
            council_quality_artifact,
            status_code=status,
            response=response,
        )
        console.print(f"[bold]LiminalQA publish:[/bold] HTTP {status}")
        if updated_quality_artifact:
            console.print(f"[bold]Quality publish trace:[/bold] {updated_quality_artifact}")
        console.print(response)
        risk_state = str(guidance.get("risk_state") or "watch")
        if risk_state in {"escalate", "repair"} and quality_payload:
            incident_status, incident_response = publish_council_incident_to_liminalqa(quality_payload)
            updated_incident_artifact = update_council_quality_artifact_incident_status(
                council_quality_artifact,
                status_code=incident_status,
                response=incident_response,
            )
            console.print(f"[bold]LiminalQA incident:[/bold] HTTP {incident_status}")
            if updated_incident_artifact:
                console.print(f"[bold]Incident trace:[/bold] {updated_incident_artifact}")
            console.print(incident_response)
    final_output = str(result.get("final_output", "") or "")
    print_plain_safe(final_output)


if __name__ == "__main__":
    app()
