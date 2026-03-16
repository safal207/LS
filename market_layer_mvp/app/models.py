from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


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


class EventType(str, enum.Enum):
    task_created = "task_created"
    task_assigned = "task_assigned"
    artifact_delivered = "artifact_delivered"
    task_verified = "task_verified"
    payout_released = "payout_released"
    reputation_updated = "reputation_updated"


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    reputation: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.open, nullable=False
    )
    reward: Mapped[float] = mapped_column(Float, nullable=False)
    escrow_locked: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    holdback_locked: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    paid_out: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    assigned_agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    assigned_agent: Mapped[Agent | None] = relationship("Agent")


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), nullable=False)
    hash: Mapped[str] = mapped_column(String(128), nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False)

    task: Mapped[Task] = relationship("Task")
    agent: Mapped[Agent] = relationship("Agent")


class LedgerEvent(Base):
    __tablename__ = "ledger_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    agent_id: Mapped[int | None] = mapped_column(ForeignKey("agents.id"))
    payload: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
