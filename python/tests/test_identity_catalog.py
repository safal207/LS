from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from identity_live_catalog_fixtures import build_live_catalog_fixture
from trusted_runtime.identity_catalog import (
    IdentityCatalogIntegrityError,
    load_signed_identity_catalog,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/identity_catalog.schema.json"


def test_signed_catalog_covers_two_verified_agent_bundles(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(tmp_path)
    catalog = load_signed_identity_catalog(
        fixture["catalog_path"],
        secret=fixture["verification_key"],
    )

    assert [entry.agent_id for entry in catalog.entries] == [
        "agent:live-alpha",
        "agent:live-beta",
    ]
    assert all(entry.event_count == 9 for entry in catalog.entries)
    assert all(entry.active_profile_version == 3 for entry in catalog.entries)
    assert all(entry.lifecycle_status == "ROLLED_BACK" for entry in catalog.entries)

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(catalog.to_dict()))


def test_catalog_signature_tampering_is_rejected(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(tmp_path)
    payload = json.loads(fixture["catalog_path"].read_text(encoding="utf-8"))
    payload["entries"][0]["active_profile_version"] = 99
    fixture["catalog_path"].write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(IdentityCatalogIntegrityError, match="signature is invalid"):
        load_signed_identity_catalog(
            fixture["catalog_path"],
            secret=fixture["verification_key"],
        )


def test_wrong_verification_key_is_rejected(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(tmp_path)

    with pytest.raises(IdentityCatalogIntegrityError, match="signature is invalid"):
        load_signed_identity_catalog(
            fixture["catalog_path"],
            secret=b"different-key-material",
        )
