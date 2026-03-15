from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from threading import RLock
from time import time
from typing import Callable
from uuid import uuid4


class CELApiError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TransferRequest:
    trace_id: str
    proposal_id: str
    from_agent_id: str
    to_agent_id: str
    amount_ct: Decimal


@dataclass(frozen=True)
class TransferReceipt:
    tx_ref: str
    from_agent_id: str
    to_agent_id: str
    amount_ct: Decimal
    from_balance_ct: Decimal
    to_balance_ct: Decimal


class CELWalletAPI:
    """In-memory wallet and transfer API with atomic updates and CTL audit callback."""

    def __init__(self, append_ctl_event: Callable[[dict], None] | None = None) -> None:
        self._balances: dict[str, Decimal] = {}
        self._lock = RLock()
        self._append_ctl_event = append_ctl_event

    def create_wallet(self, agent_id: str, initial_balance_ct: Decimal = Decimal("0")) -> None:
        if not agent_id:
            raise CELApiError("INVALID_AGENT_ID", "agent_id is required")
        if initial_balance_ct < 0:
            raise CELApiError("INVALID_INITIAL_BALANCE", "initial_balance_ct must be >= 0")

        with self._lock:
            self._balances[agent_id] = initial_balance_ct

    def get_balance(self, agent_id: str) -> Decimal:
        with self._lock:
            if agent_id not in self._balances:
                raise CELApiError("WALLET_NOT_FOUND", f"wallet not found for agent_id={agent_id}")
            return self._balances[agent_id]

    def transfer(self, req: TransferRequest) -> TransferReceipt:
        if req.amount_ct <= 0:
            raise CELApiError("INVALID_AMOUNT", "amount_ct must be > 0")
        if req.from_agent_id == req.to_agent_id:
            raise CELApiError("SAME_WALLET", "from_agent_id and to_agent_id must differ")
        if not req.trace_id.startswith("trace_"):
            raise CELApiError("INVALID_TRACE_ID", "trace_id must start with 'trace_'")
        if not req.proposal_id:
            raise CELApiError("INVALID_PROPOSAL_ID", "proposal_id is required")

        with self._lock:
            if req.from_agent_id not in self._balances:
                raise CELApiError("WALLET_NOT_FOUND", f"wallet not found for agent_id={req.from_agent_id}")
            if req.to_agent_id not in self._balances:
                raise CELApiError("WALLET_NOT_FOUND", f"wallet not found for agent_id={req.to_agent_id}")

            from_balance = self._balances[req.from_agent_id]
            to_balance = self._balances[req.to_agent_id]

            if from_balance < req.amount_ct:
                raise CELApiError("INSUFFICIENT_FUNDS", "insufficient funds")

            next_from = from_balance - req.amount_ct
            next_to = to_balance + req.amount_ct

            self._balances[req.from_agent_id] = next_from
            self._balances[req.to_agent_id] = next_to

            tx_ref = f"tx_{uuid4().hex}"
            event = {
                "event_id": f"evt_{uuid4().hex[:12]}",
                "trace_id": req.trace_id,
                "event_type": "proposal_purchased",
                "ts": int(time()),
                "producer": "cel-wallet-api",
                "schema_version": "1.0",
                "signature": "ed25519:unsigned-local",
                "data": {
                    "proposal_id": req.proposal_id,
                    "buyer_agent_id": req.from_agent_id,
                    "seller_agent_id": req.to_agent_id,
                    "amount": float(req.amount_ct),
                    "currency": "CT",
                    "tx_ref": tx_ref,
                },
            }

            if self._append_ctl_event:
                self._append_ctl_event(event)

            return TransferReceipt(
                tx_ref=tx_ref,
                from_agent_id=req.from_agent_id,
                to_agent_id=req.to_agent_id,
                amount_ct=req.amount_ct,
                from_balance_ct=next_from,
                to_balance_ct=next_to,
            )
