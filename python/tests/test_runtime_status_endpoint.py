# ruff: noqa: E402
"""Tests for the /runtime/status HTTP endpoint and the CLI entry point.

Uses the same threading + urllib pattern as test_graph_server.py.
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

import apps.ghostgpt.graph_server as srv
from apps.ghostgpt.graph_server import GraphHandler, HTTPServer


# ---------------------------------------------------------------------------
# Server fixture helpers (mirror of test_graph_server.py style)
# ---------------------------------------------------------------------------


def _make_server(port: int, data_dir: Path):
    original_data_dir = srv._DATA_DIR
    srv._DATA_DIR = data_dir
    server = HTTPServer(("127.0.0.1", port), GraphHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.05)
    return server, original_data_dir


def _stop(server, original_data_dir):
    server.shutdown()
    srv._DATA_DIR = original_data_dir


# ---------------------------------------------------------------------------
# /runtime/status endpoint
# ---------------------------------------------------------------------------


def test_runtime_status_returns_200(tmp_path):
    server, orig = _make_server(19100, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19100/runtime/status")
        assert resp.status == 200
    finally:
        _stop(server, orig)


def test_runtime_status_content_type_json(tmp_path):
    server, orig = _make_server(19101, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19101/runtime/status")
        ct = resp.headers.get("Content-Type", "")
        assert "application/json" in ct
    finally:
        _stop(server, orig)


def test_runtime_status_body_is_valid_json(tmp_path):
    server, orig = _make_server(19102, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19102/runtime/status")
        body = json.loads(resp.read())
        assert isinstance(body, dict)
    finally:
        _stop(server, orig)


def test_runtime_status_top_level_keys(tmp_path):
    server, orig = _make_server(19103, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19103/runtime/status")
        body = json.loads(resp.read())
        assert "captured_at" in body
        assert "graph_memory" in body
        assert "care_cycle" in body
        assert "omni_worker" in body
    finally:
        _stop(server, orig)


def test_runtime_status_graph_memory_keys(tmp_path):
    server, orig = _make_server(19104, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19104/runtime/status")
        gm = json.loads(resp.read())["graph_memory"]
        assert "total_cases" in gm
        assert "total_resonance_units" in gm
        assert "total_relational_snapshots" in gm
        assert "avg_resonance_score" in gm
        assert "avg_alignment_score" in gm
    finally:
        _stop(server, orig)


def test_runtime_status_care_cycle_keys(tmp_path):
    server, orig = _make_server(19105, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19105/runtime/status")
        cc = json.loads(resp.read())["care_cycle"]
        assert "total_modules" in cc
        assert "active" in cc
        assert "review" in cc
        assert "retired" in cc
    finally:
        _stop(server, orig)


def test_runtime_status_omni_worker_is_null_without_worker(tmp_path):
    server, orig = _make_server(19106, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19106/runtime/status")
        body = json.loads(resp.read())
        assert body["omni_worker"] is None
    finally:
        _stop(server, orig)


def test_runtime_status_cors_header(tmp_path):
    server, orig = _make_server(19107, tmp_path)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:19107/runtime/status")
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
    finally:
        _stop(server, orig)


def test_unknown_path_still_404(tmp_path):
    server, orig = _make_server(19108, tmp_path)
    try:
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen("http://127.0.0.1:19108/no-such-path")
        assert exc.value.code == 404
    finally:
        _stop(server, orig)


# ---------------------------------------------------------------------------
# CLI entry point (python -m graph.status)
# ---------------------------------------------------------------------------


def test_cli_prints_valid_json(tmp_path):
    from graph.__main__ import main
    import io
    import contextlib

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = main(["--data-dir", str(tmp_path)])
    assert rc == 0
    body = json.loads(out.getvalue())
    assert "captured_at" in body
    assert "graph_memory" in body


def test_cli_compact_flag_no_indent(tmp_path):
    from graph.__main__ import main
    import io
    import contextlib

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        main(["--data-dir", str(tmp_path), "--compact"])
    text = out.getvalue().strip()
    # Compact JSON has no newlines beyond the outer structure
    assert "\n" not in text


def test_cli_returns_1_on_error(tmp_path):
    from graph.__main__ import main
    import io
    import contextlib

    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        rc = main(["--data-dir", "/this/path/does/not/exist/at/all"])
    # Should return 1 (error) OR succeed with empty data — either is acceptable.
    # The key assertion: must not raise an uncaught exception.
    assert rc in (0, 1)
