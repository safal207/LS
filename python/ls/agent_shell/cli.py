from __future__ import annotations

from datetime import datetime, timezone
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

try:
    from agent.external_agent_gateway import ExternalAgentGateway, ExternalAgentGatewayRequest
except ImportError:
    from modules.agent.external_agent_gateway import ExternalAgentGateway, ExternalAgentGatewayRequest

try:
    from agent.agent_adapter_kit import AgentAdapterKit, CodexSelfUseAdapter
except ImportError:
    from modules.agent.agent_adapter_kit import AgentAdapterKit, CodexSelfUseAdapter

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


def print_json_safe(payload: object) -> None:
    output = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(output)
        sys.stdout.flush()
    except UnicodeEncodeError:
        stream = getattr(sys.stdout, "buffer", None)
        safe_bytes = output.encode("utf-8", errors="replace")
        if stream is not None:
            stream.write(safe_bytes)
            stream.flush()
        else:
            sys.stdout.write(output.encode("ascii", errors="backslashreplace").decode("ascii"))


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


def _council_quality_path(quality_dir: Path, cycle_id: str) -> Path:
    return quality_dir / f"{cycle_id}.json"


def load_council_quality_artifact(quality_dir: Path, cycle_id: str) -> dict:
    path = _council_quality_path(quality_dir, cycle_id)
    if not path.exists():
        raise ValueError(f"Council quality artifact not found: {cycle_id}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["_path"] = str(path)
    return payload


def save_council_quality_artifact(path: Path, payload: dict) -> None:
    payload = dict(payload)
    payload.pop("_path", None)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_council_review_history(payload: dict, entry: dict) -> None:
    history = list(payload.get("operator_review_history") or [])
    history.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **entry,
        }
    )
    payload["operator_review_history"] = history


def update_council_operator_review(
    quality_dir: Path,
    cycle_id: str,
    *,
    decision: str,
    reviewer: str,
    forced: bool = False,
    reason: str | None = None,
) -> Path:
    artifact = load_council_quality_artifact(quality_dir, cycle_id)
    path = Path(str(artifact.get("_path") or _council_quality_path(quality_dir, cycle_id)))
    current = artifact.get("operator_review") or {}
    artifact["operator_review"] = {
        "decision": decision,
        "reviewer": reviewer,
        "forced": bool(forced),
        "reason": str(reason or ""),
        "assigned_reviewer": current.get("assigned_reviewer"),
        "assigned_by": current.get("assigned_by"),
        "closed_reason": current.get("closed_reason"),
        "closed_by": current.get("closed_by"),
    }
    append_council_review_history(
        artifact,
        {
            "action": "approve" if decision == "approved" else "reject",
            "decision": decision,
            "reviewer": reviewer,
            "forced": bool(forced),
            "reason": str(reason or ""),
        },
    )
    save_council_quality_artifact(path, artifact)
    return path


def assign_council_reviewer(
    quality_dir: Path,
    cycle_id: str,
    *,
    reviewer: str,
    assigned_by: str,
) -> Path:
    artifact = load_council_quality_artifact(quality_dir, cycle_id)
    path = Path(str(artifact.get("_path") or _council_quality_path(quality_dir, cycle_id)))
    current = artifact.get("operator_review") or {}
    artifact["operator_review"] = {
        "decision": current.get("decision", "pending"),
        "reviewer": current.get("reviewer"),
        "forced": bool(current.get("forced", False)),
        "reason": str(current.get("reason") or ""),
        "assigned_reviewer": reviewer,
        "assigned_by": assigned_by,
    }
    append_council_review_history(
        artifact,
        {
            "action": "assign",
            "reviewer": reviewer,
            "assigned_by": assigned_by,
        },
    )
    save_council_quality_artifact(path, artifact)
    return path


def iter_council_escalation_rows(quality_dir: Path) -> list[dict]:
    rows = [
        row
        for row in load_council_quality_rows(quality_dir)
        if str((row.get("operator_guidance") or {}).get("risk_state") or "") == "escalate"
        or str((row.get("operator_guidance") or {}).get("approval_posture") or "") == "human_escalation"
    ]
    queue_rows: list[dict] = []
    for row in rows:
        guidance = row.get("operator_guidance") or {}
        outcome = row.get("council_outcome") or {}
        review = row.get("operator_review") or {}
        review_status = str(review.get("decision") or "pending")
        queue_rows.append(
            {
                "cycle_id": str(row.get("cycle_id") or "n/a"),
                "review_status": review_status,
                "assigned_reviewer": str(review.get("assigned_reviewer") or "unassigned"),
                "approval_posture": str(guidance.get("approval_posture") or "human_escalation"),
                "selected_route": str(outcome.get("selected_route") or "unknown"),
                "suggested_operator_action": str(guidance.get("suggested_operator_action") or "n/a"),
            }
        )
    queue_rows.sort(
        key=lambda item: (
            item["review_status"] != "pending",
            item["assigned_reviewer"] != "unassigned",
            item["cycle_id"],
        )
    )
    return queue_rows


def close_council_escalation(
    quality_dir: Path,
    cycle_id: str,
    *,
    reviewer: str,
    reason: str,
) -> Path:
    artifact = load_council_quality_artifact(quality_dir, cycle_id)
    path = Path(str(artifact.get("_path") or _council_quality_path(quality_dir, cycle_id)))
    current = artifact.get("operator_review") or {}
    artifact["operator_review"] = {
        "decision": "closed",
        "reviewer": reviewer,
        "forced": bool(current.get("forced", False)),
        "reason": str(current.get("reason") or ""),
        "assigned_reviewer": current.get("assigned_reviewer"),
        "assigned_by": current.get("assigned_by"),
        "closed_reason": reason,
        "closed_by": reviewer,
    }
    append_council_review_history(
        artifact,
        {
            "action": "close",
            "reviewer": reviewer,
            "reason": reason,
        },
    )
    save_council_quality_artifact(path, artifact)
    return path


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


def parse_json_option(value: str, *, option_name: str, expected_type: type) -> object:
    text = str(value or "").strip()
    if not text:
        return expected_type()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"{option_name} must be valid JSON: {exc.msg}") from exc
    if not isinstance(payload, expected_type):
        raise typer.BadParameter(f"{option_name} must be a JSON {expected_type.__name__}.")
    return payload


def configure_gateway_artifact_dirs(agent: ResonanceAgent, artifact_dir: Path) -> None:
    agent._council_ledger_dir = artifact_dir
    agent._council_quality_dir = artifact_dir.parent / "council-quality"
    agent._relational_episode_dir = artifact_dir.parent / "relational-episodes"
    agent._relation_memory_dir = artifact_dir.parent / "relation-memory"
    agent._relational_learning_dir = artifact_dir.parent / "relational-learning"


def default_codex_self_use_participants() -> list[dict]:
    return [
        {
            "participant_id": "operator",
            "participant_type": "human",
            "role": "requester",
            "intent": "safe_architecture_progress",
            "why": "avoid breaking the system while moving fast",
            "need_vector": ["care", "evidence", "stability"],
        },
        {
            "participant_id": "codex-self-use",
            "participant_type": "model",
            "role": "drafting-agent",
            "intent": "ship_fast_answer",
            "why": "give an immediate answer",
            "need_vector": ["speed", "completion"],
        },
    ]


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
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the review queue as JSON for automation.",
    ),
    fail_on_risk: bool = typer.Option(
        False,
        "--fail-on-risk",
        help="Exit non-zero when any repair/escalate cycle is present in the filtered queue.",
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
        if as_json:
            print_plain_safe(
                json.dumps(
                    {
                        "total": 0,
                        "highest_risk": "safe",
                        "risk_counts": {},
                        "items": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            raise typer.Exit(code=0)
        console.print("[yellow]No council-quality artifacts found.[/yellow]")
        raise typer.Exit(code=0)
    queue_rows: list[dict] = []
    highest_risk = "safe"
    risk_counts: dict[str, int] = {}
    for row in rows:
        guidance = row.get("operator_guidance") or {}
        relational = row.get("relational_field") or {}
        outcome = row.get("council_outcome") or {}
        quality_score = row.get("relation_adjusted_quality_score")
        if quality_score is None:
            quality_score = row.get("quality_score")
        risk_state = str(guidance.get("risk_state") or "watch")
        risk_counts[risk_state] = risk_counts.get(risk_state, 0) + 1
        if _council_risk_rank(risk_state) < _council_risk_rank(highest_risk):
            highest_risk = risk_state
        queue_rows.append(
            {
                "cycle_id": str(row.get("cycle_id") or "n/a"),
                "risk_state": risk_state,
                "recommended_mode": str(relational.get("recommended_mode") or "n/a"),
                "approval_posture": str(guidance.get("approval_posture") or "n/a"),
                "route_strategy": str(guidance.get("route_strategy") or "n/a"),
                "selected_route": str(outcome.get("selected_route") or "unknown"),
                "quality_score": None if quality_score is None else round(float(quality_score), 4),
                "review_status": str(((row.get("operator_review") or {}).get("decision")) or "pending"),
                "suggested_operator_action": str(guidance.get("suggested_operator_action") or "n/a"),
            }
        )
    if as_json:
        print_plain_safe(
            json.dumps(
                {
                    "total": len(queue_rows),
                    "highest_risk": highest_risk,
                    "risk_counts": risk_counts,
                    "items": queue_rows,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if fail_on_risk and any(item["risk_state"] in {"repair", "escalate"} for item in queue_rows):
            raise typer.Exit(code=2)
        raise typer.Exit(code=0)
    table = Table(title="Council Review Queue")
    table.add_column("cycle")
    table.add_column("risk")
    table.add_column("mode")
    table.add_column("posture")
    table.add_column("review")
    table.add_column("route")
    table.add_column("quality")
    table.add_column("action")
    for item in queue_rows:
        table.add_row(
            item["cycle_id"],
            item["risk_state"],
            item["recommended_mode"],
            item["approval_posture"],
            item["review_status"],
            item["selected_route"],
            "n/a" if item["quality_score"] is None else f"{float(item['quality_score']):.4f}",
            item["suggested_operator_action"],
        )
    console.print(table)
    if fail_on_risk and any(item["risk_state"] in {"repair", "escalate"} for item in queue_rows):
        raise typer.Exit(code=2)


@app.command("council-escalations")
def council_escalations(
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read council-quality JSON artifacts.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the escalation queue as JSON for automation.",
    ),
) -> None:
    queue_rows = iter_council_escalation_rows(quality_dir)
    if as_json:
        print_plain_safe(json.dumps({"total": len(queue_rows), "items": queue_rows}, ensure_ascii=False, indent=2))
        raise typer.Exit(code=0)
    if not queue_rows:
        console.print("[yellow]No council escalations found.[/yellow]")
        raise typer.Exit(code=0)
    table = Table(title="Council Escalation Queue")
    table.add_column("cycle")
    table.add_column("review")
    table.add_column("assignee")
    table.add_column("posture")
    table.add_column("route")
    table.add_column("action")
    for item in queue_rows:
        table.add_row(
            item["cycle_id"],
            item["review_status"],
            item["assigned_reviewer"],
            item["approval_posture"],
            item["selected_route"],
            item["suggested_operator_action"],
        )
    console.print(table)


@app.command("council-assign-reviewer")
def council_assign_reviewer(
    cycle_id: str,
    reviewer: str = typer.Option(..., "--reviewer", help="Reviewer to assign."),
    assigned_by: str = typer.Option("operator", "--assigned-by", help="Who assigned this escalation."),
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read and update council-quality JSON artifacts.",
    ),
) -> None:
    updated_path = assign_council_reviewer(
        quality_dir,
        cycle_id,
        reviewer=reviewer,
        assigned_by=assigned_by,
    )
    console.print(f"[green]Assigned reviewer[/green] {reviewer} to {cycle_id}")
    console.print(f"[bold]Review artifact:[/bold] {updated_path}")


@app.command("council-claim-next-escalation")
def council_claim_next_escalation(
    reviewer: str = typer.Option(..., "--reviewer", help="Reviewer claiming the next escalation."),
    assigned_by: str = typer.Option("operator", "--assigned-by", help="Who assigned this escalation."),
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read and update council-quality JSON artifacts.",
    ),
) -> None:
    queue_rows = iter_council_escalation_rows(quality_dir)
    target = next(
        (
            item
            for item in queue_rows
            if item["review_status"] == "pending" and item["assigned_reviewer"] == "unassigned"
        ),
        None,
    )
    if target is None:
        console.print("[yellow]No unassigned pending escalations found.[/yellow]")
        raise typer.Exit(code=1)
    updated_path = assign_council_reviewer(
        quality_dir,
        target["cycle_id"],
        reviewer=reviewer,
        assigned_by=assigned_by,
    )
    console.print(f"[green]Claimed escalation[/green] {target['cycle_id']} for {reviewer}")
    console.print(f"[bold]Review artifact:[/bold] {updated_path}")


@app.command("council-close-escalation")
def council_close_escalation(
    cycle_id: str,
    reviewer: str = typer.Option(..., "--reviewer", help="Reviewer closing this escalation."),
    reason: str = typer.Option(..., "--reason", help="Why the escalation is being closed."),
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read and update council-quality JSON artifacts.",
    ),
) -> None:
    updated_path = close_council_escalation(
        quality_dir,
        cycle_id,
        reviewer=reviewer,
        reason=reason,
    )
    console.print(f"[green]Closed escalation[/green] {cycle_id}")
    console.print(f"[bold]Reason:[/bold] {reason}")
    console.print(f"[bold]Review artifact:[/bold] {updated_path}")


@app.command("codex-adapter-demo")
def codex_adapter_demo(
    prompt: str = typer.Argument(
        "Help me decide how to handle a risky architecture bug.",
        help="Prompt to draft first, then route through LS.",
    ),
    raw_draft: str = typer.Option(
        "Patch it quickly and ship; clean up architecture later.",
        "--raw-draft",
        help="Simulated raw Codex/self-use draft before LS shaping.",
    ),
    participants_json: str = typer.Option(
        "",
        "--participants-json",
        help="Optional JSON list of participant/context objects.",
    ),
    artifact_dir: Path = typer.Option(
        Path("artifacts/council-ledger"),
        "--artifact-dir",
        help="Where to write adapter demo ledger artifacts.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the adapter comparison as JSON.",
    ),
) -> None:
    try:
        parsed_participants = parse_json_option(
            participants_json,
            option_name="--participants-json",
            expected_type=list,
        )
    except typer.BadParameter as exc:
        console.print(f"[red]Invalid adapter input:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    participants = list(parsed_participants) or default_codex_self_use_participants()
    try:
        agent = build_council_agent(
            orientation="cli-codex-self-use-adapter",
            llm_mode=CouncilLLMMode.DRY_RUN,
        )
    except Exception as exc:
        console.print(f"[red]Adapter agent init failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    configure_gateway_artifact_dirs(agent, artifact_dir)
    kit = AgentAdapterKit.from_agent(
        agent,
        default_agent_id="codex-self-use",
        default_agent_type="codex",
        default_orientation="cli-codex-self-use-adapter",
    )
    adapter = CodexSelfUseAdapter(kit, draft_fn=lambda _request: raw_draft)
    response = adapter.answer(
        prompt,
        participants=participants,
        metadata={"source": "ls-agent-shell-cli", "demo": True},
        orientation="cli-codex-self-use-adapter",
    )
    payload = response.to_public_dict()
    payload["adapter_contract"] = "agent_adapter_kit_v1"
    payload["comparison"] = adapter.compare(response)

    if as_json:
        print_json_safe(payload)
        raise typer.Exit(code=0)

    console.print(f"[cyan]Codex adapter demo:[/cyan] {response.cycle_id}")
    console.print(f"[green]Gateway mode:[/green] {response.gateway_mode}")
    console.print(f"[yellow]Reason:[/yellow] {response.gateway_reason}")
    console.print(f"[bold]Raw draft:[/bold] {response.raw_output}")
    console.print("[bold]Final after LS:[/bold]")
    print_plain_safe(response.final_output)


@app.command("agent-gateway")
def agent_gateway(
    prompt: str,
    raw_output: str = typer.Option(..., "--raw-output", help="Raw answer produced by the external agent."),
    agent_id: str = typer.Option("external-agent", "--agent-id", help="External agent identifier."),
    agent_type: str = typer.Option("external", "--agent-type", help="External agent provider/type."),
    orientation: str = typer.Option("", "--orientation", help="Optional gateway orientation/context."),
    participants_json: str = typer.Option(
        "",
        "--participants-json",
        help="Optional JSON list of participant/context objects.",
    ),
    relational_json: str = typer.Option(
        "",
        "--relational-json",
        help="Optional JSON object with precomputed relational field signals.",
    ),
    alignment_json: str = typer.Option(
        "",
        "--alignment-json",
        help="Optional JSON object with precomputed alignment signals.",
    ),
    metadata_json: str = typer.Option(
        "",
        "--metadata-json",
        help="Optional JSON object with external agent metadata.",
    ),
    llm_mode: CouncilLLMMode = typer.Option(
        CouncilLLMMode.DRY_RUN,
        "--llm-mode",
        help="Choose whether gateway context may use a real local LLM or dry-run mode.",
    ),
    artifact_dir: Path = typer.Option(
        Path("artifacts/council-ledger"),
        "--artifact-dir",
        help="Where to write gateway/council ledger JSON artifacts.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the gateway result as JSON for automation.",
    ),
) -> None:
    try:
        participants = parse_json_option(
            participants_json,
            option_name="--participants-json",
            expected_type=list,
        )
        relational_field = parse_json_option(
            relational_json,
            option_name="--relational-json",
            expected_type=dict,
        )
        alignment_report = parse_json_option(
            alignment_json,
            option_name="--alignment-json",
            expected_type=dict,
        )
        metadata = parse_json_option(
            metadata_json,
            option_name="--metadata-json",
            expected_type=dict,
        )
    except typer.BadParameter as exc:
        console.print(f"[red]Invalid gateway input:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    gateway_orientation = orientation or "cli-external-agent-gateway"
    try:
        agent = build_council_agent(orientation=gateway_orientation, llm_mode=llm_mode)
    except Exception as exc:
        console.print(f"[red]Gateway agent init failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    configure_gateway_artifact_dirs(agent, artifact_dir)

    gateway = ExternalAgentGateway(agent, default_orientation=gateway_orientation)
    request = ExternalAgentGatewayRequest(
        prompt=prompt,
        raw_output=raw_output,
        agent_id=agent_id,
        agent_type=agent_type,
        orientation=gateway_orientation,
        participants=list(participants),
        relational_field=dict(relational_field) or None,
        alignment_report=dict(alignment_report) or None,
        metadata=dict(metadata),
    )
    result = gateway.route_external_output(request)

    if as_json:
        print_json_safe(result)
        raise typer.Exit(code=0)

    gateway_summary = result.get("personal_agent_gateway") or {}
    console.print(f"[cyan]External agent gateway:[/cyan] {result.get('cycle_id', 'unknown')}")
    console.print(
        f"[green]Agent:[/green] {agent_id}    "
        f"[green]Mode:[/green] {result.get('gateway_mode', 'pass_through')}"
    )
    console.print(f"[yellow]Reason:[/yellow] {result.get('gateway_reason', 'n/a')}")
    if result.get("council_contribution_ledger_artifact"):
        console.print(f"[bold]Ledger artifact:[/bold] {result.get('council_contribution_ledger_artifact')}")
    if result.get("council_quality_artifact"):
        console.print(f"[bold]Quality artifact:[/bold] {result.get('council_quality_artifact')}")
    raw_excerpt = str(gateway_summary.get("raw_excerpt") or raw_output or "")
    console.print(f"[bold]Raw output:[/bold] {raw_excerpt}")
    console.print("[bold]Final output:[/bold]")
    print_plain_safe(str(result.get("final_output") or ""))


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
        console.print(
            f"[yellow]Approval posture:[/yellow] {guidance.get('approval_posture', 'n/a')}    "
            f"[yellow]Route strategy:[/yellow] {guidance.get('route_strategy', 'n/a')}"
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


@app.command("council-approve")
def council_approve(
    cycle_id: str,
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read and update council-quality JSON artifacts.",
    ),
    reviewer: str = typer.Option("operator", "--reviewer", help="Reviewer label to persist."),
    force: bool = typer.Option(
        False,
        "--force",
        help="Allow approval even when approval posture requires repair or human escalation.",
    ),
) -> None:
    artifact = load_council_quality_artifact(quality_dir, cycle_id)
    guidance = artifact.get("operator_guidance") or {}
    posture = str(guidance.get("approval_posture") or "evidence_check")
    if posture in {"hold_and_repair", "human_escalation"} and not force:
        console.print(
            f"[red]Approval blocked[/red] for {cycle_id}: posture={posture}. "
            "Use --force only if you intentionally override the council policy."
        )
        raise typer.Exit(code=2)
    updated_path = update_council_operator_review(
        quality_dir,
        cycle_id,
        decision="approved",
        reviewer=reviewer,
        forced=force,
        reason=f"approval_posture={posture}",
    )
    console.print(f"[green]Council approved[/green] {cycle_id}")
    console.print(f"[bold]Review artifact:[/bold] {updated_path}")


@app.command("council-reject")
def council_reject(
    cycle_id: str,
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read and update council-quality JSON artifacts.",
    ),
    reviewer: str = typer.Option("operator", "--reviewer", help="Reviewer label to persist."),
    reason: str = typer.Option("Rejected by operator", "--reason", help="Why the cycle was rejected."),
) -> None:
    updated_path = update_council_operator_review(
        quality_dir,
        cycle_id,
        decision="rejected",
        reviewer=reviewer,
        forced=False,
        reason=reason,
    )
    console.print(f"[yellow]Council rejected[/yellow] {cycle_id}")
    console.print(f"[bold]Review artifact:[/bold] {updated_path}")


@app.command("council-validate")
def council_validate(
    cycle_id: str = typer.Argument(
        ...,
        help="Cycle ID to validate, or path to a council-quality JSON artifact.",
    ),
    quality_dir: Path = typer.Option(
        Path("artifacts/council-quality"),
        "--quality-dir",
        help="Where to read council-quality JSON artifacts.",
    ),
    governance: bool = typer.Option(
        False,
        "--governance",
        help="Enable governance engine (reputation, clustering, coalitions).",
    ),
    trace: bool = typer.Option(
        False,
        "--trace",
        help="Attach a Lifetra trajectory trace.",
    ),
    sign: bool = typer.Option(
        False,
        "--sign",
        help="Sign the trace artifact with a generated Ed25519 key pair.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Emit the validation result as JSON.",
    ),
) -> None:
    """Validate a past council cycle through the collective answer validation pipeline.

    Reads the council quality artifact, converts council participants into
    validation candidates, and runs the full scoring / governance / trace pipeline.
    """
    from ls.cognition.council_validation_bridge import validate_council_artifact  # noqa: PLC0415

    # Resolve artifact path: either a direct path or cycle_id in quality_dir
    artifact_path = Path(cycle_id)
    if not artifact_path.exists():
        artifact_path = quality_dir / f"{cycle_id}.json"
    if not artifact_path.exists():
        console.print(f"[red]Artifact not found:[/red] {artifact_path}")
        raise typer.Exit(code=1)

    try:
        result = validate_council_artifact(
            artifact_path,
            governance=governance,
            trace=trace,
            sign=sign,
        )
    except Exception as exc:
        console.print(f"[red]Validation failed:[/red] {exc}")
        raise typer.Exit(code=2) from exc

    if as_json:
        output: dict = {
            "cycle_id": cycle_id,
            "winner_agent_id": result.winner_agent_id,
            "consensus_status": result.consensus_status,
            "consensus_summary": result.consensus_summary,
            "global_risk_flags": result.global_risk_flags,
            "ranked_candidates": [
                {
                    "agent_id": vc.agent_id,
                    "accepted": vc.accepted,
                    "score": round(vc.score, 4),
                    "reasons": vc.reasons,
                    "risk_flags": vc.risk_flags,
                }
                for vc in result.ranked_candidates
            ],
        }
        if result.governance_report is not None:
            output["governance"] = {
                "governed_winner": result.governance_report.governed_winner_agent_id,
                "review_required": result.governance_report.review_required,
                "governance_flags": result.governance_report.governance_flags,
            }
        if result.trace_artifact is not None:
            output["trace"] = {
                "trace_id": result.trace_artifact.trace_id,
                "node_count": result.trace_artifact.node_count,
                "edge_count": result.trace_artifact.edge_count,
            }
        print_plain_safe(json.dumps(output, ensure_ascii=False, indent=2))
        raise typer.Exit(code=0)

    # Rich table output
    console.print(f"\n[cyan]Council Validation:[/cyan] {cycle_id}")
    console.print(f"[green]Winner:[/green] {result.winner_agent_id or 'none'}")
    console.print(f"[green]Consensus:[/green] {result.consensus_status}")
    console.print(f"[green]Summary:[/green] {result.consensus_summary}")
    if result.global_risk_flags:
        console.print(f"[yellow]Risk flags:[/yellow] {', '.join(result.global_risk_flags)}")
    console.print()
    table = Table(title="Candidate Scores")
    table.add_column("agent")
    table.add_column("accepted")
    table.add_column("score")
    table.add_column("risk flags")
    for vc in result.ranked_candidates:
        table.add_row(
            vc.agent_id,
            "[green]yes[/green]" if vc.accepted else "[red]no[/red]",
            f"{vc.score:.4f}",
            ", ".join(vc.risk_flags) or "none",
        )
    console.print(table)
    if result.governance_report is not None:
        gr = result.governance_report
        console.print(f"\n[cyan]Governance:[/cyan] review_required={gr.review_required}")
        console.print(f"[cyan]Governed winner:[/cyan] {gr.governed_winner_agent_id}")
        if gr.governance_flags:
            console.print(f"[yellow]Flags:[/yellow] {', '.join(gr.governance_flags)}")
    if result.trace_artifact is not None:
        ta = result.trace_artifact
        console.print(f"\n[cyan]Trace:[/cyan] {ta.trace_id} ({ta.node_count} nodes, {ta.edge_count} edges)")


if __name__ == "__main__":
    app()
