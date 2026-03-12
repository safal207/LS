import os
import sys
from pathlib import Path

from modules.shared.bootstrap import RuntimeContext, bootstrap_app, setup_runtime_paths
from modules.shared.event_bus import EventBus


class _Event:
    def __init__(self, event_type, payload=None):
        self.type = event_type
        self.payload = payload or {}


def test_setup_runtime_paths_adds_expected_paths(monkeypatch):
    monkeypatch.setattr(sys, "path", [])

    root = setup_runtime_paths(str(Path("/workspace/LS/apps/console/main.py")))

    assert root == Path("/workspace/LS")
    assert str(root / "python") in sys.path
    assert str(root / "python" / "modules") in sys.path
    assert str(root) in sys.path


def test_bootstrap_app_returns_runtime_context(monkeypatch):
    monkeypatch.delenv("LS_APP", raising=False)

    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")

    assert isinstance(ctx, RuntimeContext)
    assert os.environ["LS_APP"] == "console"
    assert ctx.app_name == "console"
    assert ctx.root == Path("/workspace/LS")
    assert isinstance(ctx.config, dict)
    assert "llm" in ctx.config
    assert isinstance(ctx.event_bus, EventBus)


def test_event_bus_publish_subscribe():
    bus = EventBus()
    events = []

    bus.subscribe("output_ready", lambda e: events.append(e.payload["text"]))
    bus.publish(_Event("output_ready", payload={"text": "ok"}))

    assert events == ["ok"]


def test_event_bus_continues_when_handler_fails(caplog):
    bus = EventBus()
    events = []

    def broken_handler(_event):
        raise RuntimeError("boom")

    bus.subscribe("output_ready", broken_handler)
    bus.subscribe("output_ready", lambda e: events.append(e.payload["text"]))

    bus.publish(_Event("output_ready", payload={"text": "still delivered"}))

    assert events == ["still delivered"]
    assert "Event handler failed for event_type=output_ready" in caplog.text
