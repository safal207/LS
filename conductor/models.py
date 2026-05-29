from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Evidence:
    claim: str
    source: str
    status: str
    signal_code: str = ""


@dataclass
class ConductorResponse:
    artifact_type: str
    conductor_version: str
    task_type: str
    policy: str
    final_answer: str
    route_id: str
    route_score: float
    confidence: float
    route_won_vs_single: bool
    evidence: list[Evidence]
    disagreements: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    decision: str
    cost_usd: float | None
    latency_ms: int
    artifact_path: str | None
    source_artifact: dict[str, Any]
    role_market: dict[str, Any]
    claim_boundary: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConductorResponse:
        raw_evidence = data.get("evidence", [])
        evidence = [
            Evidence(
                claim=str(e.get("claim", "")),
                source=str(e.get("source", "")),
                status=str(e.get("status", "")),
                signal_code=str(e.get("signal_code", "")),
            )
            for e in raw_evidence
        ]
        return cls(
            artifact_type=str(data.get("artifact_type", "")),
            conductor_version=str(data.get("conductor_version", "")),
            task_type=str(data.get("task_type", "")),
            policy=str(data.get("policy", "")),
            final_answer=str(data.get("final_answer", "")),
            route_id=str(data.get("route_id", "")),
            route_score=float(data.get("route_score", 0.0)),
            confidence=float(data.get("confidence", 0.0)),
            route_won_vs_single=bool(data.get("route_won_vs_single", False)),
            evidence=evidence,
            disagreements=data.get("disagreements", []),
            signals=data.get("signals", []),
            decision=str(data.get("decision", "")),
            cost_usd=data.get("cost_usd"),
            latency_ms=int(data.get("latency_ms", 0)),
            artifact_path=data.get("artifact_path"),
            source_artifact=data.get("source_artifact", {}),
            role_market=data.get("role_market", {}),
            claim_boundary=str(data.get("claim_boundary", "")),
        )


@dataclass
class CompareResponse:
    winner: str
    why: list[str]
    final_output: str
    route_a: dict[str, Any]
    route_b: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompareResponse:
        return cls(
            winner=str(data.get("winner", "")),
            why=list(data.get("why", [])),
            final_output=str(data.get("final_output", "")),
            route_a=data.get("route_a", {}),
            route_b=data.get("route_b", {}),
        )


@dataclass
class HealthResponse:
    status: str
    conductor_version: str
    available_backends: list[str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HealthResponse:
        return cls(
            status=str(data.get("status", "")),
            conductor_version=str(data.get("conductor_version", "")),
            available_backends=list(data.get("available_backends", [])),
        )


@dataclass
class ConductorConfig:
    repo_path: str = ""
    base: str = "HEAD~1"
    head: str = "HEAD"
    policy: str = "cooperative_pr_review"
    store_path: str = ""
    max_diff_chars: int = 12000
    models: dict[str, str] = field(default_factory=dict)
