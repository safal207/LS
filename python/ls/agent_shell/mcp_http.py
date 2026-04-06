from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .mcp_server import LSMCPServer


class MCPHTTPHandler(BaseHTTPRequestHandler):
    server_version = "ls-mcp-http/0.1"

    def _json_response(self, status_code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @property
    def mcp(self) -> LSMCPServer:
        return self.server.mcp  # type: ignore[attr-defined]

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json_response(200, {"ok": True})
            return
        if parsed.path == "/resources/read":
            query = parse_qs(parsed.query)
            uri = query.get("uri", [None])[0]
            if not uri:
                self._json_response(400, {"ok": False, "error": "Missing uri"})
                return
            try:
                payload = self.mcp.handle({"action": "resources/read", "uri": uri})
                self._json_response(200, {"ok": True, **payload})
            except Exception as exc:  # protocol boundary
                self._json_response(400, {"ok": False, "error": str(exc)})
            return
        self._json_response(404, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json_response(400, {"ok": False, "error": "Invalid JSON"})
            return

        if self.path == "/tools/call":
            request = {
                "action": "tools/call",
                "name": payload.get("name"),
                "arguments": payload.get("arguments", {}),
            }
        elif self.path == "/tools/list":
            request = {"action": "tools/list"}
        elif self.path == "/resources/list":
            request = {"action": "resources/list"}
        else:
            self._json_response(404, {"ok": False, "error": "Not found"})
            return

        try:
            result = self.mcp.handle(request)
            self._json_response(200, {"ok": True, **result})
        except Exception as exc:
            self._json_response(400, {"ok": False, "error": str(exc)})


def run_http_server(host: str = "127.0.0.1", port: int = 8042) -> None:
    server = ThreadingHTTPServer((host, port), MCPHTTPHandler)
    server.mcp = LSMCPServer()  # type: ignore[attr-defined]
    server.serve_forever()
