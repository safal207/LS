from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import BidStatus, SettlementStatus, TaskStatus, VerificationStage


class AgentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    reputation: float


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    treasury_balance: float = Field(ge=0)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    treasury_balance: float


class TaskCreate(BaseModel):
    project_id: int
    title: str
    description: str
    reward: float = Field(gt=0)
    use_case: str = Field(default="generic", max_length=64)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    use_case: str
    status: TaskStatus
    reward: float
    escrow_locked: float
    holdback_locked: float
    paid_out: float
    auto_check_passed: bool | None
    reviewer_check_passed: bool | None
    impact_score: float | None
    assigned_agent_id: int | None


class AssignTaskRequest(BaseModel):
    agent_id: int


class BidCreate(BaseModel):
    agent_id: int
    price: float = Field(gt=0)
    eta_hours: int = Field(gt=0, le=24 * 30)


class BidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    agent_id: int
    price: float
    eta_hours: int
    status: BidStatus


class ArtifactSubmit(BaseModel):
    task_id: int
    agent_id: int
    hash: str = Field(min_length=8, max_length=128)
    quality_score: float = Field(ge=0, le=1)
    # BUG-ML-02: Cap artifact content at 512 KB to prevent unbounded DB row sizes.
    content: str = Field(default="", max_length=524_288)


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    agent_id: int
    hash: str
    quality_score: float
    content: str


class VerifyTaskRequest(BaseModel):
    approved: bool = True


class VerifyStageRequest(BaseModel):
    stage: VerificationStage
    passed: bool
    note: str = Field(default="", max_length=500)
    impact_score: float | None = Field(default=None, ge=0, le=1)


class DisputeTaskRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class SettlementResult(BaseModel):
    task_id: int
    paid_now: float
    holdback_left: float


class SettlementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    amount: float
    release_at: datetime
    status: SettlementStatus


class SettlementRunResult(BaseModel):
    released_count: int
    released_amount: float


class GovernanceParamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: float


class GovernanceUpdateRequest(BaseModel):
    value: float


class LedgerEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    task_id: int | None
    agent_id: int | None
    payload: str
    created_at: datetime
