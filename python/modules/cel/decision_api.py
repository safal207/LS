from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import RLock
from time import time
from typing import Callable

from .wallet_api import CELWalletAPI, TransferReceipt, TransferRequest


class DecisionApiError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProposalCreateRequest:
    trace_id: str
    proposal_id: str
    agent_id: str
    asset: str
    prediction: str
    confidence: float
    price_ct: Decimal
    ttl_sec: int


@dataclass(frozen=True)
class ProposalBuyRequest:
    trace_id: str
    proposal_id: str
    buyer_agent_id: str


@dataclass(frozen=True)
class ProposalSubscribeRequest:
    trace_id: str
    proposal_id: str
    subscriber_agent_id: str


class DecisionListingAPI:
    """In-memory Sprint 3 Decision Listing API.

    Responsibilities:
    - create/list/get proposals
    - buy proposal via CELWalletAPI
    - subscribe to proposal signals
    - publish CEM events for proposal_created / proposal_sold
    """

    def __init__(
        self,
        wallet_api: CELWalletAPI,
        publish_cem_event: Callable[[dict], None] | None = None,
    ) -> None:
        self._wallet_api = wallet_api
        self._publish_cem_event = publish_cem_event
        self._lock = RLock()
        self._proposals: dict[str, dict] = {}
        self._access: dict[str, set[str]] = {}
        self._subscriptions: dict[str, set[str]] = {}

    def create(self, req: ProposalCreateRequest) -> dict:
        if not req.trace_id.startswith("trace_"):
            raise DecisionApiError("INVALID_TRACE_ID", "trace_id must start with 'trace_'")
        if req.ttl_sec <= 0:
            raise DecisionApiError("INVALID_TTL", "ttl_sec must be > 0")
        if req.price_ct <= 0:
            raise DecisionApiError("INVALID_PRICE", "price_ct must be > 0")
        if not req.proposal_id:
            raise DecisionApiError("INVALID_PROPOSAL_ID", "proposal_id is required")

        now = int(time())
        with self._lock:
            if req.proposal_id in self._proposals:
                raise DecisionApiError("PROPOSAL_ALREADY_EXISTS", "proposal already exists")

            proposal = {
                "proposal_id": req.proposal_id,
                "agent_id": req.agent_id,
                "asset": req.asset,
                "prediction": req.prediction,
                "confidence": req.confidence,
                "price_ct": req.price_ct,
                "ttl_sec": req.ttl_sec,
                "created_at": now,
                "expires_at": now + req.ttl_sec,
                "status": "active",
                "sold_to": None,
            }
            self._proposals[req.proposal_id] = proposal
            self._access[req.proposal_id] = {req.agent_id}
            self._subscriptions[req.proposal_id] = set()

            event = {
                "trace_id": req.trace_id,
                "event_type": "proposal_created",
                "proposal_id": req.proposal_id,
                "agent_id": req.agent_id,
            }
            if self._publish_cem_event:
                self._publish_cem_event(event)

            return proposal.copy()

    def list(self) -> list[dict]:
        with self._lock:
            self._refresh_expired_locked()
            return [proposal.copy() for proposal in self._proposals.values()]

    def get(self, proposal_id: str) -> dict:
        with self._lock:
            self._refresh_expired_locked()
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise DecisionApiError("PROPOSAL_NOT_FOUND", "proposal not found")
            return proposal.copy()

    def buy(self, req: ProposalBuyRequest) -> dict:
        with self._lock:
            self._refresh_expired_locked()
            proposal = self._proposals.get(req.proposal_id)
            if not proposal:
                raise DecisionApiError("PROPOSAL_NOT_FOUND", "proposal not found")
            if proposal["status"] != "active":
                raise DecisionApiError("PROPOSAL_NOT_ACTIVE", "proposal is not active")

            transfer_receipt: TransferReceipt = self._wallet_api.transfer(
                TransferRequest(
                    trace_id=req.trace_id,
                    proposal_id=req.proposal_id,
                    from_agent_id=req.buyer_agent_id,
                    to_agent_id=proposal["agent_id"],
                    amount_ct=Decimal(str(proposal["price_ct"])),
                )
            )

            proposal["status"] = "sold"
            proposal["sold_to"] = req.buyer_agent_id
            self._access[req.proposal_id].add(req.buyer_agent_id)

            event = {
                "trace_id": req.trace_id,
                "event_type": "proposal_sold",
                "proposal_id": req.proposal_id,
                "buyer_agent_id": req.buyer_agent_id,
            }
            if self._publish_cem_event:
                self._publish_cem_event(event)

            return {
                "proposal_id": req.proposal_id,
                "status": proposal["status"],
                "sold_to": proposal["sold_to"],
                "tx_ref": transfer_receipt.tx_ref,
            }

    def subscribe(self, req: ProposalSubscribeRequest) -> dict:
        with self._lock:
            self._refresh_expired_locked()
            proposal = self._proposals.get(req.proposal_id)
            if not proposal:
                raise DecisionApiError("PROPOSAL_NOT_FOUND", "proposal not found")
            if proposal["status"] == "archived":
                raise DecisionApiError("PROPOSAL_ARCHIVED", "cannot subscribe archived proposal")

            self._subscriptions[req.proposal_id].add(req.subscriber_agent_id)
            return {
                "proposal_id": req.proposal_id,
                "subscriber_agent_id": req.subscriber_agent_id,
                "status": "subscribed",
            }

    def can_access(self, proposal_id: str, agent_id: str) -> bool:
        with self._lock:
            self._refresh_expired_locked()
            return agent_id in self._access.get(proposal_id, set())

    def archive(self, proposal_id: str) -> None:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise DecisionApiError("PROPOSAL_NOT_FOUND", "proposal not found")
            proposal["status"] = "archived"

    def _refresh_expired_locked(self) -> None:
        now = int(time())
        for proposal in self._proposals.values():
            if proposal["status"] == "active" and now >= proposal["expires_at"]:
                proposal["status"] = "expired"
