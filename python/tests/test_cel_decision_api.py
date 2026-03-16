from __future__ import annotations

from decimal import Decimal
import pytest

from modules.cel import (
    CELWalletAPI,
    DecisionApiError,
    DecisionListingAPI,
    ProposalBuyRequest,
    ProposalCreateRequest,
    ProposalSubscribeRequest,
)


def _mk_api() -> tuple[DecisionListingAPI, list[dict]]:
    cem_events: list[dict] = []
    wallet = CELWalletAPI()
    wallet.create_wallet("energy-98231", Decimal("0"))
    wallet.create_wallet("trader-111", Decimal("25"))
    wallet.create_wallet("observer-007", Decimal("0"))
    api = DecisionListingAPI(wallet_api=wallet, publish_cem_event=cem_events.append)
    return api, cem_events


def test_create_list_get_and_subscribe() -> None:
    api, cem_events = _mk_api()

    created = api.create(
        ProposalCreateRequest(
            trace_id="trace_create_1",
            proposal_id="prop_003",
            agent_id="energy-98231",
            asset="oil",
            prediction="price_up_5pct_7d",
            confidence=0.87,
            price_ct=Decimal("10"),
            ttl_sec=3600,
        )
    )

    assert created["status"] == "active"
    assert api.get("prop_003")["status"] == "active"
    assert len(api.list()) == 1

    sub = api.subscribe(
        ProposalSubscribeRequest(
            trace_id="trace_sub_1",
            proposal_id="prop_003",
            subscriber_agent_id="observer-007",
        )
    )
    assert sub["status"] == "subscribed"

    assert cem_events[0]["event_type"] == "proposal_created"


def test_buy_updates_status_emits_sold_event_and_grants_access() -> None:
    api, cem_events = _mk_api()

    api.create(
        ProposalCreateRequest(
            trace_id="trace_create_2",
            proposal_id="prop_004",
            agent_id="energy-98231",
            asset="oil",
            prediction="sideways",
            confidence=0.55,
            price_ct=Decimal("10"),
            ttl_sec=3600,
        )
    )

    receipt = api.buy(
        ProposalBuyRequest(
            trace_id="trace_buy_2",
            proposal_id="prop_004",
            buyer_agent_id="trader-111",
        )
    )

    assert receipt["status"] == "sold"
    assert receipt["sold_to"] == "trader-111"
    assert api.can_access("prop_004", "trader-111") is True
    assert api.get("prop_004")["status"] == "sold"

    assert cem_events[-1]["event_type"] == "proposal_sold"


def test_proposal_expiration_to_expired_status(monkeypatch: pytest.MonkeyPatch) -> None:
    api, _ = _mk_api()

    import modules.cel.decision_api as decision_api_module

    now = 1_710_000_000
    monkeypatch.setattr(decision_api_module, "time", lambda: now)

    api.create(
        ProposalCreateRequest(
            trace_id="trace_create_expire",
            proposal_id="prop_expire",
            agent_id="energy-98231",
            asset="gas",
            prediction="down_2pct",
            confidence=0.6,
            price_ct=Decimal("3"),
            ttl_sec=1,
        )
    )

    monkeypatch.setattr(decision_api_module, "time", lambda: now + 2)
    assert api.get("prop_expire")["status"] == "expired"


def test_buy_rejects_non_active_proposal() -> None:
    api, _ = _mk_api()
    api.create(
        ProposalCreateRequest(
            trace_id="trace_create_3",
            proposal_id="prop_005",
            agent_id="energy-98231",
            asset="oil",
            prediction="flat",
            confidence=0.51,
            price_ct=Decimal("10"),
            ttl_sec=3600,
        )
    )
    api.archive("prop_005")

    with pytest.raises(DecisionApiError) as exc:
        api.buy(
            ProposalBuyRequest(
                trace_id="trace_buy_3",
                proposal_id="prop_005",
                buyer_agent_id="trader-111",
            )
        )

    assert exc.value.code == "PROPOSAL_NOT_ACTIVE"
