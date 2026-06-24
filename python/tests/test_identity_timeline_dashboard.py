from __future__ import annotations

from pathlib import Path

from identity_timeline_api_fixtures import build_timeline_bundle
from trusted_runtime.identity_timeline_api import build_identity_timeline_wsgi_app


def _request(app, method: str, path: str):
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "SERVER_NAME": "test",
                "SERVER_PORT": "80",
                "wsgi.url_scheme": "http",
                "wsgi.input": None,
            },
            start_response,
        )
    )
    return captured["status"], captured["headers"], body


def test_dashboard_is_accessible_responsive_and_read_only(tmp_path: Path) -> None:
    build_timeline_bundle(tmp_path, "agent:dashboard")
    app = build_identity_timeline_wsgi_app(tmp_path)

    status, headers, body = _request(app, "GET", "/")
    html = body.decode("utf-8")
    assert status.startswith("200")
    assert headers["Content-Security-Policy"]
    assert '<html lang="en">' in html
    assert 'class="skip-link"' in html
    assert '<main id="main-content"' in html
    assert 'role="status"' in html
    assert 'aria-live="assertive"' in html
    assert "Read only" in html
    assert "cannot approve, apply, or roll back" in html
    assert "<form" not in html.lower()

    css_status, _, css_body = _request(app, "GET", "/styles.css")
    css = css_body.decode("utf-8")
    assert css_status.startswith("200")
    assert "@media (max-width:" in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css

    js_status, _, js_body = _request(app, "GET", "/app.js")
    javascript = js_body.decode("utf-8")
    assert js_status.startswith("200")
    assert 'method: "GET"' in javascript
    assert 'method: "POST"' not in javascript
    assert 'method: "PUT"' not in javascript
    assert 'method: "DELETE"' not in javascript


def test_dashboard_and_api_reject_mutation_methods(tmp_path: Path) -> None:
    fixture = build_timeline_bundle(tmp_path, "agent:no-mutations")
    app = build_identity_timeline_wsgi_app(tmp_path)
    before = fixture["events_path"].read_bytes()

    for path in ("/", "/api/v1/agents"):
        status, headers, body = _request(app, "POST", path)
        assert status.startswith("405")
        assert headers["Allow"] == "GET, HEAD"
        assert b"read-only" in body.lower()

    assert fixture["events_path"].read_bytes() == before


def test_head_requests_return_headers_without_bodies(tmp_path: Path) -> None:
    build_timeline_bundle(tmp_path, "agent:head")
    app = build_identity_timeline_wsgi_app(tmp_path)

    static_status, static_headers, static_body = _request(app, "HEAD", "/")
    api_status, api_headers, api_body = _request(app, "HEAD", "/api/v1/agents")

    assert static_status.startswith("200")
    assert api_status.startswith("200")
    assert static_body == b""
    assert api_body == b""
    assert static_headers["Content-Length"] == "0"
    assert api_headers["Content-Length"] == "0"
