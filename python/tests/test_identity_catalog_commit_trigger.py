from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from identity_catalog_trigger_fixtures import (
    build_committed_timeline,
    visibility_for,
)
from trusted_runtime.identity_catalog_trigger import (
    OUTBOX_TRAIL_ID,
    append_timeline_commit_request,
    process_identity_catalog_triggers,
)
from trusted_runtime.persistence import JsonlEventStoreAdapter


ROOT = Path(__file__).resolve().parents[2]
RECEIPT_SCHEMA = ROOT / "schemas/trusted_runtime/identity_timeline_commit_receipt.schema.json"
BATCH_SCHEMA = ROOT / "schemas/trusted_runtime/identity_catalog_trigger_batch.schema.json"


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


def test_finalize_writes_commit_marker_and_durable_outbox_request(
    tmp_path: Path,
) -> None:
    fixture = build_committed_timeline(tmp_path, "agent:commit-hook")
    marker = json.loads(
        (fixture["bundle"] / "identity-timeline-commit.json").read_text()
    )
    events = JsonlEventStoreAdapter(fixture["outbox_path"]).read_events(
        OUTBOX_TRAIL_ID
    )

    assert marker == fixture["receipt"].to_dict()
    assert len(events) == 1
    assert events[0].event_id == fixture["receipt"].request_id
    assert events[0].event_ref == fixture["outbox_event_ref"]
    assert events[0].payload["payload"]["receipt"] == marker

    schema = json.loads(RECEIPT_SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(marker))


def test_redelivery_is_idempotent_even_after_another_agent_request(
    tmp_path: Path,
) -> None:
    first = build_committed_timeline(tmp_path, "agent:first")
    second = build_committed_timeline(tmp_path, "agent:second")
    duplicate_ref = append_timeline_commit_request(
        first["outbox_path"],
        first["receipt"],
    )
    events = JsonlEventStoreAdapter(first["outbox_path"]).read_events(
        OUTBOX_TRAIL_ID
    )

    assert duplicate_ref == first["outbox_event_ref"]
    assert len(events) == 2
    assert [event.event_id for event in events] == [
        first["receipt"].request_id,
        second["receipt"].request_id,
    ]


def test_two_agent_commits_publish_one_coalesced_generation(tmp_path: Path) -> None:
    first = build_committed_timeline(tmp_path, "agent:reviewer")
    second = build_committed_timeline(tmp_path, "agent:auditor")
    visibility = visibility_for("agent:reviewer", "agent:auditor")

    result = _process(first, visibility)
    publication = result.publication
    assert publication is not None
    assert publication.changed is True
    assert publication.publication.generation == 1
    assert set(result.processed_request_ids) == {
        first["receipt"].request_id,
        second["receipt"].request_id,
    }
    assert result.pending_request_ids == ()
    assert result.quarantined == ()

    batch = json.loads(result.trigger_batch_path.read_text(encoding="utf-8"))
    assert batch["generation"] == 1
    assert batch["request_ids"] == [
        first["receipt"].request_id,
        second["receipt"].request_id,
    ]
    assert batch["trigger_tail_event_refs"] == [
        first["receipt"].tail_event_ref,
        second["receipt"].tail_event_ref,
    ]
    assert batch["agent_ids"] == ["agent:auditor", "agent:reviewer"]
    assert batch["outbox_sequences"] == [0, 1]

    schema = json.loads(BATCH_SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(batch))


def test_reprocessing_same_outbox_does_not_create_generation_two(
    tmp_path: Path,
) -> None:
    fixture = build_committed_timeline(tmp_path, "agent:idempotent")
    visibility = visibility_for("agent:idempotent")
    first = _process(fixture, visibility)
    second = _process(
        fixture,
        visibility,
        processed_at="2026-06-24T04:20:00Z",
    )

    assert first.publication is not None
    assert first.publication.publication.generation == 1
    assert second.publication is None
    state = json.loads(second.state_path.read_text(encoding="utf-8"))
    assert state["last_generation"] == 1
    assert len(tuple((fixture["publisher_output_root"] / "history").glob("*.json"))) == 1


def test_new_committed_agent_triggers_generation_two_and_preserves_existing(
    tmp_path: Path,
) -> None:
    first = build_committed_timeline(tmp_path, "agent:one")
    first_result = _process(first, visibility_for("agent:one"))
    assert first_result.publication.publication.generation == 1

    second = build_committed_timeline(tmp_path, "agent:two")
    second_result = _process(
        first,
        visibility_for("agent:one", "agent:two"),
        processed_at="2026-06-24T04:20:00Z",
    )
    assert second_result.publication is not None
    assert second_result.publication.publication.generation == 2
    assert second_result.processed_request_ids == (
        second["receipt"].request_id,
    )
    assert [
        entry.agent_id for entry in second_result.publication.publication.entries
    ] == ["agent:one", "agent:two"]
