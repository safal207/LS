from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

GRAPH_PATH = Path(__file__).parents[2] / "codex/temporal_graph/graph.json"
UI_PATH = Path(__file__).parent / "graph_ui.html"


class GraphHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._serve_file(UI_PATH, "text/html")
        elif self.path == "/graph.json":
            self._serve_file(GRAPH_PATH, "application/json")
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_response(404)
            self.end_headers()
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = HTTPServer((host, port), GraphHandler)
    print(f"Temporal Graph UI → http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
