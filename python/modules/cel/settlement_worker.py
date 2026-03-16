from __future__ import annotations

from dataclasses import dataclass
from time import time
from typing import Callable
from uuid import uuid4

UNSIGNED_PLACEHOLDER = "ed25519:unsigned-local"


class SettlementError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SettlementRequest:
    trace_id: str
    proposal_id: str
    agent_id: str
    expected_delta: float
    actual_delta: float
    horizon_sec: int


@dataclass(frozen=True)
class SettlementResult:
    proposal_id: str
    result: str
    error_band: float
    quality_score: float


class OutcomeSettlementWorker:
    """Computes settlement metrics and appends outcome_settled events to CTL."""

    def __init__(
        self,
        append_ctl_event: Callable[[dict], None] | None = None,
        publish_cem_event: Callable[[dict], None] | None = None,
    ) -> None:
        self._append_ctl_event = append_ctl_event
        self._publish_cem_event = publish_cem_event

    def settle(self, req: SettlementRequest) -> SettlementResult:
        if not req.trace_id.startswith("trace_"):
            raise SettlementError("INVALID_TRACE_ID", "trace_id must start with 'trace_'")
        if not req.proposal_id:
            raise SettlementError("INVALID_PROPOSAL_ID", "proposal_id is required")
        if not req.agent_id:
            raise SettlementError("INVALID_AGENT_ID", "agent_id is required")
        if req.horizon_sec <= 0:
            raise SettlementError("INVALID_HORIZON", "horizon_sec must be > 0")

        result = "hit" if (req.expected_delta >= 0) == (req.actual_delta >= 0) else "miss"
        error_band = abs(req.actual_delta - req.expected_delta)
        quality_score = max(0.0, min(1.0, 1.0 - error_band))

        ctl_event = {
            "event_id": f"evt_{uuid4().hex[:12]}",
            "trace_id": req.trace_id,
            "event_type": "outcome_settled",
            "ts": int(time()),
            "producer": "settlement-worker",
            "schema_version": "1.0",
            "signature": UNSIGNED_PLACEHOLDER,
            "data": {
                "proposal_id": req.proposal_id,
                "agent_id": req.agent_id,
                "horizon_sec": req.horizon_sec,
                "result": result,
                "error_band": round(error_band, 6),
                "quality_score": round(quality_score, 6),
            },
        }
        if self._append_ctl_event:
            self._append_ctl_event(ctl_event)

        cem_event = {
            "trace_id": req.trace_id,
            "event_type": "settlement_completed",
            "proposal_id": req.proposal_id,
            "result": result,
        }
        if self._publish_cem_event:
            self._publish_cem_event(cem_event)

        return SettlementResult(
            proposal_id=req.proposal_id,
            result=result,
            error_band=round(error_band, 6),
            quality_score=round(quality_score, 6),
        )
