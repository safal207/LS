#!/usr/bin/env python3
"""Dependency-free HTTP gateway for the LS ReviewDecision adapter v0.1."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import socket
import sys
import threading
from copy import deepcopy
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, BinaryIO

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "tools" / "review_decision_adapter_v0_1.py"
GATEWAY_VERSION = "ls-review-decision-gateway-v0.1"
PROJECT_PATH = "/v1/review-decision/project"
MAX_BODY_BYTES = 65536
READ_TIMEOUT_SECONDS = 5.0
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

_spec = importlib.util.spec_from_file_location("review_decision_adapter_v0_1", ADAPTER_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import adapter from {ADAPTER_PATH}")
adapter = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = adapter
_spec.loader.exec_module(adapter)


def read_exact(stream: BinaryIO, length: int) -> bytes | None:
    """Read exactly length bytes or return None on early EOF."""
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = stream.read(min(remaining, 8192))
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class GatewayMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values = {
            "review_decision_requests_total": 0,
            "blocked_ambiguous_signals_total": 0,
            "transport_rejections_total": 0,
            "invented_user_decisions_total": 0,
        }

    def record(self, *, blocked_ambiguous: bool = False, transport_rejection: bool = False) -> None:
        with self._lock:
            self._values["review_decision_requests_total"] += 1
            self._values["blocked_ambiguous_signals_total"] += int(blocked_ambiguous)
            self._values["transport_rejections_total"] += int(transport_rejection)
            if self._values["invented_user_decisions_total"] != 0:
                raise RuntimeError("invented_user_decisions_total invariant violated")

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._values)

    def prometheus(self) -> str:
        values = self.snapshot()
        lines: list[str] = []
        for name, value in values.items():
            lines.extend((f"# TYPE {name} counter", f"{name} {value}"))
        return "\n".join(lines) + "\n"


class ReviewDecisionGateway:
    def __init__(self, metrics: GatewayMetrics | None = None) -> None:
        self.metrics = metrics or GatewayMetrics()

    @staticmethod
    def request_id(body: bytes, supplied: str | None = None) -> str:
        candidate = supplied.strip() if isinstance(supplied, str) else ""
        if REQUEST_ID_PATTERN.fullmatch(candidate):
            return candidate
        return "req-" + hashlib.sha256(body).hexdigest()[:24]

    @staticmethod
    def envelope(request_id: str, result: dict[str, Any]) -> dict[str, Any]:
        return {
            "gateway_version": GATEWAY_VERSION,
            "request_id": request_id,
            "adapter": {
                "valid": result["valid"],
                "errors": list(result["errors"]),
            },
            "projection": deepcopy(result["projection"]),
            "side_effects_performed": False,
        }

    def project(self, payload: Any, request_id: str) -> tuple[int, dict[str, Any]]:
        result = adapter.project_signal(payload)
        projection = result["projection"]
        signal = payload.get("signal") if isinstance(payload, dict) else None
        invented = projection.get("durable_event_type") in {"UserApproved", "UserRejected"} and signal not in {
            "USER_APPROVED",
            "USER_REJECTED",
        }
        if invented:
            result = adapter.fail_closed(["gateway invariant violation: invented user decision"])
        self.metrics.record(blocked_ambiguous=not result["valid"])
        status = HTTPStatus.OK if result["valid"] else HTTPStatus.UNPROCESSABLE_ENTITY
        return int(status), self.envelope(request_id, result)

    def reject(self, status: HTTPStatus, error: str, request_id: str) -> tuple[int, dict[str, Any]]:
        result = adapter.fail_closed([error])
        self.metrics.record(transport_rejection=True)
        return int(status), self.envelope(request_id, result)


class GatewayServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], gateway: ReviewDecisionGateway):
        self.gateway = gateway
        super().__init__(address, GatewayHandler)


class GatewayHandler(BaseHTTPRequestHandler):
    server: GatewayServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return

    def send_json(self, status: int, value: dict[str, Any]) -> None:
        body = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, status: int, value: str) -> None:
        body = value.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def transport_error(self, status: HTTPStatus, error: str, body: bytes = b"") -> None:
        self.close_connection = True
        request_id = self.server.gateway.request_id(body, self.headers.get("X-Request-ID"))
        code, response = self.server.gateway.reject(status, error, request_id)
        self.send_json(code, response)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self.send_json(200, {"gateway_version": GATEWAY_VERSION, "status": "ok", "side_effects_performed": False})
        elif self.path == "/metrics":
            self.send_text(200, self.server.gateway.metrics.prometheus())
        else:
            self.send_json(404, {"gateway_version": GATEWAY_VERSION, "error": "not found", "side_effects_performed": False})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != PROJECT_PATH:
            self.close_connection = True
            self.send_json(404, {"gateway_version": GATEWAY_VERSION, "error": "not found", "side_effects_performed": False})
            return
        if self.headers.get("Transfer-Encoding") is not None:
            self.transport_error(HTTPStatus.BAD_REQUEST, "Transfer-Encoding is not supported")
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.transport_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Content-Type must be application/json")
            return
        length_headers = self.headers.get_all("Content-Length", [])
        if len(length_headers) != 1:
            self.transport_error(HTTPStatus.LENGTH_REQUIRED, "exactly one Content-Length is required")
            return
        try:
            length = int(length_headers[0])
        except ValueError:
            length = -1
        if length < 0:
            self.transport_error(HTTPStatus.LENGTH_REQUIRED, "valid Content-Length is required")
            return
        if length > MAX_BODY_BYTES:
            self.transport_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body exceeds 65536 bytes")
            return

        self.connection.settimeout(READ_TIMEOUT_SECONDS)
        try:
            body = read_exact(self.rfile, length)
        except (socket.timeout, TimeoutError):
            self.connection.settimeout(None)
            self.transport_error(HTTPStatus.REQUEST_TIMEOUT, "request body read timed out")
            return
        self.connection.settimeout(None)
        if body is None:
            self.transport_error(HTTPStatus.BAD_REQUEST, "request body was truncated")
            return

        request_id = self.server.gateway.request_id(body, self.headers.get("X-Request-ID"))
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            code, response = self.server.gateway.reject(HTTPStatus.BAD_REQUEST, "request body must be valid UTF-8 JSON", request_id)
            self.send_json(code, response)
            return
        code, response = self.server.gateway.project(payload, request_id)
        self.send_json(code, response)


def create_server(host: str = "127.0.0.1", port: int = 8080, gateway: ReviewDecisionGateway | None = None) -> GatewayServer:
    return GatewayServer((host, port), gateway or ReviewDecisionGateway())


def demo() -> str:
    gateway = ReviewDecisionGateway()
    payload = {
        "approval_id": "approval-gateway-demo-001",
        "signal": "REQUESTER_CANCELLED",
        "actor": {"type": "AGENT", "id": "agent-root"},
        "reason": "requesting future cancelled",
        "evidence_ref": None,
        "exact_bindings_match": True,
        "expiry_policy_configured": False,
    }
    status, response = gateway.project(payload, "demo-request-001")
    projection = response["projection"]
    return f"""LS ReviewDecision Gateway — 30-second demo

POST {PROJECT_PATH}
HTTP: {status}
Authority:    {projection['authority_state']}
Requester:    {projection['requester_state']}
Presentation: {projection['presentation_state']}
Execution:    {projection['execution_state']}
Status:       {projection['outward_status']}
Blocked:      {str(projection['execution_blocked']).lower()}
Side effects: {str(response['side_effects_performed']).lower()}

{projection['user_message']}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8080, type=int)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    if args.demo:
        print(demo())
        return 0
    server = create_server(args.host, args.port)
    print(f"{GATEWAY_VERSION} listening on http://{args.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
