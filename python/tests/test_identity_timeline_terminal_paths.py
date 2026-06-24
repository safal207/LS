from __future__ import annotations

import pytest

from identity_timeline_fixtures import lifecycle_records
from trusted_runtime.identity_timeline import (
    IdentityTimelineStatus,
    persist_identity_lifecycle,
    replay_identity_timeline,
)
from trusted_runtime.persistence import InMemoryEventStoreAdapter


@pytest.mark.parametrize(
    ("decision", "expected_status"),
    (
        ("REJECT", IdentityTimelineStatus.REJECTED),
        ("EXPIRE", IdentityTimelineStatus.EXPIRED),
        ("INVALIDATE", IdentityTimelineStatus.INVALIDATED),
    ),
)
def test_terminal_approval_paths_remain_inspectable_without_effects(
    decision,
    expected_status,
) -> None:
    records = lifecycle_records()
    agent_id = records["agent_id"]["value"]
    approval = records["approval"]
    approval["decision"] = decision
    approval["expires_at"] = None
    approval["contradiction_refs"] = (
        ["episode:contradiction:1"] if decision == "INVALIDATE" else []
    )
    store = InMemoryEventStoreAdapter()
    persist_identity_lifecycle(
        store,
        agent_id=agent_id,
        profile_v1=records["profile_v1"],
        proposal=records["proposal"],
        approval=approval,
    )

    timeline = replay_identity_timeline(store, agent_id=agent_id)
    assert timeline.status is expected_status
    assert timeline.active_profile["version"] == 1
    assert timeline.patch_refs == ()
    assert timeline.commit_refs == ()
    assert timeline.application_refs == ()
    assert timeline.rollback_refs == ()
    assert timeline.side_effects_applied is False
