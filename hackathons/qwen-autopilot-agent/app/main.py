from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .policy import assess_policy, stricter_decision
from .qwen import QwenRiskReasoner
from .store import ApprovalStore


ROOT = Path(__file__).resolve().parents[1]
app = FastAPI(title="LS Qwen Autopilot Trust Agent", version="0.1.0")
store = ApprovalStore()


class ActionRequest(BaseModel):
    actor: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=3, max_length=500)
    resource: str = Field(default="unspecified", max_length=300)
    context: str = Field(default="", max_length=2000)
    requested_effect: str = Field(default="", max_length=1000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    reviewer: str = Field(min_length=1, max_length=120)
    note: str = Field(default="", max_length=1000)


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((ROOT / "static" / "index.html").read_text(encoding="utf-8"))


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "ls-qwen-autopilot-agent"}


@app.post("/api/evaluate")
def evaluate(request: ActionRequest) -> dict[str, Any]:
    payload = request.model_dump()
    policy = assess_policy(payload)
    policy_data = {
        "score": policy.score,
        "floor_decision": policy.floor_decision,
        "signals": policy.signals,
    }

    model_status = "COMPLETED"
    try:
        model_result = QwenRiskReasoner().assess(payload, policy_data)
    except Exception as exc:
        model_status = "NOT_RUN"
        model_result = {
            "risk_level": "MEDIUM",
            "decision": "HUMAN_APPROVAL",
            "confidence": 0,
            "reasons": [f"Qwen assessment unavailable: {type(exc).__name__}"],
            "required_controls": ["Configure Qwen Cloud and repeat assessment"],
        }

    final_decision = stricter_decision(policy.floor_decision, str(model_result.get("decision")))
    assessment = {
        "decision": final_decision,
        "risk_level": model_result.get("risk_level", "MEDIUM"),
        "confidence": model_result.get("confidence", 0),
        "reasons": model_result.get("reasons", []),
        "required_controls": model_result.get("required_controls", []),
        "policy": policy_data,
        "qwen": {"status": model_status, "model": os.getenv("QWEN_MODEL", "qwen3.7-plus")},
        "execution": {"status": "NOT_EXECUTED", "authority": "advisory_only"},
    }

    if final_decision == "HUMAN_APPROVAL":
        assessment["approval_id"] = store.create(payload, assessment)
    return assessment


@app.get("/api/approvals/{approval_id}")
def get_approval(approval_id: str) -> dict[str, Any]:
    result = store.get(approval_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return result


@app.post("/api/approvals/{approval_id}")
def resolve_approval(approval_id: str, request: ApprovalDecision) -> dict[str, Any]:
    result = store.resolve(approval_id, request.decision, request.reviewer, request.note)
    if result is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return result
