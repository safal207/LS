from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import uuid
import os
import sys


ALLOWED_MODES = {"read-only", "safe-write", "full-agent"}


class CoreTaskRuntime:
    """Authoritative shell runtime binding used by MCP default resolver."""

    def __init__(self, state_path: str | Path = ".ls_agent/core-runtime/state.json", artifact_root: str | Path = ".ls_agent/core-runtime/artifacts") -> None:
        self.state_path = Path(state_path)
        self.artifact_root = Path(artifact_root)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        self._state = self._load()
        self._agent_loop: Any | None = None

    def _load(self) -> dict[str, Any]:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"tasks": {}}

    def _save(self) -> None:
        self.state_path.write_text(json.dumps(self._state, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _task_id() -> str:
        return f"task-{uuid.uuid4().hex[:8]}"

    def _task(self, task_id: str) -> dict[str, Any]:
        task = self._state["tasks"].get(task_id)
        if task is None:
            raise ValueError(f"Unknown task_id: {task_id}")
        return task

    def plan_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        if mode not in ALLOWED_MODES:
            raise ValueError(f"Unknown mode: {mode}")
        task_id = self._task_id()
        step = {"id": f"{task_id}-step-1", "title": "Fetch task context", "type": "read", "needs_approval": False, "reason": "Need source context before analysis.", "status": "pending"}
        self._state["tasks"][task_id] = {"mode": mode, "status": "blocked", "summary": None, "steps": [step], "events": [], "artifacts": [], "prompt": prompt}
        self._save()
        return {"task_id": task_id, "status": "blocked", "plan": [step], "summary": "Plan generated only."}

    def run_task(self, *, prompt: str, mode: str) -> dict[str, Any]:
        if mode not in ALLOWED_MODES:
            raise ValueError(f"Unknown mode: {mode}")
        task_id = self._task_id()
        steps = [
            {"id": f"{task_id}-step-1", "title": "Read relevant docs", "type": "read", "needs_approval": False, "reason": "Collect local context first.", "status": "completed"},
            {"id": f"{task_id}-step-2", "title": "Draft execution output", "type": "reason", "needs_approval": False, "reason": "Prepare bounded advisory output.", "status": "completed"},
            {"id": f"{task_id}-step-3", "title": "Apply write action", "type": "write", "needs_approval": True, "reason": "Write-side effects require explicit approval.", "status": "waiting_approval"},
        ]
        self._state["tasks"][task_id] = {"mode": mode, "status": "waiting_approval", "summary": None, "steps": steps, "events": [], "artifacts": [], "prompt": prompt}
        self._save()
        return {"task_id": task_id, "status": "waiting_approval", "next_action": "approval_required", "current_step_id": steps[2]["id"]}

    def resume_task(self, *, task_id: str) -> dict[str, Any]:
        task = self._task(task_id)
        if task["status"] in {"blocked", "waiting_approval"}:
            raise ValueError("Cannot resume current task state")
        task["status"] = "running"
        self._save()
        return {"task_id": task_id, "status": "running"}

    def get_status(self, *, task_id: str) -> dict[str, Any]:
        task = self._task(task_id)
        return {"task_id": task_id, "mode": task["mode"], "status": task["status"], "summary": task["summary"], "steps": task["steps"]}

    def get_trace(self, *, task_id: str, limit: int = 100) -> dict[str, Any]:
        task = self._task(task_id)
        return {"task_id": task_id, "events": task["events"][-limit:]}

    def list_artifacts(self, *, task_id: str) -> dict[str, Any]:
        task = self._task(task_id)
        return {"task_id": task_id, "artifacts": task["artifacts"]}

    def approve(self, *, task_id: str, step_id: str) -> dict[str, Any]:
        task = self._task(task_id)
        for step in task["steps"]:
            if step["id"] == step_id:
                step["status"] = "completed"
                break
        else:
            raise ValueError(f"Unknown step_id: {step_id}")
        task["status"] = "completed"
        artifact_path = self.artifact_root / task_id / "report.md"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("# Task report\n", encoding="utf-8")
        task["artifacts"].append({"id": f"artifact-{uuid.uuid4().hex[:8]}", "title": "Task report", "type": "report", "path_or_url": str(artifact_path)})
        task["summary"] = "Task completed with approved side effects; artifact created."
        self._save()
        return {"task_id": task_id, "step_id": step_id, "status": "approved"}

    def reject(self, *, task_id: str, step_id: str, reason: str) -> dict[str, Any]:
        task = self._task(task_id)
        for step in task["steps"]:
            if step["id"] == step_id:
                step["status"] = "rejected"
                break
        else:
            raise ValueError(f"Unknown step_id: {step_id}")
        task["status"] = "blocked"
        task["summary"] = f"Task blocked after rejection: {reason}"
        self._save()
        return {"task_id": task_id, "step_id": step_id, "status": "rejected"}

    def bind_agent_loop(self, loop: Any) -> None:
        """Optional runtime bridge for cognitive MCP resources."""
        self._agent_loop = loop

    def get_resonance_snapshot(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> list[dict[str, Any]]:
        try:
            modules_root = Path(__file__).resolve().parents[3] / "modules"
            root_str = str(modules_root)
            if root_str not in sys.path:
                sys.path.insert(0, root_str)
            from graph.memory_store import MemoryGraphStore

            store = MemoryGraphStore(
                os.environ.get("GRAPH_MEMORY_STORE_PATH", "data/graph_memory/cases.jsonl")
            )
            rows = store.get_resonance_snapshot(
                top_k=top_k,
                min_resonance_score=min_resonance_score,
            )
            return [row.to_dict() for row in rows]
        except Exception:
            return []

    def get_omni_last_insight(self) -> dict[str, Any] | None:
        worker = getattr(self._agent_loop, "qwen_omni_worker", None)
        if worker is None:
            return None
        try:
            return worker.get_last_insight()
        except Exception:
            return None


def build_runtime() -> CoreTaskRuntime:
    return CoreTaskRuntime()
