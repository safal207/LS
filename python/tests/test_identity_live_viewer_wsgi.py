from __future__ import annotations

import json
from pathlib import Path

from identity_live_catalog_fixtures import build_live_catalog_fixture
from trusted_runtime.identity_live_viewer import build_signed_catalog_identity_viewer


def _request(
    app,
    method: str,
    path: str,
    *,
    query_string: str = "",
    etag: str | None = None,
):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": query_string,
        "SERVER_NAME": "test",
        "SERVER_PORT": "80",
        "wsgi.url_scheme": "http",
        "wsgi.input": None,
    }
    if etag:
        environ["HTTP_IF_NONE_MATCH"] = etag
    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], body


def test_signed_catalog_wsgi_serves_dashboard_and_paginated_events(
    tmp_path: Path,
) -> None:
    fixture = build_live_catalog_fixture(
        tmp_path,
        agent_ids=("agent:wsgi",),
    )
    bundle = fixture["bundles"][0]
    before = bundle["events_path"].read_bytes()
    app = build_signed_catalog_identity_viewer(
        fixture["data_root"],
        fixture["catalog_path"],
        secret=fixture["verification_key"],
    )

    static_status, static_headers, static_body = _request(app, "GET", "/")
    catalog_status, _, catalog_body = _request(app, "GET", "/api/v1/catalog")
    page_status, page_headers, page_body = _request(
        app,
        "GET",
        "/api/v1/agents/agent%3Awsgi/events",
        query_string="limit=3",
    )
    page = json.loads(page_body.decode("utf-8"))

    assert static_status.startswith("200")
    assert b"Identity Timeline" in static_body
    assert static_headers["ETag"].startswith('"sha256:')
    assert catalog_status.startswith("200")
    assert json.loads(catalog_body)["signature_verified"] is True
    assert page_status.startswith("200")
    assert page["total"] == 9
    assert len(page["items"]) == 3

    not_modified = _request(
        app,
        "GET",
        "/api/v1/agents/agent%3Awsgi/events",
        query_string="limit=3",
        etag=page_headers["ETag"],
    )
    assert not_modified[0].startswith("304")
    assert not_modified[2] == b""
    assert bundle["events_path"].read_bytes() == before


def test_wsgi_rejects_mutations(tmp_path: Path) -> None:
    fixture = build_live_catalog_fixture(
        tmp_path,
        agent_ids=("agent:wsgi-readonly",),
    )
    app = build_signed_catalog_identity_viewer(
        fixture["data_root"],
        fixture["catalog_path"],
        secret=fixture["verification_key"],
    )

    status, headers, body = _request(app, "POST", "/api/v1/catalog")
    assert status.startswith("405")
    assert headers["Allow"] == "GET, HEAD"
    assert b"read-only" in body.lower()
