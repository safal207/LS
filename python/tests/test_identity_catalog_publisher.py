from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from identity_catalog_publisher_fixtures import build_publisher_fixture
from trusted_runtime.identity_catalog_publisher import (
    load_published_identity_catalog,
    publish_identity_catalog,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/identity_catalog_publication.schema.json"


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


def test_first_publish_is_atomic_signed_and_schema_valid(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(tmp_path)
    result = _publish(fixture, published_at="2026-06-24T05:00:00Z")

    assert result.changed is True
    assert result.publication.generation == 1
    assert result.publication.previous_publication_digest is None
    assert [entry.agent_id for entry in result.publication.entries] == [
        "agent:publisher-alpha",
        "agent:publisher-beta",
    ]
    assert all(entry.authoritative for entry in result.publication.entries)
    assert result.publication_path.exists()
    assert result.legacy_catalog_path.exists()
    assert result.history_path.exists()
    assert result.state_path.exists()
    assert not list(fixture["output_root"].glob(".*.tmp"))

    loaded = load_published_identity_catalog(
        result.publication_path,
        keyring={"key-old": fixture["keyring"]["key-old"]},
        minimum_generation=1,
    )
    assert loaded == result.publication

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert not list(
        Draft202012Validator(schema).iter_errors(result.publication.to_dict())
    )


def test_restart_without_source_change_reuses_generation(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(tmp_path)
    first = _publish(fixture, published_at="2026-06-24T05:00:00Z")
    second = _publish(fixture, published_at="2026-06-24T05:05:00Z")

    assert first.changed is True
    assert second.changed is False
    assert second.publication.generation == 1
    assert second.publication.publication_digest == first.publication.publication_digest
    assert len(tuple((fixture["output_root"] / "history").glob("*.json"))) == 1


def test_new_visible_agent_creates_next_chained_generation(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:publisher-alpha",),
    )
    first = _publish(fixture, published_at="2026-06-24T05:00:00Z")

    from identity_timeline_api_fixtures import build_timeline_bundle

    build_timeline_bundle(fixture["data_root"], "agent:publisher-gamma")
    fixture["visibility"]["agent:publisher-gamma"] = ("internal",)
    second = _publish(fixture, published_at="2026-06-24T05:10:00Z")

    assert second.changed is True
    assert second.publication.generation == 2
    assert second.publication.previous_publication_digest == (
        first.publication.publication_digest
    )
    assert [entry.agent_id for entry in second.publication.entries] == [
        "agent:publisher-alpha",
        "agent:publisher-gamma",
    ]
    assert len(tuple((fixture["output_root"] / "history").glob("*.json"))) == 2


def test_rotation_publication_is_verifiable_by_old_and_new_keys(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:rotation",),
    )
    first = _publish(fixture, published_at="2026-06-24T05:00:00Z")
    second = _publish(
        fixture,
        published_at="2026-06-24T05:10:00Z",
        active_key_id="key-new",
        signing_key_ids=("key-new", "key-old"),
    )

    assert first.publication.generation == 1
    assert second.publication.generation == 2
    assert second.publication.active_key_id == "key-new"
    assert set(second.publication.signatures) == {"key-new", "key-old"}

    old_verified = load_published_identity_catalog(
        second.publication_path,
        keyring={"key-old": fixture["keyring"]["key-old"]},
        minimum_generation=2,
    )
    new_verified = load_published_identity_catalog(
        second.publication_path,
        keyring={"key-new": fixture["keyring"]["key-new"]},
        minimum_generation=2,
    )
    assert old_verified.publication_digest == new_verified.publication_digest
