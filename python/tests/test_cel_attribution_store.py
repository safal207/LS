from __future__ import annotations

from decimal import Decimal

from modules.cel import (
    AttributionIngestRequest,
    AttributionReplayAPI,
    AttributionStore,
    ContributorImpact,
    OpenDisputeRequest,
    RecomputePayoutsRequest,
    ResolveDisputeRequest,
)


def _seed(api: AttributionReplayAPI) -> None:
    api.ingest(
        AttributionIngestRequest(
            event_id="evt_1",
            project_id="proj_1",
            event_type="code_committed",
            ts=1710000000,
            policy_version="v1",
            contributors=(ContributorImpact("agent_a", 1.0, 1.0),),
        )
    )


def test_sqlite_store_persists_payouts_across_api_instances(tmp_path) -> None:
    db_path = str(tmp_path / "iare.db")
    store = AttributionStore(db_path)
    api = AttributionReplayAPI(store=store, governance_threshold=Decimal("1"))

    _seed(api)
    payouts = api.recompute_payouts(
        RecomputePayoutsRequest(
            project_id="proj_1",
            policy_version="v1",
            window_days=7,
            total_value=Decimal("10"),
        )
    )
    assert len(payouts) == 1
    payout_id = payouts[0]["payout_id"]

    # new API instance should still see previously stored payout
    api2 = AttributionReplayAPI(store=AttributionStore(db_path))
    listed = api2.list_payouts("proj_1")
    assert len(listed) == 1
    assert listed[0]["payout_id"] == payout_id


def test_sqlite_store_persists_dispute_lifecycle(tmp_path) -> None:
    db_path = str(tmp_path / "iare_lifecycle.db")
    api = AttributionReplayAPI(store=AttributionStore(db_path), governance_threshold=Decimal("1"))
    _seed(api)

    payout = api.recompute_payouts(
        RecomputePayoutsRequest(
            project_id="proj_1",
            policy_version="v1",
            window_days=30,
            total_value=Decimal("10"),
        )
    )[0]

    payout_id = payout["payout_id"]
    api.open_dispute(OpenDisputeRequest(payout_id=payout_id, reason="check"))
    api.resolve_dispute(ResolveDisputeRequest(payout_id=payout_id, approve=True, approver="gov"))
    api.execute_payout(payout_id)

    api_reloaded = AttributionReplayAPI(store=AttributionStore(db_path))
    listed = api_reloaded.list_payouts("proj_1")
    assert listed[0]["status"] == "paid"
    assert listed[0]["dispute_approver"] == "gov"
