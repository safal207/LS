from __future__ import annotations

from pathlib import Path
from typing import Any

from identity_catalog_publisher_fixtures import KEYRING
from identity_timeline_api_fixtures import build_timeline_bundle
from trusted_runtime.identity_catalog_trigger import finalize_identity_timeline_commit
from trusted_runtime.persistence import JsonlEventStoreAdapter


def build_committed_timeline(
    root: Path,
    agent_id: str,
    *,
    committed_at: str = "2026-06-24T04:05:00Z",
) -> dict[str, Any]:
    data_root = root / "data"
    outbox_path = root / "identity-catalog-publication-outbox.jsonl"
    fixture = build_timeline_bundle(data_root, agent_id)
    receipt, outbox_event_ref = finalize_identity_timeline_commit(
        JsonlEventStoreAdapter(fixture["events_path"]),
        agent_id=agent_id,
        bundle_root=fixture["bundle"],
        data_root=data_root,
        outbox_path=outbox_path,
        committed_at=committed_at,
    )
    return {
        **fixture,
        "data_root": data_root,
        "outbox_path": outbox_path,
        "receipt": receipt,
        "outbox_event_ref": outbox_event_ref,
        "publisher_output_root": root / "publisher",
        "trigger_output_root": root / "trigger",
        "keyring": dict(KEYRING),
    }


def visibility_for(*agent_ids: str) -> dict[str, tuple[str, ...]]:
    return {agent_id: ("internal",) for agent_id in agent_ids}
