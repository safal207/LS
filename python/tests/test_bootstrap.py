import sys
from pathlib import Path

from modules.shared.bootstrap import RuntimeContext, bootstrap_app, setup_runtime_paths
from modules.shared.event_bus import EventBus
from modules.shared.module_loader import DynamicModuleLoader
from modules.shared.service_registry import ServiceRegistry


class _Event:
    def __init__(self, event_type, payload=None):
        self.type = event_type
        self.payload = payload or {}


class _DummyModule:
    name = "dummy"

    def __init__(self):
        self.setup_calls = 0
        self.shutdown_calls = 0

    def setup(self, ctx):
        self.setup_calls += 1
        ctx.services.register("dummy_service", object(), capabilities={"read"})

    def shutdown(self, ctx):
        self.shutdown_calls += 1
        ctx.services.unregister("dummy_service")


def test_setup_runtime_paths_adds_expected_paths(monkeypatch):
    monkeypatch.setattr(sys, "path", [])

    root = setup_runtime_paths(str(Path("/workspace/LS/apps/console/main.py")))

    assert root == Path("/workspace/LS")
    assert str(root / "python") in sys.path
    assert str(root / "python" / "modules") in sys.path
    assert str(root) in sys.path


def test_bootstrap_app_returns_runtime_context():
    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")

    assert isinstance(ctx, RuntimeContext)
    assert ctx.app_name == "console"
    assert ctx.root == Path("/workspace/LS")
    assert isinstance(ctx.config, dict)
    assert "llm" in ctx.config
    assert isinstance(ctx.event_bus, EventBus)
    assert isinstance(ctx.services, ServiceRegistry)
    assert ctx.manifest is not None
    assert ctx.manifest.app_name == "console"


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


def test_service_registry_register_and_get():
    registry = ServiceRegistry()
    service = object()

    registry.register("memory", service, capabilities={"read", "write"})

    assert registry.has("memory")
    assert registry.get("memory") is service
    assert registry.get("memory", required_capability="read") is service


def test_service_registry_prevents_duplicate_registration():
    registry = ServiceRegistry()
    registry.register("memory", object())

    try:
        registry.register("memory", object())
        assert False, "Expected KeyError for duplicate service name"
    except KeyError as exc:
        assert "Service already registered" in str(exc)


def test_service_registry_enforces_capabilities():
    registry = ServiceRegistry()
    registry.register("memory", object(), capabilities={"read"})

    try:
        registry.get("memory", required_capability="write")
        assert False, "Expected PermissionError when capability is missing"
    except PermissionError as exc:
        assert "does not grant capability" in str(exc)


def test_dynamic_module_loader_load_unload_publishes_events():
    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")
    loader = DynamicModuleLoader(ctx)
    module = _DummyModule()

    events = []
    ctx.event_bus.subscribe("module_loaded", lambda e: events.append((e.type, e.payload["name"])))
    ctx.event_bus.subscribe("module_unloaded", lambda e: events.append((e.type, e.payload["name"])))

    loader.load(module)
    assert "dummy" in loader.list_loaded()
    assert module.setup_calls == 1
    assert ctx.services.has("dummy_service")

    loader.unload("dummy")
    assert module.shutdown_calls == 1
    assert not ctx.services.has("dummy_service")

    assert events == [("module_loaded", "dummy"), ("module_unloaded", "dummy")]
