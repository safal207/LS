from __future__ import annotations

import json
from pathlib import Path

import pytest

from identity_catalog_trigger_fixtures import (
    build_committed_timeline,
    visibility_for,
)
from identity_timeline_api_fixtures import build_timeline_bundle
from trusted_runtime import identity_catalog_trigger as trigger
from trusted_runtime.identity_catalog_trigger import (
    OUTBOX_TRAIL_ID,
    IdentityTimelineCommitReceipt,
    append_timeline_commit_request,
    process_identity_catalog_triggers,
    reconcile_timeline_commit_receipts,
)
from trusted_runtime.persistence import JsonlEventStoreAdapter


def _process(fixture, visibility, *, processed_at="2026-06-24T04:10:00Z"):
    return process_identity_catalog_triggers(
        fixture["data_root"],
        fixture["outbox_path"],
        fixture["publisher_output_root"],
        fixture["trigger_output_root"],
        keyring=fixture["keyring"],
        active_key_id="key-old",
        signing_key_ids=("key-old",),
        audience="internal",
        visibility_policy=visibility,
        processed_at=processed_at,
        stale_after_seconds=86400,
    )


def test_reconcile_recovers_complete_bundle_missing_outbox_delivery(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    fixture = build_timeline_bundle(data_root, "agent:reconcile")
    outbox = tmp_path / "outbox.jsonl"

    first = reconcile_timeline_commit_receipts(
        data_root,
        outbox,
        reconciled_at="2026-06-24T04:05:00Z",
    )
    second = reconcile_timeline_commit_receipts(
        data_root,
        outbox,
        reconciled_at="2026-06-24T04:10:00Z",
    )
    events = JsonlEventStoreAdapter(outbox).read_events(OUTBOX_TRAIL_ID)

    assert len(first) == 1
    assert second == first
    assert len(events) == 1
    assert (fixture["bundle"] / "identity-timeline-commit.json").exists()


def test_partial_bundle_without_projection_never_enters_outbox(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    fixture = build_timeline_bundle(data_root, "agent:partial")
    fixture["timeline_path"].unlink()
    outbox = tmp_path / "outbox.jsonl"

    refs = reconcile_timeline_commit_receipts(
        data_root,
        outbox,
        reconciled_at="2026-06-24T04:05:00Z",
    )

    assert refs == ()
    assert JsonlEventStoreAdapter(outbox).read_events(OUTBOX_TRAIL_ID) == ()


def test_incomplete_bundle_is_quarantined_then_resumes_when_restored(
    tmp_path: Path,
) -> None:
    fixture = build_committed_timeline(tmp_path, "agent:quarantine")
    timeline_bytes = fixture["timeline_path"].read_bytes()
    fixture["timeline_path"].unlink()
    visibility = visibility_for("agent:quarantine")

    blocked = _process(fixture, visibility)
    assert blocked.publication is None
    assert blocked.processed_request_ids == ()
    assert blocked.pending_request_ids == (fixture["receipt"].request_id,)
    assert len(blocked.quarantined) == 1
    health = json.loads(blocked.health_path.read_text(encoding="utf-8"))
    assert health["read_only"] is True
    assert health["pending_request_count"] == 1
    assert health["quarantined_request_count"] == 1

    fixture["timeline_path"].write_bytes(timeline_bytes)
    recovered = _process(
        fixture,
        visibility,
        processed_at="2026-06-24T04:20:00Z",
    )
    assert recovered.publication is not None
    assert recovered.publication.publication.generation == 1
    assert recovered.pending_request_ids == ()
    assert recovered.quarantined == ()


def test_restart_after_publish_before_checkpoint_recovers_same_generation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = build_committed_timeline(tmp_path, "agent:resume")
    visibility = visibility_for("agent:resume")
    original = trigger._atomic_write_json

    def fail_state(path, payload):
        if path.name == "identity-catalog-trigger-state.json":
            raise RuntimeError("simulated checkpoint interruption")
        original(path, payload)

    monkeypatch.setattr(trigger, "_atomic_write_json", fail_state)
    with pytest.raises(RuntimeError, match="checkpoint interruption"):
        _process(fixture, visibility)

    publication_path = (
        fixture["publisher_output_root"] / "identity-catalog-publication.json"
    )
    assert json.loads(publication_path.read_text())["generation"] == 1
    assert not (
        fixture["trigger_output_root"] / "identity-catalog-trigger-state.json"
    ).exists()

    monkeypatch.setattr(trigger, "_atomic_write_json", original)
    recovered = _process(
        fixture,
        visibility,
        processed_at="2026-06-24T04:20:00Z",
    )
    assert recovered.publication is not None
    assert recovered.publication.changed is False
    assert recovered.publication.publication.generation == 1
    assert recovered.pending_request_ids == ()
    assert len(tuple((fixture["publisher_output_root"] / "history").glob("*.json"))) == 1


def test_multiple_same_agent_receipts_coalesce_into_one_generation(
    tmp_path: Path,
) -> None:
    fixture = build_committed_timeline(tmp_path, "agent:coalesced")
    first = fixture["receipt"]
    second = IdentityTimelineCommitReceipt.build(
        agent_id=first.agent_id,
        bundle_path=first.bundle_path,
        task_id=first.task_id,
        trail_id=first.trail_id,
        tail_event_ref=first.tail_event_ref,
        event_count=first.event_count,
        timeline_digest=first.timeline_digest,
        committed_at="2026-06-24T04:06:00Z",
    )
    append_timeline_commit_request(fixture["outbox_path"], second)

    result = _process(fixture, visibility_for("agent:coalesced"))
    batch = json.loads(result.trigger_batch_path.read_text(encoding="utf-8"))

    assert result.publication.publication.generation == 1
    assert set(result.processed_request_ids) == {
        first.request_id,
        second.request_id,
    }
    assert batch["request_ids"] == [first.request_id, second.request_id]
    assert batch["trigger_tail_event_refs"] == [
        first.tail_event_ref,
        second.tail_event_ref,
    ]
