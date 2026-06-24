from __future__ import annotations

from pathlib import Path
from typing import Any

from identity_timeline_api_fixtures import build_timeline_bundle
from trusted_runtime.identity_catalog import build_signed_identity_catalog, write_signed_identity_catalog


VERIFICATION_KEY = b"catalog-fixture-key-material"
KEY_ID = "fixture-key-v1"
GENERATED_AT = "2026-06-24T05:00:00Z"


def build_live_catalog_fixture(
    root: Path,
    *,
    agent_ids: tuple[str, ...] = ("agent:live-alpha", "agent:live-beta"),
) -> dict[str, Any]:
    data_root = root / "data"
    bundles = [build_timeline_bundle(data_root, agent_id) for agent_id in agent_ids]
    catalog = build_signed_identity_catalog(
        data_root,
        secret=VERIFICATION_KEY,
        key_id=KEY_ID,
        generated_at=GENERATED_AT,
    )
    catalog_path = root / "identity-catalog.json"
    write_signed_identity_catalog(catalog_path, catalog)
    return {
        "data_root": data_root,
        "catalog": catalog,
        "catalog_path": catalog_path,
        "bundles": bundles,
        "verification_key": VERIFICATION_KEY,
    }
