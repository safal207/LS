from __future__ import annotations

from pathlib import Path

import pytest

from identity_catalog_publisher_fixtures import build_publisher_fixture
from trusted_runtime import identity_catalog_publisher as publisher


def _arguments(fixture):
    return {
        "keyring": fixture["keyring"],
        "active_key_id": "key-old",
        "signing_key_ids": ("key-old",),
        "audience": "internal",
        "visibility_policy": fixture["visibility"],
        "published_at": "2026-06-24T05:00:00Z",
        "stale_after_seconds": 86400,
    }


def test_failure_before_current_replace_never_publishes_partial_catalog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:atomic",),
    )
    original = publisher._atomic_write_json
    calls = []

    def fail_after_history(path, payload):
        calls.append(path.name)
        if len(calls) == 2:
            raise RuntimeError("simulated publication interruption")
        original(path, payload)

    monkeypatch.setattr(publisher, "_atomic_write_json", fail_after_history)
    with pytest.raises(RuntimeError, match="simulated publication interruption"):
        publisher.publish_identity_catalog(
            fixture["data_root"],
            fixture["output_root"],
            **_arguments(fixture),
        )

    assert not (
        fixture["output_root"] / "identity-catalog-publication.json"
    ).exists()
    assert not (fixture["output_root"] / "identity-catalog.json").exists()
    assert not (
        fixture["output_root"] / "identity-catalog-publisher-state.json"
    ).exists()
    assert not (
        fixture["output_root"] / ".identity-catalog-publisher.lock"
    ).exists()

    monkeypatch.setattr(publisher, "_atomic_write_json", original)
    recovered = publisher.publish_identity_catalog(
        fixture["data_root"],
        fixture["output_root"],
        **_arguments(fixture),
    )
    assert recovered.changed is True
    assert recovered.publication.generation == 1
    assert recovered.publication_path.exists()


def test_atomic_writer_leaves_no_temporary_files(tmp_path: Path) -> None:
    fixture = build_publisher_fixture(
        tmp_path,
        agent_ids=("agent:no-temp",),
    )
    result = publisher.publish_identity_catalog(
        fixture["data_root"],
        fixture["output_root"],
        **_arguments(fixture),
    )

    assert result.publication_path.exists()
    assert not list(fixture["output_root"].rglob("*.tmp"))
