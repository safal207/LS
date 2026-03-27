from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


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
    quality_score: float = 0.0
    usage_count: int = 0


@dataclass
class ContributionRecord:
    backend: str
    model: str
    role: str
    delta_score: float
    accepted_fragments: int = 0
    rejected_fragments: int = 0
    helped_final_answer: bool = False
