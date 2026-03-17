from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import BidStatus, TaskStatus


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    reputation: float


class TaskCreate(BaseModel):
    title: str
    description: str
    reward: float = Field(gt=0)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TaskStatus
    reward: float
    escrow_locked: float
    holdback_locked: float
    paid_out: float
    assigned_agent_id: int | None


class AssignTaskRequest(BaseModel):
    agent_id: int


class BidCreate(BaseModel):
    agent_id: int
    price: float = Field(gt=0)


class BidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    agent_id: int
    price: float
    status: BidStatus


class ArtifactSubmit(BaseModel):
    task_id: int
    agent_id: int
    hash: str = Field(min_length=8, max_length=128)
    quality_score: float = Field(ge=0, le=1)


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    agent_id: int
    hash: str
    quality_score: float


class VerifyTaskRequest(BaseModel):
    approved: bool = True


class DisputeTaskRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SettlementResult(BaseModel):
    task_id: int
    paid_now: float
    holdback_left: float


class LedgerEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    task_id: int | None
    agent_id: int | None
    payload: str
    created_at: datetime
