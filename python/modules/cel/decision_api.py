from __future__ import annotations

import heapq
from collections import defaultdict, deque
from dataclasses import dataclass
from decimal import Decimal
from threading import RLock
from time import time
from typing import Callable

from .price_engine import PriceEngine, PriceInput
from .reputation_engine import ReputationEngine
from .wallet_api import CELApiError, CELWalletAPI, TransferReceipt, TransferRequest


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
    demand_index: float = 0.0
    risk_discount: float = 1.0


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
    """In-memory Decision Listing API with stake gate + per-agent rate limiting."""

    def __init__(
        self,
        wallet_api: CELWalletAPI,
        publish_cem_event: Callable[[dict], None] | None = None,
        reputation_engine: ReputationEngine | None = None,
        price_engine: PriceEngine | None = None,
        min_stake_ct: Decimal = Decimal("5"),
        create_rate_limit_per_hour: int = 10,
        buy_rate_limit_per_hour: int = 10,
        stake_vault_agent_id: str = "cel-stake-vault",
    ) -> None:
        self._wallet_api = wallet_api
        self._publish_cem_event = publish_cem_event
        self._reputation_engine = reputation_engine
        self._price_engine = price_engine
        self._min_stake_ct = min_stake_ct
        self._create_rate_limit_per_hour = create_rate_limit_per_hour
        self._buy_rate_limit_per_hour = buy_rate_limit_per_hour
        self._stake_vault_agent_id = stake_vault_agent_id

        self._lock = RLock()
        self._proposals: dict[str, dict] = {}
        self._access: dict[str, set[str]] = {}
        self._subscriptions: dict[str, set[str]] = {}
        self._expiry_heap: list[tuple[int, str]] = []
        self._create_requests: dict[str, deque[int]] = defaultdict(deque)
        self._buy_requests: dict[str, deque[int]] = defaultdict(deque)

        try:
            self._wallet_api.get_balance(stake_vault_agent_id)
        except CELApiError:
            self._wallet_api.create_wallet(stake_vault_agent_id, Decimal("0"))

    def create(self, req: ProposalCreateRequest) -> dict:
        if not req.trace_id.startswith("trace_"):
            raise DecisionApiError("INVALID_TRACE_ID", "trace_id must start with 'trace_'")
        if req.ttl_sec <= 0:
            raise DecisionApiError("INVALID_TTL", "ttl_sec must be > 0")
        if req.price_ct <= 0:
            raise DecisionApiError("INVALID_PRICE", "price_ct must be > 0")
        if req.price_ct < self._min_stake_ct:
            raise DecisionApiError("MIN_STAKE_NOT_MET", f"minimum stake is {self._min_stake_ct} CT")
        if not req.proposal_id:
            raise DecisionApiError("INVALID_PROPOSAL_ID", "proposal_id is required")

        now = int(time())
        with self._lock:
            self._check_rate_limit(self._create_requests[req.agent_id], now, "CREATE_RATE_LIMIT", self._create_rate_limit_per_hour)
            self._refresh_expired_locked(now)

            if req.proposal_id in self._proposals:
                raise DecisionApiError("PROPOSAL_ALREADY_EXISTS", "proposal already exists")

            try:
                self._wallet_api.transfer(
                    TransferRequest(
                        trace_id=req.trace_id,
                        proposal_id=f"{req.proposal_id}:stake",
                        from_agent_id=req.agent_id,
                        to_agent_id=self._stake_vault_agent_id,
                        amount_ct=self._min_stake_ct,
                    )
                )
            except CELApiError as exc:
                raise DecisionApiError(exc.code, str(exc)) from exc

            dynamic_price = req.price_ct
            band_min: Decimal | None = None
            band_max: Decimal | None = None

            if self._price_engine:
                reputation_score = 0.5
                if self._reputation_engine:
                    reputation_score = self._reputation_engine.get(req.agent_id).reputation_score
                quote = self._price_engine.quote(
                    PriceInput(
                        base_price_ct=req.price_ct,
                        reputation_score=reputation_score,
                        demand_index=req.demand_index,
                        confidence_calibrated=req.confidence,
                        risk_discount=req.risk_discount,
                    )
                )
                dynamic_price = quote.price_ct
                band_min = quote.suggested_resonance_band_min
                band_max = quote.suggested_resonance_band_max

            proposal = {
                "proposal_id": req.proposal_id,
                "agent_id": req.agent_id,
                "asset": req.asset,
                "prediction": req.prediction,
                "confidence": req.confidence,
                "price_ct": dynamic_price,
                "base_price_ct": req.price_ct,
                "stake_ct": self._min_stake_ct,
                "suggested_resonance_band_min": band_min,
                "suggested_resonance_band_max": band_max,
                "ttl_sec": req.ttl_sec,
                "created_at": now,
                "expires_at": now + req.ttl_sec,
                "status": "active",
                "sold_to": None,
            }
            self._proposals[req.proposal_id] = proposal
            self._access[req.proposal_id] = {req.agent_id}
            self._subscriptions[req.proposal_id] = set()
            heapq.heappush(self._expiry_heap, (proposal["expires_at"], req.proposal_id))

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
            self._refresh_expired_locked(int(time()))
            return [proposal.copy() for proposal in self._proposals.values()]

    def get(self, proposal_id: str) -> dict:
        with self._lock:
            self._refresh_expired_locked(int(time()))
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise DecisionApiError("PROPOSAL_NOT_FOUND", "proposal not found")
            return proposal.copy()

    def buy(self, req: ProposalBuyRequest) -> dict:
        now = int(time())
        with self._lock:
            self._check_rate_limit(self._buy_requests[req.buyer_agent_id], now, "BUY_RATE_LIMIT", self._buy_rate_limit_per_hour)
            self._refresh_expired_locked(now)
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
            self._refresh_expired_locked(int(time()))
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
            self._refresh_expired_locked(int(time()))
            return agent_id in self._access.get(proposal_id, set())

    def archive(self, proposal_id: str) -> None:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                raise DecisionApiError("PROPOSAL_NOT_FOUND", "proposal not found")
            proposal["status"] = "archived"

    def _refresh_expired_locked(self, now: int) -> None:
        while self._expiry_heap and self._expiry_heap[0][0] <= now:
            _, proposal_id = heapq.heappop(self._expiry_heap)
            proposal = self._proposals.get(proposal_id)
            if proposal and proposal["status"] == "active" and now >= proposal["expires_at"]:
                proposal["status"] = "expired"

    def _check_rate_limit(self, events: deque[int], now: int, code: str, limit: int) -> None:
        threshold = now - 3600
        while events and events[0] <= threshold:
            events.popleft()
        if len(events) >= limit:
            raise DecisionApiError(code, "rate limit exceeded")
        events.append(now)
