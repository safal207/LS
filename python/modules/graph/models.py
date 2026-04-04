# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4


@dataclass
class NetworkQuestion:
    text: str
    clean_text: str
    intent: Optional[str] = None
    why: Optional[str] = None
    strategy: Optional[dict[str, Any]] = None
    thread_context: Optional[str] = None
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryCase:
    case_id: str
    question_text: str
    clean_text: str
    intent: Optional[str] = None
    why: Optional[str] = None
    thread_context: Optional[str] = None
    answer_text: str = ""
    answer_quality: dict[str, Any] = field(default_factory=dict)
    contributors: list[dict[str, Any]] = field(default_factory=list)
    embedding: Optional[list[float]] = None
    reuse_count: int = 0
    created_at: Optional[str] = None
    last_reused_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryCase":
        return cls(
            case_id=str(data.get("case_id", "")),
            question_text=str(data.get("question_text", "")),
            clean_text=str(data.get("clean_text", data.get("question_text", ""))),
            intent=data.get("intent"),
            why=data.get("why"),
            thread_context=data.get("thread_context"),
            answer_text=str(data.get("answer_text", "")),
            answer_quality=dict(data.get("answer_quality") or {}),
            contributors=list(data.get("contributors") or []),
            embedding=data.get("embedding"),
            reuse_count=int(data.get("reuse_count", 0) or 0),
            created_at=data.get("created_at"),
            last_reused_at=data.get("last_reused_at"),
        )


@dataclass
class ReuseDecision:
    mode: str
    matched_case_id: Optional[str]
    similarity: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievedCase:
    case: MemoryCase
    similarity: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case": self.case.to_dict(),
            "similarity": self.similarity,
            "reason": self.reason,
        }


@dataclass
class GraphCandidate:
    backend: str
    model: str
    role: str
    answer: str
    quality: dict[str, Any] = field(default_factory=dict)
    source_case_id: Optional[str] = None
    used_prior_memory: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Coalition:
    coalition_id: str
    members: list[str]
    roles: dict[str, str]
    trust_score: float = 0.0
    topic_domains: list[str] = field(default_factory=list)


@dataclass
class DerivedModule:
    module_id: str
    parent_coalition_id: str
    domain: str
    task_type: str
    policy_type: str
    policy_text: str = ""
    preferred_backend: str = "local"
    source_route_key: str = ""
    trust_score: float = 0.0
    quality_score: float = 0.0
    usage_count: int = 0
    runs: int = 0
    successes: int = 0
    state: str = "active"
    care_cycles: int = 0
    last_used_at: Optional[str] = None
    last_reviewed_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DerivedModule":
        return cls(
            module_id=str(data.get("module_id", "")),
            parent_coalition_id=str(data.get("parent_coalition_id", "")),
            domain=str(data.get("domain", "")),
            task_type=str(data.get("task_type", "")),
            policy_type=str(data.get("policy_type", "")),
            policy_text=str(data.get("policy_text", "")),
            preferred_backend=str(data.get("preferred_backend", "local") or "local"),
            source_route_key=str(data.get("source_route_key", "")),
            trust_score=float(data.get("trust_score", 0.0) or 0.0),
            quality_score=float(data.get("quality_score", 0.0) or 0.0),
            usage_count=int(data.get("usage_count", 0) or 0),
            runs=int(data.get("runs", 0) or 0),
            successes=int(data.get("successes", 0) or 0),
            state=str(data.get("state", "active") or "active"),
            care_cycles=int(data.get("care_cycles", 0) or 0),
            last_used_at=data.get("last_used_at"),
            last_reviewed_at=data.get("last_reviewed_at"),
        )


@dataclass
class ContributionRecord:
    backend: str
    model: str
    role: str
    delta_score: float
    accepted_fragments: int = 0
    rejected_fragments: int = 0
    helped_final_answer: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContributionRecord":
        return cls(
            backend=str(data.get("backend", "")),
            model=str(data.get("model", "")),
            role=str(data.get("role", "")),
            delta_score=float(data.get("delta_score", 0.0) or 0.0),
            helped_final_answer=bool(data.get("helped_final_answer", False)),
            accepted_fragments=int(data.get("accepted_fragments", 0)),
            rejected_fragments=int(data.get("rejected_fragments", 0)),
        )


@dataclass
class ResonanceKnowledgeUnit:
    """Единица проверенного когнитивного маршрута (структура мышления, а не просто ответ)."""

    source_question: str

    unit_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    clean_question: Optional[str] = None
    intent: Optional[str] = None
    why: Optional[str] = None
    goal_vector: list[float] = field(default_factory=list)
    causal_path: list[dict[str, Any]] = field(default_factory=list)
    resonance_score: float = 0.0
    alignment_score: float = 0.0
    edges: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResonanceKnowledgeUnit":
        # Совместимость с JSONL-снапшотами MVP.
        return cls(
            source_question=str(data.get("source_question") or ""),
            unit_id=str(data.get("unit_id") or str(uuid4())),
            timestamp=str(
                data.get("timestamp") or datetime.now(timezone.utc).isoformat()
            ),
            clean_question=data.get("clean_question"),
            intent=data.get("intent"),
            why=data.get("why"),
            goal_vector=list(data.get("goal_vector") or []),
            causal_path=list(data.get("causal_path") or []),
            resonance_score=float(data.get("resonance_score", 0.0) or 0.0),
            alignment_score=float(data.get("alignment_score", 0.0) or 0.0),
            edges=list(data.get("edges") or []),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class RelationalFieldSnapshot:
    field_id: str
    timestamp: str
    participants: list[str] = field(default_factory=list)
    interaction_scope: str = "human-human"
    tension_score: float = 0.0
    alignment_score: float = 0.0
    dominant_signal: str = "neutral"
    background_pressure: list[str] = field(default_factory=list)
    foreground_expression: list[str] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RelationalFieldSnapshot":
        return cls(
            field_id=str(data.get("field_id") or str(uuid4())),
            timestamp=str(
                data.get("timestamp") or datetime.now(timezone.utc).isoformat()
            ),
            participants=list(data.get("participants") or []),
            interaction_scope=str(data.get("interaction_scope") or "human-human"),
            tension_score=float(data.get("tension_score", 0.0) or 0.0),
            alignment_score=float(data.get("alignment_score", 0.0) or 0.0),
            dominant_signal=str(data.get("dominant_signal") or "neutral"),
            background_pressure=list(data.get("background_pressure") or []),
            foreground_expression=list(data.get("foreground_expression") or []),
            notes=str(data.get("notes") or ""),
            metadata=dict(data.get("metadata") or {}),
        )
