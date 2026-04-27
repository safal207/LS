from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from .service import HcpMarketplaceService
from .store import load_store_with_seed

logger = logging.getLogger(__name__)


def _cors() -> str:
    return os.getenv("HCP_CORS_ORIGIN", "*").strip() or "*"


def _read_json_body(handler: BaseHTTPRequestHandler, max_body: int = 1_048_576) -> dict[str, Any]:
    raw_cl = handler.headers.get("Content-Length", "0")
    try:
        n = max(int(raw_cl), 0)
    except (TypeError, ValueError):
        n = 0
    if n > max_body:
        raise ValueError("request body too large")
    raw = handler.rfile.read(min(n, max_body))
    if not raw:
        return {}
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def create_handler(service_factory: Callable[[], HcpMarketplaceService]) -> type[BaseHTTPRequestHandler]:
    class HcpHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.info("hcp_api %s", format % args)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", _cors())
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            svc = service_factory()
            if parsed.path == "/api/hcp/health":
                self._json(200, {"status": "ok", "service": "hcp_marketplace"})
            elif parsed.path == "/api/hcp/items":
                self._json(200, {"items": svc.list_items()})
            elif parsed.path.startswith("/api/hcp/items/"):
                item_id = parsed.path.rstrip("/").split("/")[-1]
                it = svc.get_item(item_id)
                if it is None:
                    self._json(404, {"error": "not_found"})
                else:
                    self._json(200, it)
            elif parsed.path == "/api/hcp/credits":
                inst = (qs.get("instance") or [""])[0] or (qs.get("instance_id") or [""])[0] or "default"
                self._json(200, svc.get_credits(inst))
            else:
                self._json(404, {"error": "not_found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            svc = service_factory()
            try:
                body = _read_json_body(self)
            except (ValueError, json.JSONDecodeError) as e:
                self._json(400, {"error": str(e)})
                return
            if parsed.path == "/api/hcp/purchase":
                item_id = str(body.get("item_id", ""))
                inst = str(body.get("instance_id", "default"))
                if not item_id:
                    self._json(400, {"error": "item_id required"})
                    return
                self._json(200, svc.purchase(item_id, inst))
            elif parsed.path == "/api/hcp/install":
                item_id = str(body.get("item_id", ""))
                inst = str(body.get("instance_id", "default"))
                if not item_id:
                    self._json(400, {"error": "item_id required"})
                    return
                self._json(200, svc.install(item_id, inst))
            else:
                self._json(404, {"error": "not_found"})

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            b = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.send_header("Access-Control-Allow-Origin", _cors())
            self.end_headers()
            self.wfile.write(b)

    return HcpHandler


def run_hcp_marketplace_api(
    host: str = "127.0.0.1",
    port: int = 8781,
    state_path: str = "hcp_marketplace.json",
) -> None:
    store = load_store_with_seed(Path(state_path))
    service = HcpMarketplaceService(store)
    handler = create_handler(lambda: service)
    server = HTTPServer((host, port), handler)
    print(f"HCP Marketplace API http://{host}:{port} (state: {state_path})")
    server.serve_forever()
