from __future__ import annotations

import json

import pytest

from identity_timeline_fixtures import lifecycle_records
from trusted_runtime.identity_timeline import (
    IdentityLifecycleEventType,
    IdentityTimelineReplayError,
    identity_task_id,
    identity_trail_id,
    persist_identity_lifecycle,
    replay_identity_timeline,
    scan_identity_timeline,
)
from trusted_runtime.persistence import (
    EventStoreCorruptionError,
    InMemoryEventStoreAdapter,
    JsonlEventStoreAdapter,
    digest_json,
)


def _agent(records):
    return records["agent_id"]["value"]


def test_application_without_commit_is_detected() -> None:
    records = lifecycle_records()
    agent_id = _agent(records)
    store = InMemoryEventStoreAdapter()
    persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=records["profile_v1"],
        proposal=records["proposal"],
        approval=records["approval"],
        patch=records["patch"],
    )
    parent = store.read_events(identity_trail_id(agent_id))[-1]
    application = records["application"]
    store.append(
        {
            "event_id": "event:test:application-without-commit",
            "task_id": identity_task_id(agent_id),
            "trail_id": identity_trail_id(agent_id),
            "event_type": IdentityLifecycleEventType.APPLICATION_RECORDED.value,
            "actor": application["activated_by"],
            "created_at": application["activated_at"],
            "parent_cause": parent.event_id,
            "evidence_refs": [application["application_id"]],
            "payload": {
                "agent_id": agent_id,
                "record_type": IdentityLifecycleEventType.APPLICATION_RECORDED.value,
                "record_digest": digest_json(application),
                "record": application,
            },
        }
    )

    projection = scan_identity_timeline(store, agent_id=agent_id)
    codes = {finding.code for finding in projection.findings}
    assert "MISSING_PATCH_COMMIT" in codes
    with pytest.raises(IdentityTimelineReplayError):
        replay_identity_timeline(store, agent_id=agent_id)


def test_duplicate_application_is_rejected_semantically() -> None:
    records = lifecycle_records()
    agent_id = _agent(records)
    store = InMemoryEventStoreAdapter()
    persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=records["profile_v1"],
        proposal=records["proposal"],
        approval=records["approval"],
        patch=records["patch"],
        commit=records["commit"],
        application=records["application"],
        profile_v2=records["profile_v2"],
    )
    parent = store.read_events(identity_trail_id(agent_id))[-1]
    application = records["application"]
    store.append(
        {
            "event_id": "event:test:duplicate-application",
            "task_id": identity_task_id(agent_id),
            "trail_id": identity_trail_id(agent_id),
            "event_type": IdentityLifecycleEventType.APPLICATION_RECORDED.value,
            "actor": application["activated_by"],
            "created_at": "2026-06-24T02:21:00Z",
            "parent_cause": parent.event_id,
            "evidence_refs": [application["application_id"]],
            "payload": {
                "agent_id": agent_id,
                "record_type": IdentityLifecycleEventType.APPLICATION_RECORDED.value,
                "record_digest": digest_json(application),
                "record": application,
            },
        }
    )

    codes = {
        finding.code
        for finding in scan_identity_timeline(store, agent_id=agent_id).findings
    }
    assert "DUPLICATE_APPLICATION" in codes
    assert "PATCH_REAPPLIED" in codes


def test_proposal_digest_mismatch_is_detected() -> None:
    records = lifecycle_records()
    agent_id = _agent(records)
    records["approval"]["proposal_digest"] = "0" * 64
    store = InMemoryEventStoreAdapter()
    persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=records["profile_v1"],
        proposal=records["proposal"],
        approval=records["approval"],
    )

    codes = {
        finding.code
        for finding in scan_identity_timeline(store, agent_id=agent_id).findings
    }
    assert "PROPOSAL_DIGEST_MISMATCH" in codes


def test_jsonl_tampering_breaks_hash_chain(tmp_path) -> None:
    records = lifecycle_records()
    agent_id = _agent(records)
    path = tmp_path / "identity-events.jsonl"
    store = JsonlEventStoreAdapter(path)
    persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=records["profile_v1"],
        proposal=records["proposal"],
        approval=records["approval"],
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[1])
    tampered["actor"] = "attacker:tampered"
    lines[1] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    with pytest.raises(EventStoreCorruptionError):
        replay_identity_timeline(store, agent_id=agent_id)
