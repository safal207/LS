from __future__ import annotations

from pathlib import Path
from queue import Queue
import time

from modules.shared.bootstrap import bootstrap_app
from modules.shared.monitoring import MonitorService
from modules.shared.plugin_manager import PluginManager, PluginPermissions


class _Event:
    def __init__(self, event_type, payload=None):
        self.type = event_type
        self.payload = payload or {}


def test_plugin_manager_loads_and_unloads_example_plugin():
    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")
    manager = PluginManager(ctx)

    loaded = manager.load_from_path(Path("/workspace/LS/python/plugins/echo_plugin.py"))
    assert loaded == "echo_plugin"
    assert "echo_plugin" in manager.list_loaded()
    assert ctx.services.has("echo_plugin_status")

    responses = []
    ctx.event_bus.subscribe("echo_response", lambda e: responses.append(e.payload["text"]))
    ctx.event_bus.publish(_Event("echo_request", {"text": "hello"}))
    assert responses == ["hello"]

    manager.unload("echo_plugin")
    assert "echo_plugin" not in manager.list_loaded()
    assert not ctx.services.has("echo_plugin_status")


def test_plugin_manager_isolates_setup_failures(tmp_path):
    plugin_file = tmp_path / "broken_plugin.py"
    plugin_file.write_text(
        """
class BrokenPlugin:
    name = \"broken\"
    def setup(self, ctx):
        raise RuntimeError(\"boom\")
    def shutdown(self, ctx):
        pass
plugin = BrokenPlugin()
"""
    )

    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")
    manager = PluginManager(ctx, plugin_dir=tmp_path)

    failures = []
    ctx.event_bus.subscribe("plugin_failed", lambda e: failures.append(e.payload["name"]))

    loaded = manager.load_from_path(plugin_file)
    assert loaded is None
    assert manager.list_loaded() == []
    assert failures == ["broken"]


def test_plugin_manager_denies_permissions(tmp_path):
    plugin_file = tmp_path / "networked_plugin.py"
    plugin_file.write_text(
        """
from modules.shared.plugin_manager import PluginPermissions
class NetworkedPlugin:
    name = \"networked\"
    permissions = PluginPermissions(network_access=True)
    def setup(self, ctx):
        pass
    def shutdown(self, ctx):
        pass
plugin = NetworkedPlugin()
"""
    )

    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")
    manager = PluginManager(ctx, plugin_dir=tmp_path, allowed_permissions=PluginPermissions())

    denied = []
    ctx.event_bus.subscribe("plugin_permission_denied", lambda e: denied.append(e.payload["name"]))

    loaded = manager.load_from_path(plugin_file)
    assert loaded is None
    assert denied == ["networked"]


def test_monitor_service_queue_stats_and_alerts():
    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")
    queue = Queue(maxsize=10)
    for _ in range(9):
        queue.put(1)
    ctx.services.register("llm_queue", queue)

    monitor = MonitorService(ctx)
    monitor.register()

    alerts = []
    monitor.subscribe_alert("queue_high_utilization", lambda event: alerts.append(event.payload["queue"]))

    queue_stats = monitor.get_queue_stats()
    assert queue_stats["llm_queue"]["size"] == 9
    assert queue_stats["llm_queue"]["capacity"] == 10
    assert queue_stats["llm_queue"]["utilization"] == 0.9
    assert alerts == ["llm_queue"]

    bus_stats = monitor.get_event_bus_stats()
    assert "total_subscribers" in bus_stats


def test_monitor_service_latency_alert_for_llm():
    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")
    monitor = MonitorService(ctx)

    alerts = []
    monitor.subscribe_alert("llm_timeout", lambda event: alerts.append(event.payload["avg_ms"]))
    monitor.record_latency("llm", 6000)
    monitor.record_latency("llm", 7000)

    stats = monitor.get_latency_stats()
    assert stats["llm"]["avg_ms"] == 6500
    assert alerts and alerts[0] >= 6500


def test_monitor_service_resource_usage_cache():
    ctx = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")
    monitor = MonitorService(ctx, resource_cache_ttl_s=0.5)

    first = monitor.get_resource_usage()
    second = monitor.get_resource_usage()
    assert first == second

    time.sleep(0.6)
    third = monitor.get_resource_usage()
    assert set(third.keys()) == set(first.keys())
