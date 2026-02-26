import json
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import apps.ghostgpt.graph_server as srv
from apps.ghostgpt.graph_server import GraphHandler, HTTPServer


def _make_server(graph_data: dict, port: int):
    tmp = tempfile.mkdtemp()
    graph_path = Path(tmp) / "graph.json"
    graph_path.write_text(json.dumps(graph_data))
    original = srv.GRAPH_PATH
    srv.GRAPH_PATH = graph_path
    server = HTTPServer(("127.0.0.1", port), GraphHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.1)
    return server, original


def test_graph_json_endpoint():
    data = {"nodes": {"t1:1000": {"id": "t1:1000"}}, "edges": []}
    server, original = _make_server(data, 18765)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:18765/graph.json")
        assert resp.status == 200
        body = json.loads(resp.read())
        assert "nodes" in body
    finally:
        server.shutdown()
        srv.GRAPH_PATH = original


def test_404_on_unknown_path():
    data = {"nodes": {}, "edges": []}
    server, original = _make_server(data, 18766)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen("http://127.0.0.1:18766/unknown")
        assert exc.value.code == 404
    finally:
        server.shutdown()
        srv.GRAPH_PATH = original


def test_cors_header():
    data = {"nodes": {}, "edges": []}
    server, original = _make_server(data, 18767)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:18767/graph.json")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        server.shutdown()
        srv.GRAPH_PATH = original
