from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

GRAPH_PATH = Path(__file__).parents[2] / "codex/temporal_graph/graph.json"
MEMORY_GRAPH_PATH = Path(__file__).parents[2] / "data/memory_graph.json"
UI_PATH = Path(__file__).parent / "graph_ui.html"
_DATA_DIR = Path(__file__).parents[2] / "data" / "graph_memory"
_MODULES_DIR = Path(__file__).parents[2] / "python" / "modules"


def _ensure_modules_on_path() -> None:
    if str(_MODULES_DIR) not in sys.path:
        sys.path.insert(0, str(_MODULES_DIR))


class GraphHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(UI_PATH, "text/html")
        elif self.path == "/graph.json":
            self._serve_file(GRAPH_PATH, "application/json")
        elif self.path == "/memory_graph.json":
            self._serve_file(MEMORY_GRAPH_PATH, "application/json")
        elif self.path == "/runtime/status":
            self._serve_runtime_status()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found")
            return

        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _serve_runtime_status(self) -> None:
        try:
            _ensure_modules_on_path()
            from graph.derived_module_registry import DerivedModuleRegistry
            from graph.memory_store import MemoryGraphStore
            from graph.runtime_snapshot import collect_runtime_status

            store = MemoryGraphStore(_DATA_DIR / "cases.jsonl")
            registry = DerivedModuleRegistry(_DATA_DIR / "derived_modules.json")
            snap = collect_runtime_status(graph_store=store, registry=registry)
            body = json.dumps(snap.to_dict(), ensure_ascii=False, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        except Exception as exc:
            body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = HTTPServer((host, port), GraphHandler)
    print(f"🚀 Temporal Graph UI → http://{host}:{port}")
    print(f"   Graph: {GRAPH_PATH.resolve()}")
    print(f"   Runtime status: http://{host}:{port}/runtime/status")
    server.serve_forever()


if __name__ == "__main__":
    run()
