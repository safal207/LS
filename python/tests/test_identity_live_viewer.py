from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from identity_live_catalog_fixtures import build_live_catalog_fixture
from trusted_runtime.identity_live_viewer import (
    CatalogIdentityTimelineRepository,
    SignedCatalogIdentityTimelineAPI,
)


def _payload(response):
    return json.loads(response[2].decode("utf-8"))


def test_catalog_endpoint_and_agents_are_verified(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(tmp_path)
    repository = CatalogIdentityTimelineRepository(
        fixture["data_root"],
        fixture["catalog_path"],
        secret=fixture["verification_key"],
    )
    api = SignedCatalogIdentityTimelineAPI(repository)

    catalog_response = api.handle_live("GET", "/api/v1/catalog")
    catalog = _payload(catalog_response)
    agents = _payload(api.handle_live("GET", "/api/v1/agents"))["agents"]

    assert catalog_response[0] == 200
    assert catalog["signature_verified"] is True
    assert catalog["catalog"]["entry_count"] == 2
    assert all(item["health"] == "VALID" for item in catalog["entries"])
    assert [item["agent_id"] for item in agents] == [
        "agent:live-alpha",
        "agent:live-beta",
    ]
    assert all(item["integrity_status"] == "VALID" for item in agents)


def test_event_pages_are_deterministic_and_preserve_causal_order(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(
        tmp_path,
        agent_ids=("agent:paginated",),
    )
    api = SignedCatalogIdentityTimelineAPI(
        CatalogIdentityTimelineRepository(
            fixture["data_root"],
            fixture["catalog_path"],
            secret=fixture["verification_key"],
        )
    )
    encoded = quote("agent:paginated", safe="")
    path = f"/api/v1/agents/{encoded}/events"

    first = _payload(api.handle_live("GET", path, query_string="limit=4"))
    second = _payload(
        api.handle_live(
            "GET",
            path,
            query_string=f"limit=4&cursor={first['next_cursor']}",
        )
    )
    third = _payload(
        api.handle_live(
            "GET",
            path,
            query_string=f"limit=4&cursor={second['next_cursor']}",
        )
    )
    events = [*first["items"], *second["items"], *third["items"]]

    assert first["total"] == 9
    assert first["causal_order"] == "durable_sequence_ascending"
    assert [event["sequence"] for event in events] == list(range(9))
    assert len({event["event_ref"] for event in events}) == 9
    assert third["next_cursor"] is None
    assert third["tail_event_ref"] == events[-1]["event_ref"]


def test_conditional_get_returns_304_with_stable_etag(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(
        tmp_path,
        agent_ids=("agent:etag",),
    )
    api = SignedCatalogIdentityTimelineAPI(
        CatalogIdentityTimelineRepository(
            fixture["data_root"],
            fixture["catalog_path"],
            secret=fixture["verification_key"],
        )
    )
    path = "/api/v1/agents/agent%3Aetag/events"
    first = api.handle_live("GET", path, query_string="limit=3")
    headers = dict(first[3])
    second = api.handle_live(
        "GET",
        path,
        query_string="limit=3",
        if_none_match=headers["ETag"],
    )

    assert first[0] == 200
    assert headers["ETag"].startswith('"sha256:')
    assert second[0] == 304
    assert second[2] == b""
    assert dict(second[3])["ETag"] == headers["ETag"]


def test_read_requests_and_rejected_writes_do_not_change_events(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(
        tmp_path,
        agent_ids=("agent:immutable",),
    )
    bundle = fixture["bundles"][0]
    before = bundle["events_path"].read_bytes()
    api = SignedCatalogIdentityTimelineAPI(
        CatalogIdentityTimelineRepository(
            fixture["data_root"],
            fixture["catalog_path"],
            secret=fixture["verification_key"],
        )
    )
    path = "/api/v1/agents/agent%3Aimmutable/events"

    for cursor in (0, 3, 6):
        assert api.handle_live(
            "GET",
            path,
            query_string=f"cursor={cursor}&limit=3",
        )[0] == 200
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert api.handle_live(method, path)[0] == 405

    assert bundle["events_path"].read_bytes() == before
