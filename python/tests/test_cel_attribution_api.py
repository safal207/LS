from __future__ import annotations

from decimal import Decimal

import pytest

from modules.cel import (
    AttributionApiError,
    AttributionIngestRequest,
    AttributionReplayAPI,
    ContributorImpact,
    OpenDisputeRequest,
    PayoutPreviewRequest,
    PayoutReplayRequest,
    RecomputePayoutsRequest,
    ResolveDisputeRequest,
)


def _ingest(api: AttributionReplayAPI, event_id: str, parent: str | None = None, agent: str = "agent_a") -> dict:
    return api.ingest(
        AttributionIngestRequest(
            event_id=event_id,
            project_id="proj_1",
            event_type="code_committed",
            ts=1710000000,
            policy_version="v1",
            contributors=(ContributorImpact(agent, 1.0, 1.0),),
            parents=(parent,) if parent else (),
        )
    )


def test_ingest_returns_duplicate_for_same_event_id() -> None:
    api = AttributionReplayAPI()
    req = AttributionIngestRequest(
        event_id="evt_1",
        project_id="proj_1",
        event_type="code_committed",
        ts=1710000000,
        policy_version="v1",
        contributors=(ContributorImpact("agent_a", 1.0, 1.0),),
    )

    first = api.ingest(req)
    second = api.ingest(req)

    assert first["status"] == "accepted"
    assert second["status"] == "duplicate"


def test_ingest_rejects_missing_parent() -> None:
    api = AttributionReplayAPI()
    with pytest.raises(AttributionApiError) as exc:
        api.ingest(
            AttributionIngestRequest(
                event_id="evt_child",
                project_id="proj_1",
                event_type="code_committed",
                ts=1710000001,
                policy_version="v1",
                contributors=(ContributorImpact("agent_b", 1.0, 1.0),),
                parents=("evt_missing",),
            )
        )

    assert exc.value.code == "MISSING_PARENT"


def test_replay_verify_matches_stored_hashes() -> None:
    api = AttributionReplayAPI()
    _ingest(api, "evt_1", agent="agent_a")
    api.ingest(
        AttributionIngestRequest(
            event_id="evt_2",
            project_id="proj_1",
            event_type="test_added",
            ts=1710000001,
            policy_version="v1",
            contributors=(ContributorImpact("agent_b", 1.0, 0.8),),
            parents=("evt_1",),
        )
    )

    preview = api.payout_preview(
        PayoutPreviewRequest(project_id="proj_1", policy_version="v1", total_value=Decimal("50"))
    )
    replay = api.replay_verify(
        PayoutReplayRequest(
            project_id="proj_1",
            policy_version="v1",
            total_value=Decimal("50"),
            expected_input_snapshot_hash=preview.input_snapshot_hash,
            expected_output_payout_hash=preview.output_payout_hash,
        )
    )

    assert replay["input_hash_match"] is True
    assert replay["output_hash_match"] is True


def test_payout_preview_surfaces_engine_validation_errors() -> None:
    api = AttributionReplayAPI()
    with pytest.raises(AttributionApiError) as exc:
        api.payout_preview(
            PayoutPreviewRequest(project_id="missing", policy_version="v1", total_value=Decimal("10"))
        )
    assert exc.value.code == "NO_SCORES"


def test_recompute_windows_and_governance_lifecycle() -> None:
    api = AttributionReplayAPI(governance_threshold=Decimal("25"))
    _ingest(api, "evt_1", agent="agent_a")
    _ingest(api, "evt_2", parent="evt_1", agent="agent_b")

    payouts = api.recompute_payouts(
        RecomputePayoutsRequest(
            project_id="proj_1",
            policy_version="v1",
            window_days=7,
            total_value=Decimal("100"),
        )
    )
    assert len(payouts) == 2
    assert {p["status"] for p in payouts} == {"pending_dispute"}

    p0 = payouts[0]["payout_id"]
    disputed = api.open_dispute(OpenDisputeRequest(payout_id=p0, reason="manual_review"))
    assert disputed["status"] == "pending_dispute"

    resolved = api.resolve_dispute(ResolveDisputeRequest(payout_id=p0, approve=True, approver="gov_1"))
    assert resolved["status"] == "ready_to_pay"

    paid = api.execute_payout(p0)
    assert paid["status"] == "paid"


def test_invalid_window_is_rejected() -> None:
    api = AttributionReplayAPI()
    _ingest(api, "evt_1")
    with pytest.raises(AttributionApiError) as exc:
        api.recompute_payouts(
            RecomputePayoutsRequest(
                project_id="proj_1",
                policy_version="v1",
                window_days=14,
                total_value=Decimal("10"),
            )
        )
    assert exc.value.code == "INVALID_WINDOW"


def test_burst_limit_causes_quarantine() -> None:
    api = AttributionReplayAPI(burst_limit_per_actor=1)
    first = _ingest(api, "evt_1", agent="agent_a")
    second = _ingest(api, "evt_2", agent="agent_a")

    assert first["status"] == "accepted"
    assert second["status"] == "quarantined"
    assert second["reason"] == "BURST_LIMIT_EXCEEDED"
