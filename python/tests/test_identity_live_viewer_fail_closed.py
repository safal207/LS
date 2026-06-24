from __future__ import annotations

import json
from pathlib import Path

from identity_live_catalog_fixtures import build_live_catalog_fixture
from trusted_runtime.identity_live_viewer import (
    CatalogIdentityTimelineRepository,
    SignedCatalogIdentityTimelineAPI,
)
from trusted_runtime.persistence import digest_json


def _payload(response):
    return json.loads(response[2].decode("utf-8"))


def test_bundle_changed_after_signing_is_visible_but_non_authoritative(
    tmp_path: Path,
) -> None:
    fixture = build_live_catalog_fixture(
        tmp_path,
        agent_ids=("agent:changed-after-signing",),
    )
    timeline_path = fixture["bundles"][0]["timeline_path"]
    timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
    timeline["active_profile"]["traits"]["review_style"] = "changed"
    unsigned = dict(timeline)
    unsigned.pop("integrity")
    timeline["integrity"]["timeline_digest"] = digest_json(unsigned)
    timeline_path.write_text(
        json.dumps(timeline, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    api = SignedCatalogIdentityTimelineAPI(
        CatalogIdentityTimelineRepository(
            fixture["data_root"],
            fixture["catalog_path"],
            secret=fixture["verification_key"],
        )
    )
    response = api.handle_live(
        "GET",
        "/api/v1/agents/agent%3Achanged-after-signing/timeline",
    )
    payload = _payload(response)
    codes = {item["code"] for item in payload["findings"]}

    assert response[0] == 200
    assert payload["authoritative"] is False
    assert payload["active_profile"] is None
    assert "CATALOG_TIMELINE_DIGEST_MISMATCH" in codes


def test_invalid_catalog_key_fails_closed(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(tmp_path)
    api = SignedCatalogIdentityTimelineAPI(
        CatalogIdentityTimelineRepository(
            fixture["data_root"],
            fixture["catalog_path"],
            secret=b"wrong-key-material",
        )
    )

    response = api.handle_live("GET", "/api/v1/catalog")
    payload = _payload(response)

    assert response[0] == 409
    assert payload["error"] == "catalog_integrity_failure"
    assert payload["authoritative"] is False


def test_unknown_agent_and_invalid_pagination_do_not_leak_data(
    tmp_path: Path,
) -> None:
    fixture = build_live_catalog_fixture(
        tmp_path,
        agent_ids=("agent:known",),
    )
    api = SignedCatalogIdentityTimelineAPI(
        CatalogIdentityTimelineRepository(
            fixture["data_root"],
            fixture["catalog_path"],
            secret=fixture["verification_key"],
        )
    )

    invalid_page = api.handle_live(
        "GET",
        "/api/v1/agents/agent%3Aknown/events",
        query_string="cursor=-1&limit=1000",
    )
    assert invalid_page[0] == 400
    assert _payload(invalid_page)["error"] == "invalid_pagination"
