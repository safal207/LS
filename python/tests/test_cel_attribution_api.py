from __future__ import annotations

from decimal import Decimal

import pytest

from modules.cel import (
    AttributionApiError,
    AttributionIngestRequest,
    AttributionReplayAPI,
    ContributorImpact,
    PayoutPreviewRequest,
    PayoutReplayRequest,
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
