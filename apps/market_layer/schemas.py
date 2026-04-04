from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1)


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    reputation_score: float
    balance: float


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    treasury: float = Field(ge=0.0)


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    treasury: float


class TaskCreate(BaseModel):
    project_id: int
    title: str
    description: str
    reward_budget: float = Field(gt=0.0)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    title: str
    description: str
    reward_budget: float
    escrow_balance: float
    status: str


class AcceptTaskIn(BaseModel):
    agent_id: int


class CompleteTaskIn(BaseModel):
    agent_id: int
    artifact: str = Field(min_length=1)
    impact_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)


class CreationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    agent_id: int
    timestamp: datetime
    impact_score: float
    quality_score: float
    artifact: str


class RewardComputeOut(BaseModel):
    processed_count: int
    total_amount: float


class EfficiencyIn(BaseModel):
    tasks_per_month: int = Field(ge=1)
    avg_reward_budget: float = Field(gt=0.0)
    avg_impact_score: float = Field(ge=0.0, le=1.0)
    avg_quality_score: float = Field(ge=0.0, le=1.0)
    baseline_human_cost_per_task: float = Field(gt=0.0)
    automation_uplift_pct: float = Field(ge=0.0, le=1.0)
    platform_opex_monthly: float = Field(ge=0.0)


class EfficiencyOut(BaseModel):
    payout_per_task: float
    net_saving_per_task: float
    gross_monthly_saving: float
    automation_uplift_value: float
    monthly_net_effect: float
    roi_monthly: float | None
    payback_months: float | None
