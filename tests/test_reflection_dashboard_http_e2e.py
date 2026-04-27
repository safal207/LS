"""HTTP-level smoke: snapshot → approve → snapshot; OPTIONS CORS preflight."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from agent.decision_pipeline import DecisionPipeline
from agent.reflection import ReflectionPipeline
from agent.reflection_dashboard_api import create_handler
from agent.reflection_dashboard_service import ReflectionDashboardService


def _dummy_tool(payload: dict) -> dict:
    return {"status": "ok", "payload": payload}


def _build_service() -> ReflectionDashboardService:
    state = {
        "action_history": [{"success": True}],
        "strategy_stats": {
            "retrieve_context": {"successes": 1, "attempts": 1, "total_value": 1.0},
            "answer_with_tool": {"successes": 1, "attempts": 1, "total_value": 1.0},
        },
        "action_log": [{"fallback_reason": None}],
        "tool_error_counts": {"answer_with_tool": 7},
        "recent_reflections": [{"id": "r1", "timestamp": "2026-03-13T12:30:00+00:00"}],
        "pipeline_activity": [],
    }
    decision_pipeline = DecisionPipeline(state, tool_registry={"answer_with_tool": _dummy_tool})
    pipeline = ReflectionPipeline(decision_pipeline)
    return ReflectionDashboardService(pipeline)


def _http_json(method: str, url: str, body: dict | None = None, timeout: float = 10.0) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        raw = json.dumps(body).encode("utf-8")
        data = raw
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def test_reflection_http_snapshot_approve_roundtrip(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    service = _build_service()
    handler = create_handler(lambda: service)
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        base = f"http://127.0.0.1:{port}"

        status, snap1 = _http_json("GET", f"{base}/api/reflection/snapshot?recent_limit=3&timeline_limit=3")
        assert status == 200
        assert "memory_graph" in snap1
        assert "metrics" in snap1
        before = int(snap1["metrics"].get("canonical_count", 0))

        proposal = {
            "proposal_id": "e2e-p1",
            "change_type": "control_update",
            "target": "low_confidence_threshold",
            "proposed_value": 0.44,
        }
        status, action_res = _http_json(
            "POST",
            f"{base}/api/reflection/action",
            {"action": "approve", "proposal": proposal},
        )
        assert status == 200
        assert action_res.get("status") == "ok"

        status, snap2 = _http_json("GET", f"{base}/api/reflection/snapshot?recent_limit=3&timeline_limit=3")
        assert status == 200
        assert int(snap2["metrics"].get("canonical_count", 0)) >= before + 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)


def test_reflection_options_preflight_includes_cors_headers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REFLECTION_CORS_ORIGIN", "http://localhost:5173")
    service = _build_service()
    handler = create_handler(lambda: service)
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        url = f"http://127.0.0.1:{port}/api/reflection/action"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            assert resp.status == 204
            assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
            assert "POST" in (resp.headers.get("Access-Control-Allow-Methods") or "")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)
        monkeypatch.delenv("REFLECTION_CORS_ORIGIN", raising=False)


def test_reflection_http_edit_registers_timeline(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """POST action=edit with proposed_value should appear in snapshot action_timeline."""
    monkeypatch.chdir(tmp_path)
    service = _build_service()
    handler = create_handler(lambda: service)
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_port
        base = f"http://127.0.0.1:{port}"
        proposal = {
            "proposal_id": "e2e-edit-1",
            "change_type": "control_update",
            "target": "fallback_action",
            "proposed_value": "retrieve_context",
        }
        status, _ = _http_json(
            "POST",
            f"{base}/api/reflection/action",
            {
                "action": "edit",
                "proposal": proposal,
                "proposed_value": "structured_reasoning",
                "note": "e2e",
            },
        )
        assert status == 200

        _status, snap = _http_json("GET", f"{base}/api/reflection/snapshot?recent_limit=2&timeline_limit=10")
        assert _status == 200
        timeline = snap.get("action_timeline", [])
        types = {item.get("type") for item in timeline if isinstance(item, dict)}
        assert "edit" in types
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5.0)
