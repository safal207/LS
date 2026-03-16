from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1)


class AgentOut(BaseModel):
    id: int
    name: str
    reputation_score: float
    balance: float

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    treasury: float = Field(ge=0.0)


class ProjectOut(BaseModel):
    id: int
    name: str
    treasury: float

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    project_id: int
    title: str
    description: str
    reward_budget: float = Field(gt=0.0)


class TaskOut(BaseModel):
    id: int
    project_id: int
    title: str
    description: str
    reward_budget: float
    status: str

    class Config:
        from_attributes = True


class AcceptTaskIn(BaseModel):
    agent_id: int


class CompleteTaskIn(BaseModel):
    agent_id: int
    artifact: str = Field(min_length=1)
    impact_score: float = Field(ge=0.0)
    quality_score: float = Field(ge=0.0)


class CreationEventOut(BaseModel):
    id: int
    task_id: int
    agent_id: int
    timestamp: datetime
    impact_score: float
    quality_score: float
    artifact: str

    class Config:
        from_attributes = True


class RewardComputeOut(BaseModel):
    processed_count: int
    total_amount: float
