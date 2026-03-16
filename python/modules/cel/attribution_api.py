from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import RLock

from .iare_engine import (
    ContributorImpact,
    CreationEvent,
    IAREError,
    IncrementalAttributionEngine,
    PayoutSnapshot,
)


class AttributionApiError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AttributionIngestRequest:
    event_id: str
    project_id: str
    event_type: str
    ts: int
    policy_version: str
    contributors: tuple[ContributorImpact, ...]
    parents: tuple[str, ...] = ()
    base_weight: float = 1.0


@dataclass(frozen=True)
class PayoutPreviewRequest:
    project_id: str
    policy_version: str
    total_value: Decimal


@dataclass(frozen=True)
class PayoutReplayRequest:
    project_id: str
    policy_version: str
    total_value: Decimal
    expected_input_snapshot_hash: str
    expected_output_payout_hash: str


class AttributionReplayAPI:
    """In-memory facade for IARE ingestion and deterministic replay checks."""

    def __init__(self, attribution_engine: IncrementalAttributionEngine | None = None) -> None:
        self._engine = attribution_engine or IncrementalAttributionEngine()
        self._lock = RLock()

    def ingest(self, req: AttributionIngestRequest) -> dict:
        event = CreationEvent(
            event_id=req.event_id,
            project_id=req.project_id,
            event_type=req.event_type,
            ts=req.ts,
            policy_version=req.policy_version,
            contributors=req.contributors,
            parents=req.parents,
            base_weight=req.base_weight,
        )
        try:
            with self._lock:
                created = self._engine.add_event(event)
                status = "accepted" if created else "duplicate"
                return {
                    "event_id": req.event_id,
                    "project_id": req.project_id,
                    "status": status,
                }
        except IAREError as exc:
            raise AttributionApiError(exc.code, str(exc)) from exc

    def payout_preview(self, req: PayoutPreviewRequest) -> PayoutSnapshot:
        try:
            with self._lock:
                return self._engine.build_payout_snapshot(
                    project_id=req.project_id,
                    policy_version=req.policy_version,
                    total_value=req.total_value,
                )
        except IAREError as exc:
            raise AttributionApiError(exc.code, str(exc)) from exc

    def replay_verify(self, req: PayoutReplayRequest) -> dict:
        snapshot = self.payout_preview(
            PayoutPreviewRequest(
                project_id=req.project_id,
                policy_version=req.policy_version,
                total_value=req.total_value,
            )
        )
        return {
            "project_id": req.project_id,
            "policy_version": req.policy_version,
            "input_snapshot_hash": snapshot.input_snapshot_hash,
            "output_payout_hash": snapshot.output_payout_hash,
            "input_hash_match": snapshot.input_snapshot_hash == req.expected_input_snapshot_hash,
            "output_hash_match": snapshot.output_payout_hash == req.expected_output_payout_hash,
        }
