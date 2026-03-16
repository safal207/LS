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


@dataclass(frozen=True)
class RecomputePayoutsRequest:
    project_id: str
    policy_version: str
    window_days: int
    total_value: Decimal


@dataclass(frozen=True)
class OpenDisputeRequest:
    payout_id: int
    reason: str


@dataclass(frozen=True)
class ResolveDisputeRequest:
    payout_id: int
    approve: bool
    approver: str


class AttributionReplayAPI:
    """In-memory facade for IARE ingestion, anti-gaming and payout governance lifecycle."""

    def __init__(
        self,
        attribution_engine: IncrementalAttributionEngine | None = None,
        governance_threshold: Decimal = Decimal("10"),
        burst_limit_per_actor: int = 20,
    ) -> None:
        self._engine = attribution_engine or IncrementalAttributionEngine()
        self._governance_threshold = governance_threshold
        self._burst_limit_per_actor = burst_limit_per_actor
        self._lock = RLock()

        self._actor_ingest_counts: dict[tuple[str, str], int] = {}
        self._payout_id_seq = 0
        self._payouts: dict[int, dict] = {}

    def ingest(self, req: AttributionIngestRequest) -> dict:
        self._validate_window_inputs(req)
        # anti-gaming: quarantine bursty actors per project
        for contributor in req.contributors:
            key = (req.project_id, contributor.agent_id)
            next_count = self._actor_ingest_counts.get(key, 0) + 1
            self._actor_ingest_counts[key] = next_count
            if next_count > self._burst_limit_per_actor:
                return {
                    "event_id": req.event_id,
                    "project_id": req.project_id,
                    "status": "quarantined",
                    "reason": "BURST_LIMIT_EXCEEDED",
                }

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

    def recompute_payouts(self, req: RecomputePayoutsRequest) -> list[dict]:
        if req.window_days not in (7, 30, 90):
            raise AttributionApiError("INVALID_WINDOW", "window_days must be one of 7, 30, 90")

        snapshot = self.payout_preview(
            PayoutPreviewRequest(
                project_id=req.project_id,
                policy_version=req.policy_version,
                total_value=req.total_value,
            )
        )
        with self._lock:
            created: list[dict] = []
            for line in snapshot.lines:
                self._payout_id_seq += 1
                payout_id = self._payout_id_seq
                status = "pending_dispute" if line.payout >= self._governance_threshold else "ready_to_pay"
                rec = {
                    "payout_id": payout_id,
                    "project_id": req.project_id,
                    "window_days": req.window_days,
                    "policy_version": req.policy_version,
                    "agent_id": line.agent_id,
                    "amount": line.payout,
                    "status": status,
                    "input_snapshot_hash": snapshot.input_snapshot_hash,
                    "output_payout_hash": snapshot.output_payout_hash,
                    "dispute_reason": None,
                    "dispute_approver": None,
                }
                self._payouts[payout_id] = rec
                created.append(rec.copy())
            return created

    def open_dispute(self, req: OpenDisputeRequest) -> dict:
        with self._lock:
            payout = self._must_get_payout(req.payout_id)
            if payout["status"] == "paid":
                raise AttributionApiError("INVALID_PAYOUT_STATE", "cannot dispute paid payout")
            payout["status"] = "pending_dispute"
            payout["dispute_reason"] = req.reason
            return payout.copy()

    def resolve_dispute(self, req: ResolveDisputeRequest) -> dict:
        with self._lock:
            payout = self._must_get_payout(req.payout_id)
            if payout["status"] != "pending_dispute":
                raise AttributionApiError("INVALID_PAYOUT_STATE", "payout is not pending_dispute")
            payout["status"] = "ready_to_pay" if req.approve else "rejected"
            payout["dispute_approver"] = req.approver
            return payout.copy()

    def execute_payout(self, payout_id: int) -> dict:
        with self._lock:
            payout = self._must_get_payout(payout_id)
            if payout["status"] != "ready_to_pay":
                raise AttributionApiError("INVALID_PAYOUT_STATE", "payout is not ready_to_pay")
            payout["status"] = "paid"
            return payout.copy()

    def list_payouts(self, project_id: str) -> list[dict]:
        with self._lock:
            payouts = [p.copy() for p in self._payouts.values() if p["project_id"] == project_id]
            return sorted(payouts, key=lambda p: p["payout_id"])

    @staticmethod
    def _validate_window_inputs(req: AttributionIngestRequest) -> None:
        if not req.event_type:
            raise AttributionApiError("INVALID_EVENT_TYPE", "event_type is required")

    def _must_get_payout(self, payout_id: int) -> dict:
        payout = self._payouts.get(payout_id)
        if payout is None:
            raise AttributionApiError("PAYOUT_NOT_FOUND", "payout not found")
        return payout
