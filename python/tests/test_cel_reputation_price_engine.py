from __future__ import annotations

from decimal import Decimal

import pytest

from modules.cel import (
    CELWalletAPI,
    DecisionListingAPI,
    PriceEngine,
    PriceInput,
    PriceEngineError,
    ProposalCreateRequest,
    ReputationEngine,
)


def test_reputation_engine_updates_with_quality_and_contribution() -> None:
    engine = ReputationEngine(quality_weight=0.3, contribution_weight=0.2, decay=0.1)

    before = engine.get("energy-98231")
    after = engine.update("energy-98231", quality_score=0.9, contribution_score=0.7)

    assert before.reputation_score == 0.5
    assert after.reputation_score > before.reputation_score
    assert after.updates_count == 1


def test_reputation_engine_decay_under_low_quality() -> None:
    engine = ReputationEngine(quality_weight=0.2, contribution_weight=0.0, decay=0.2)
    engine.update("agent-decay", quality_score=1.0, contribution_score=0.0)
    prev = engine.get("agent-decay")
    for _ in range(5):
        engine.update("agent-decay", quality_score=0.0, contribution_score=0.0)
    curr = engine.get("agent-decay")
    assert curr.reputation_score < prev.reputation_score


def test_price_engine_formula_and_band() -> None:
    engine = PriceEngine(alpha=0.4, beta=0.2, gamma=0.3, band_pct=0.1)
    quote = engine.quote(
        PriceInput(
            base_price_ct=Decimal("10"),
            reputation_score=0.5,
            demand_index=1.0,
            confidence_calibrated=0.8,
            risk_discount=1.0,
        )
    )

    assert quote.price_ct == Decimal("17.856000")
    assert quote.suggested_resonance_band_min == Decimal("16.070400")
    assert quote.suggested_resonance_band_max == Decimal("19.641600")


def test_price_engine_rejects_bad_input() -> None:
    engine = PriceEngine()
    with pytest.raises(PriceEngineError):
        engine.quote(
            PriceInput(
                base_price_ct=Decimal("10"),
                reputation_score=2.0,
                demand_index=0.0,
                confidence_calibrated=0.5,
                risk_discount=1.0,
            )
        )


def test_decision_api_uses_reputation_and_price_engines() -> None:
    wallet = CELWalletAPI()
    wallet.create_wallet("energy-98231", Decimal("100"))

    reputation = ReputationEngine()
    reputation.update("energy-98231", quality_score=0.95, contribution_score=0.9)
    pricing = PriceEngine()

    api = DecisionListingAPI(wallet_api=wallet, reputation_engine=reputation, price_engine=pricing)

    created = api.create(
        ProposalCreateRequest(
            trace_id="trace_price_1",
            proposal_id="prop_dynamic_1",
            agent_id="energy-98231",
            asset="oil",
            prediction="up",
            confidence=0.9,
            price_ct=Decimal("10"),
            ttl_sec=3600,
            demand_index=1.0,
            risk_discount=1.0,
        )
    )

    assert created["price_ct"] > Decimal("10")
    assert created["suggested_resonance_band_min"] is not None
    assert created["suggested_resonance_band_max"] is not None


def test_reputation_engine_normalizes_contribution_ema() -> None:
    engine = ReputationEngine()
    updated = engine.update("agent-x", quality_score=0.7, contribution_score=5.0)

    assert 0 <= updated.contribution_ema <= 1
