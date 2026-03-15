"""HTTP API helpers/server for Reflection Dashboard service contract."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict
from urllib.parse import parse_qs, urlparse

from .decision_pipeline import DecisionPipeline
from .reflection import ReflectionPipeline
from .reflection_dashboard_service import ReflectionDashboardService


def build_snapshot_response(service: ReflectionDashboardService, query: Dict[str, list[str]]) -> Dict[str, Any]:
    """Build snapshot payload from URL query parameters."""
    recent_limit = _parse_positive_int(query.get("recent_limit", ["20"])[0], default=20)
    timeline_limit = _parse_positive_int(query.get("timeline_limit", ["30"])[0], default=30)
    return service.get_dashboard_snapshot(recent_limit=recent_limit, timeline_limit=timeline_limit)


def execute_action(service: ReflectionDashboardService, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute approve/reject/edit action from API payload."""
    action = str(payload.get("action", "")).strip().lower()
    proposal = payload.get("proposal")
    if not isinstance(proposal, dict):
        raise ValueError("proposal must be an object")

    if action == "approve":
        messages = service.approve(proposal)
        return {"status": "ok", "action": action, "messages": messages}

    if action == "reject":
        reason = payload.get("reason")
        messages = service.reject(proposal, reason=str(reason) if reason is not None else None)
        return {"status": "ok", "action": action, "messages": messages}

    if action == "edit":
        if "proposed_value" not in payload:
            raise ValueError("proposed_value is required for edit")
        note = payload.get("note")
        messages = service.edit(proposal, payload.get("proposed_value"), note=str(note) if note is not None else None)
        return {"status": "ok", "action": action, "messages": messages}

    raise ValueError(f"unsupported action: {action}")


class ReflectionDashboardApiHandler(BaseHTTPRequestHandler):
    """Minimal JSON API handler for Reflection Dashboard workflows.

    Note:
        Instantiate this handler via ``create_handler(...)`` so ``service_factory`` is configured.
    """

    service_factory: Callable[[], ReflectionDashboardService] | None = None

    def __init__(self, *args: Any, **kwargs: Any):
        if self.service_factory is None:
            raise RuntimeError("service_factory is not configured; use create_handler(...) to bind a service")
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/reflection/snapshot":
            self._send_json(404, {"error": "not_found"})
            return

        service = self._require_service()
        snapshot = build_snapshot_response(service, parse_qs(parsed.query))
        self._send_json(200, snapshot)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/reflection/action":
            self._send_json(404, {"error": "not_found"})
            return

        service = self._require_service()
        try:
            payload = self._read_json_body()
            result = execute_action(service, payload)
        except ValueError as error:
            self._send_json(400, {"error": str(error)})
            return

        self._send_json(200, result)

    def _require_service(self) -> ReflectionDashboardService:
        if self.service_factory is None:
            raise RuntimeError("service_factory is not configured")
        return self.service_factory()

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(max(content_length, 0))
        if not raw:
            return {}
        decoded = json.loads(raw.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("payload must be a JSON object")
        return decoded

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # dev-only: restrict in production
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:
        pass


def create_handler(service_factory: Callable[[], ReflectionDashboardService]) -> type[ReflectionDashboardApiHandler]:
    """Create handler class bound to given service factory."""

    class BoundReflectionDashboardApiHandler(ReflectionDashboardApiHandler):
        pass

    BoundReflectionDashboardApiHandler.service_factory = service_factory
    return BoundReflectionDashboardApiHandler


def create_service(state_path: str = "reflection_state.json") -> ReflectionDashboardService:
    """Create dashboard service from persisted pipeline state file."""
    pipeline = ReflectionPipeline(DecisionPipeline.load_state(state_path), state_path=state_path)
    return ReflectionDashboardService(pipeline)


def run_reflection_dashboard_api(host: str = "127.0.0.1", port: int = 8780, state_path: str = "reflection_state.json") -> None:
    """Run Reflection Dashboard API server."""
    service = create_service(state_path=state_path)
    handler = create_handler(lambda: service)
    server = HTTPServer((host, port), handler)
    print(f"🚀 Reflection Dashboard API → http://{host}:{port}")
    server.serve_forever()


def _parse_positive_int(raw: str, default: int) -> int:
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default
