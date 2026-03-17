from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaskStatus(str, enum.Enum):
    open = "open"
    assigned = "assigned"
    delivered = "delivered"
    verified = "verified"
    accepted = "accepted"
    disputed = "disputed"
    closed = "closed"


class BidStatus(str, enum.Enum):
    submitted = "submitted"
    accepted = "accepted"
    rejected = "rejected"


class SettlementStatus(str, enum.Enum):
    pending = "pending"
    released = "released"


class VerificationStage(str, enum.Enum):
    auto = "auto"
    reviewer = "reviewer"
    impact = "impact"


class EventType(str, enum.Enum):
    task_created = "task_created"
    bid_submitted = "bid_submitted"
    task_assigned = "task_assigned"
    artifact_delivered = "artifact_delivered"
    verification_stage_recorded = "verification_stage_recorded"
    task_verified = "task_verified"
    task_disputed = "task_disputed"
    payout_released = "payout_released"
    settlement_scheduled = "settlement_scheduled"
    settlement_released = "settlement_released"
    reputation_updated = "reputation_updated"
    treasury_updated = "treasury_updated"
    governance_updated = "governance_updated"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    treasury_balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    reputation: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.open, nullable=False
    )
    reward: Mapped[float] = mapped_column(Float, nullable=False)
    escrow_locked: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    holdback_locked: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    paid_out: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    auto_check_passed: Mapped[bool | None] = mapped_column(default=None)
    reviewer_check_passed: Mapped[bool | None] = mapped_column(default=None)
    impact_score: Mapped[float | None] = mapped_column(Float, default=None)

    assigned_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    assigned_agent: Mapped[Agent | None] = relationship("Agent")
    project: Mapped[Project] = relationship("Project")


class Bid(Base):
    __tablename__ = "bids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    eta_hours: Mapped[int] = mapped_column(Integer, default=72, nullable=False)
    status: Mapped[BidStatus] = mapped_column(
        Enum(BidStatus), default=BidStatus.submitted, nullable=False
    )

    task: Mapped[Task] = relationship("Task")
    agent: Mapped[Agent] = relationship("Agent")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    hash: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)

    task: Mapped[Task] = relationship("Task")
    agent: Mapped[Agent] = relationship("Agent")


class VerificationReview(Base):
    __tablename__ = "verification_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    stage: Mapped[VerificationStage] = mapped_column(Enum(VerificationStage), nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False)
    note: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    release_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus), default=SettlementStatus.pending, nullable=False
    )


class GovernanceParam(Base):
    __tablename__ = "governance_params"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)


class LedgerEvent(Base):
    __tablename__ = "ledger_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    payload: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
