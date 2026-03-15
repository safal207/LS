from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

from modules.cel import CELApiError, CELWalletAPI, TransferRequest


def test_transfer_updates_balances_and_emits_ctl_event() -> None:
    events: list[dict] = []
    api = CELWalletAPI(append_ctl_event=events.append)
    api.create_wallet("trader-111", Decimal("20"))
    api.create_wallet("energy-98231", Decimal("0"))

    receipt = api.transfer(
        TransferRequest(
            trace_id="trace_01HXYZABCD",
            proposal_id="prop_003",
            from_agent_id="trader-111",
            to_agent_id="energy-98231",
            amount_ct=Decimal("10"),
        )
    )

    assert receipt.amount_ct == Decimal("10")
    assert receipt.from_balance_ct == Decimal("10")
    assert receipt.to_balance_ct == Decimal("10")

    assert len(events) == 1
    event = events[0]
    assert event["event_type"] == "proposal_purchased"
    assert event["trace_id"] == "trace_01HXYZABCD"
    assert event["data"]["proposal_id"] == "prop_003"
    assert event["data"]["amount"] == 10.0


def test_transfer_rejects_insufficient_funds_with_deterministic_code() -> None:
    api = CELWalletAPI()
    api.create_wallet("buyer", Decimal("1"))
    api.create_wallet("seller", Decimal("0"))

    with pytest.raises(CELApiError) as exc:
        api.transfer(
            TransferRequest(
                trace_id="trace_ok_value",
                proposal_id="prop_1",
                from_agent_id="buyer",
                to_agent_id="seller",
                amount_ct=Decimal("2"),
            )
        )

    assert exc.value.code == "INSUFFICIENT_FUNDS"


def test_transfer_is_atomic_under_concurrency() -> None:
    api = CELWalletAPI()
    api.create_wallet("buyer", Decimal("100"))
    api.create_wallet("seller", Decimal("0"))

    def _one_transfer() -> None:
        api.transfer(
            TransferRequest(
                trace_id="trace_concurrent_123",
                proposal_id="prop_concurrency",
                from_agent_id="buyer",
                to_agent_id="seller",
                amount_ct=Decimal("1"),
            )
        )

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(lambda _: _one_transfer(), range(100)))

    assert api.get_balance("buyer") == Decimal("0")
    assert api.get_balance("seller") == Decimal("100")


def test_transfer_rejects_unknown_wallet() -> None:
    api = CELWalletAPI()
    api.create_wallet("buyer", Decimal("10"))

    with pytest.raises(CELApiError) as exc:
        api.transfer(
            TransferRequest(
                trace_id="trace_wallet_404",
                proposal_id="prop_404",
                from_agent_id="buyer",
                to_agent_id="missing",
                amount_ct=Decimal("1"),
            )
        )

    assert exc.value.code == "WALLET_NOT_FOUND"
