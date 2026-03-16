from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .models import TaskStatus


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)


class AgentOut(BaseModel):
    id: int
    name: str
    reputation: float

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    title: str
    description: str
    reward: float = Field(gt=0)


class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    status: TaskStatus
    reward: float
    escrow_locked: float
    holdback_locked: float
    paid_out: float
    assigned_agent_id: int | None

    class Config:
        from_attributes = True


class AssignTaskRequest(BaseModel):
    agent_id: int


class ArtifactSubmit(BaseModel):
    task_id: int
    agent_id: int
    hash: str = Field(min_length=8, max_length=128)
    quality_score: float = Field(ge=0, le=1)


class ArtifactOut(BaseModel):
    id: int
    task_id: int
    agent_id: int
    hash: str
    quality_score: float

    class Config:
        from_attributes = True


class VerifyTaskRequest(BaseModel):
    approved: bool = True


class SettlementResult(BaseModel):
    task_id: int
    paid_now: float
    holdback_left: float


class LedgerEventOut(BaseModel):
    id: int
    event_type: str
    task_id: int | None
    agent_id: int | None
    payload: str
    created_at: datetime

    class Config:
        from_attributes = True
