from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from identity_timeline_fixtures import lifecycle_records
from trusted_runtime.identity_timeline import (
    IdentityTimelineStatus,
    persist_identity_lifecycle,
    replay_identity_timeline,
)
from trusted_runtime.persistence import InMemoryEventStoreAdapter


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/identity_timeline.schema.json"


def test_complete_lifecycle_rebuilds_profile_v3_deterministically() -> None:
    records = lifecycle_records()
    agent_id = records["agent_id"]["value"]
    store = InMemoryEventStoreAdapter()
    refs = persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=records["profile_v1"],
        proposal=records["proposal"],
        approval=records["approval"],
        patch=records["patch"],
        commit=records["commit"],
        application=records["application"],
        profile_v2=records["profile_v2"],
        rollback=records["rollback"],
        profile_v3=records["profile_v3"],
    )

    first = replay_identity_timeline(store, agent_id=agent_id)
    second = replay_identity_timeline(store, agent_id=agent_id)

    assert len(refs) == 9
    assert first.status is IdentityTimelineStatus.ROLLED_BACK
    assert first.active_profile["version"] == 3
    assert first.active_profile["traits"] == records["profile_v1"]["traits"]
    assert len(first.profile_versions) == 3
    assert len(first.application_refs) == 1
    assert len(first.rollback_refs) == 1
    assert first.side_effects_applied is False
    assert first.to_dict() == second.to_dict()
    assert first.to_dict()["integrity"]["event_count"] == 9

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(first.to_dict()))


def test_persist_is_idempotent_for_identical_records() -> None:
    records = lifecycle_records()
    agent_id = records["agent_id"]["value"]
    store = InMemoryEventStoreAdapter()
    kwargs = {
        "agent_id": agent_id,
        "profile_v1": records["profile_v1"],
        "proposal": records["proposal"],
        "approval": records["approval"],
        "patch": records["patch"],
        "commit": records["commit"],
        "application": records["application"],
        "profile_v2": records["profile_v2"],
        "rollback": records["rollback"],
        "profile_v3": records["profile_v3"],
    }
    first_refs = persist_identity_lifecycle(store, **kwargs)
    second_refs = persist_identity_lifecycle(store, **kwargs)

    assert first_refs == second_refs
    assert len(replay_identity_timeline(store, agent_id=agent_id).events) == 9
