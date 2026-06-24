from __future__ import annotations

import json
from pathlib import Path

import pytest

from identity_catalog_publisher_fixtures import build_publisher_fixture
from trusted_runtime.identity_catalog_publisher import (
    CatalogGenerationRollbackError,
    CatalogPublisherBusyError,
    load_published_identity_catalog,
    publish_identity_catalog,
)


def _publish(fixture, *, published_at: str, **overrides):
    arguments = {
        "keyring": fixture["keyring"],
        "active_key_id": "key-old",
        "signing_key_ids": ("key-old",),
        "audience": "internal",
        "visibility_policy": fixture["visibility"],
        "published_at": published_at,
        "stale_after_seconds": 86400,
    }
    arguments.update(overrides)
    return publish_identity_catalog(
        fixture["data_root"],
        fixture["output_root"],
        **arguments,
    )


def test_catalog_rollback_to_older_generation_is_rejected(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:rollback",),
    )
    first = _publish(fixture, published_at="2026-06-24T05:00:00Z")
    second = _publish(
        fixture,
        published_at="2026-06-24T05:10:00Z",
        active_key_id="key-new",
        signing_key_ids=("key-new", "key-old"),
    )
    assert second.publication.generation == 2

    first_payload = json.loads(first.history_path.read_text(encoding="utf-8"))
    second.publication_path.write_text(
        json.dumps(first_payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CatalogGenerationRollbackError):
        _publish(
            fixture,
            published_at="2026-06-24T05:20:00Z",
            active_key_id="key-new",
            signing_key_ids=("key-new", "key-old"),
        )


def test_existing_lock_rejects_concurrent_publisher(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:concurrency",),
    )
    fixture["output_root"].mkdir(parents=True, exist_ok=True)
    lock = fixture["output_root"] / ".identity-catalog-publisher.lock"
    lock.write_text("other-process", encoding="utf-8")

    with pytest.raises(CatalogPublisherBusyError, match="already running"):
        _publish(fixture, published_at="2026-06-24T05:00:00Z")

    assert lock.read_text(encoding="utf-8") == "other-process"


def test_stale_entry_is_visible_but_not_in_authoritative_catalog(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:stale",),
    )
    result = _publish(
        fixture,
        published_at="2026-06-25T05:00:00Z",
        stale_after_seconds=60,
    )

    entry = result.publication.entries[0]
    assert entry.health == "STALE"
    assert entry.authoritative is False
    assert result.publication.legacy_catalog["entries"] == []


def test_invalid_event_store_is_visible_but_non_authoritative(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:invalid",),
    )
    events_path = fixture["bundles"][0]["events_path"]
    lines = events_path.read_text(encoding="utf-8").splitlines()
    changed = json.loads(lines[1])
    changed["actor"] = "tampered:actor"
    lines[1] = json.dumps(changed, sort_keys=True, separators=(",", ":"))
    events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _publish(fixture, published_at="2026-06-24T05:00:00Z")
    entry = result.publication.entries[0]
    codes = {finding["code"] for finding in entry.findings}

    assert entry.health == "INVALID"
    assert entry.authoritative is False
    assert "EVENT_HASH_MISMATCH" in codes
    assert result.publication.legacy_catalog["entries"] == []


def test_unauthorized_agent_is_absent_from_publication(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:visible", "agent:hidden"),
    )
    fixture["visibility"] = {
        "agent:visible": ("internal",),
        "agent:hidden": ("restricted",),
    }
    result = _publish(fixture, published_at="2026-06-24T05:00:00Z")

    assert [entry.agent_id for entry in result.publication.entries] == [
        "agent:visible"
    ]
    assert [
        entry["agent_id"] for entry in result.publication.legacy_catalog["entries"]
    ] == ["agent:visible"]


def test_minimum_generation_blocks_direct_history_rollback(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:min-generation",),
    )
    first = _publish(fixture, published_at="2026-06-24T05:00:00Z")

    with pytest.raises(CatalogGenerationRollbackError):
        load_published_identity_catalog(
            first.publication_path,
            keyring={"key-old": fixture["keyring"]["key-old"]},
            minimum_generation=2,
        )
