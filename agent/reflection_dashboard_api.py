"""HTTP API helpers/server for Reflection Dashboard service contract."""

from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict
from urllib.parse import parse_qs, urlparse

from .decision_pipeline import DecisionPipeline
from .reflection import ReflectionPipeline
from .reflection_dashboard_service import ReflectionDashboardService

logger = logging.getLogger(__name__)


def _cors_allow_origin() -> str:
    """Use ``REFLECTION_CORS_ORIGIN`` in production; default ``*`` for local dev."""
    return os.getenv("REFLECTION_CORS_ORIGIN", "*").strip() or "*"


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


class ContentTooLargeError(ValueError):
    """Raised when the request body exceeds the maximum allowed size."""


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

    def do_OPTIONS(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path not in ("/api/reflection/snapshot", "/api/reflection/action"):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", _cors_allow_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/reflection/snapshot":
            logger.warning("reflection_api 404 GET %s", parsed.path)
            self._send_json(404, {"error": "not_found"})
            return

        service = self._require_service()
        snapshot = build_snapshot_response(service, parse_qs(parsed.query))
        self._send_json(200, snapshot)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/reflection/action":
            logger.warning("reflection_api 404 POST %s", parsed.path)
            self._send_json(404, {"error": "not_found"})
            return

        service = self._require_service()
        try:
            payload = self._read_json_body()
            result = execute_action(service, payload)
        except ContentTooLargeError as error:
            logger.warning("reflection_api 413 POST %s: %s", parsed.path, error)
            self._send_json(413, {"error": str(error)})
            return
        except ValueError as error:
            logger.warning("reflection_api 400 POST %s: %s", parsed.path, error)
            self._send_json(400, {"error": str(error)})
            return

        self._send_json(200, result)

    def _require_service(self) -> ReflectionDashboardService:
        if self.service_factory is None:
            raise RuntimeError("service_factory is not configured")
        return self.service_factory()

    # BUG-API-01: Limit request body to 1 MB to prevent DoS via unbounded reads
    _MAX_BODY = 1_048_576

    def _read_json_body(self) -> Dict[str, Any]:
        raw_cl = self.headers.get("Content-Length", "0")
        try:
            content_length = max(int(raw_cl), 0)
        except (TypeError, ValueError):
            content_length = 0
        # BUG-API-01: Reject oversized bodies before reading
        if content_length > self._MAX_BODY:
            logger.warning("reflection_api request body too large: %d > %d", content_length, self._MAX_BODY)
            raise ContentTooLargeError(f"request body too large ({content_length} > {self._MAX_BODY})")
        raw = self.rfile.read(min(content_length, self._MAX_BODY))
        if not raw:
            return {}
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as error:
            logger.warning("reflection_api invalid JSON: %s", error)
            raise ValueError(f"invalid JSON: {error}") from error
        if not isinstance(decoded, dict):
            logger.warning("reflection_api payload not an object")
            raise ValueError("payload must be a JSON object")
        return decoded

    def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", _cors_allow_origin())
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        # BUG-API-02: Restore minimal server-side logging so errors are visible
        logger.info("reflection_api %s", format % args)


def create_handler(service_factory: Callable[[], ReflectionDashboardService]) -> type[ReflectionDashboardApiHandler]:
    """Create handler class bound to given service factory."""

    class BoundReflectionDashboardApiHandler(ReflectionDashboardApiHandler):
        pass

    BoundReflectionDashboardApiHandler.service_factory = staticmethod(service_factory)
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
