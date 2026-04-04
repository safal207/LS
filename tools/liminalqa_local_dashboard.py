from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "tools" / "liminalqa_local_dashboard.html"
ENV_PATH = ROOT / ".env.liminalqa.local"


def load_local_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if not ENV_PATH.exists():
        return values
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def resolve_settings() -> tuple[str, str]:
    env_map = load_local_env()
    base_url = os.environ.get("LIMINALQA_URL") or env_map.get("LIMINALQA_URL") or "http://127.0.0.1:8080"
    token = os.environ.get("LIMINALQA_TOKEN") or env_map.get("LIMINALQA_TOKEN") or "devtoken"
    return base_url.rstrip("/"), token


def api_request(method: str, path: str, payload: dict | None = None) -> tuple[int, object]:
    base_url, token = resolve_settings()
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = {"error": body or str(exc)}
        return exc.code, parsed
    except Exception as exc:  # noqa: BLE001
        return 500, {"error": str(exc)}


def ulid_like() -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")

    def encode(value: int, length: int) -> str:
        chars = []
        for _ in range(length):
            chars.append(alphabet[value & 0x1F])
            value >>= 5
        return "".join(reversed(chars))

    return encode(ms, 10) + encode(rand, 16)


def smoke_payload() -> dict:
    now = datetime.now(timezone.utc)
    started = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    completed = (now.replace(microsecond=min(now.microsecond + 120000, 999000))).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    return {
        "run": {
            "run_id": ulid_like(),
            "build_id": ulid_like(),
            "plan_name": "ls-dashboard-smoke",
            "env": {"CI": "false", "SOURCE": "ls-dashboard"},
            "started_at": started,
            "runner_version": "ls-dashboard-v1",
        },
        "tests": [
            {
                "name": "dashboard_smoke_publish",
                "suite": "ls.local.dashboard",
                "guidance": "Local dashboard smoke publish",
                "status": "pass",
                "duration_ms": 120,
                "started_at": started,
                "completed_at": completed,
            }
        ],
        "signals": [
            {
                "test_name": "dashboard_smoke_publish",
                "kind": "system",
                "value": 1.0,
                "meta": {"note": "dashboard smoke publish"},
                "at": started,
            }
        ],
        "artifacts": [],
    }


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._send_html(HTML_PATH.read_text(encoding="utf-8"))
            return
        if self.path == "/api/health":
            status, payload = api_request("GET", "/health")
            self._send_json(status, payload)
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/smoke":
            status, payload = api_request("POST", "/ingest/batch", smoke_payload())
            self._send_json(status, payload)
            return
        if self.path == "/api/query":
            status, payload = api_request("POST", "/query", {"limit": 10})
            self._send_json(status, payload)
            return
        self._send_json(404, {"error": "not found"})

    def log_message(self, fmt: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a small local dashboard for LiminalQA.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"LiminalQA local dashboard: http://{args.host}:{args.port}")
    print(f"Proxy target: {resolve_settings()[0]}")
    server.serve_forever()


if __name__ == "__main__":
    main()
