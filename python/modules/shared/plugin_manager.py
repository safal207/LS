from __future__ import annotations

import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, Protocol

from modules.shared.bootstrap import RuntimeContext


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PluginLifecycleEvent:
    type: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class PluginPermissions:
    filesystem_read: bool = False
    filesystem_write: bool = False
    network_access: bool = False
    spawn_process: bool = False

    def allows(self, requested: "PluginPermissions") -> bool:
        return (
            (not requested.filesystem_read or self.filesystem_read)
            and (not requested.filesystem_write or self.filesystem_write)
            and (not requested.network_access or self.network_access)
            and (not requested.spawn_process or self.spawn_process)
        )


class Plugin(Protocol):
    name: str
    permissions: PluginPermissions

    def setup(self, ctx: RuntimeContext) -> None:
        ...

    def shutdown(self, ctx: RuntimeContext) -> None:
        ...


class PluginRuntimeContext:
    """Context proxy that tracks plugin service/event registrations for safe cleanup."""

    def __init__(self, ctx: RuntimeContext, plugin_name: str):
        self.app_name = ctx.app_name
        self.root = ctx.root
        self.config = ctx.config
        self.manifest = ctx.manifest
        self._ctx = ctx
        self._plugin_name = plugin_name
        self._service_names: set[str] = set()
        self._subscriptions: list[tuple[str, Callable[[Any], None]]] = []

    @property
    def services(self):
        return _ServiceRegistryProxy(self)

    @property
    def event_bus(self):
        return _EventBusProxy(self)

    def _register_service(self, name: str, service: Any, capabilities: set[str] | None = None) -> None:
        self._ctx.services.register(name, service, capabilities=capabilities)
        self._service_names.add(name)

    def _unregister_service(self, name: str) -> None:
        self._ctx.services.unregister(name)
        self._service_names.discard(name)

    def _subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self._ctx.event_bus.subscribe(event_type, handler)
        self._subscriptions.append((event_type, handler))

    def _unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self._ctx.event_bus.unsubscribe(event_type, handler)
        self._subscriptions = [s for s in self._subscriptions if s != (event_type, handler)]

    def cleanup(self) -> None:
        for event_type, handler in list(self._subscriptions):
            self._ctx.event_bus.unsubscribe(event_type, handler)
        self._subscriptions.clear()

        for service_name in list(self._service_names):
            self._ctx.services.unregister(service_name)
        self._service_names.clear()


class _ServiceRegistryProxy:
    def __init__(self, owner: PluginRuntimeContext):
        self._owner = owner

    def register(self, name: str, service: Any, capabilities=None) -> None:
        cap_set = set(capabilities or [])
        self._owner._register_service(name, service, capabilities=cap_set)

    def unregister(self, name: str) -> None:
        self._owner._unregister_service(name)

    def __getattr__(self, item: str):
        return getattr(self._owner._ctx.services, item)


class _EventBusProxy:
    def __init__(self, owner: PluginRuntimeContext):
        self._owner = owner

    def subscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self._owner._subscribe(event_type, handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Any], None]) -> None:
        self._owner._unsubscribe(event_type, handler)

    def __getattr__(self, item: str):
        return getattr(self._owner._ctx.event_bus, item)


@dataclass
class _LoadedPlugin:
    plugin: Plugin
    module_name: str
    source_path: Path
    ctx_proxy: PluginRuntimeContext


class PluginManager:
    """Loads and manages hot-swappable runtime plugins from python/plugins."""

    def __init__(
        self,
        ctx: RuntimeContext,
        plugin_dir: Path | None = None,
        allowed_permissions: PluginPermissions | None = None,
    ):
        self.ctx = ctx
        self.plugin_dir = plugin_dir or (ctx.root / "python" / "plugins")
        self.allowed_permissions = allowed_permissions or PluginPermissions(filesystem_read=True)
        self._plugins: Dict[str, _LoadedPlugin] = {}

    def discover(self) -> list[Path]:
        if not self.plugin_dir.exists():
            return []
        return sorted(p for p in self.plugin_dir.glob("*.py") if p.name != "__init__.py")

    def load_from_path(self, plugin_path: Path) -> str | None:
        plugin_path = plugin_path.resolve()
        module_name = f"runtime_plugin_{plugin_path.stem}"
        try:
            module = self._import_module(module_name, plugin_path)
            plugin = self._extract_plugin(module)
        except Exception as exc:
            logger.exception("Failed to import plugin from %s: %s", plugin_path, exc)
            self.ctx.event_bus.publish(
                PluginLifecycleEvent("plugin_load_failed", {"path": str(plugin_path), "error": str(exc)})
            )
            return None

        return self.load_plugin(plugin, module_name=module_name, source_path=plugin_path)

    def load_plugin(self, plugin: Plugin, module_name: str = "inline", source_path: Path | None = None) -> str | None:
        if plugin.name in self._plugins:
            raise KeyError(f"Plugin already loaded: {plugin.name}")

        requested_permissions = self._extract_permissions(plugin)
        if not self.allowed_permissions.allows(requested_permissions):
            error = (
                f"Plugin '{plugin.name}' requests permissions {requested_permissions} "
                f"outside allowed policy {self.allowed_permissions}"
            )
            self.ctx.event_bus.publish(PluginLifecycleEvent("plugin_permission_denied", {"name": plugin.name, "error": error}))
            logger.error(error)
            return None

        plugin_ctx = PluginRuntimeContext(self.ctx, plugin.name)
        try:
            plugin.setup(plugin_ctx)  # type: ignore[arg-type]
        except Exception as exc:
            logger.exception("Plugin setup failed for %s: %s", plugin.name, exc)
            plugin_ctx.cleanup()
            self.ctx.event_bus.publish(
                PluginLifecycleEvent("plugin_failed", {"name": plugin.name, "error": str(exc)})
            )
            return None

        self._plugins[plugin.name] = _LoadedPlugin(
            plugin=plugin,
            module_name=module_name,
            source_path=source_path or self.plugin_dir,
            ctx_proxy=plugin_ctx,
        )
        self.ctx.event_bus.publish(
            PluginLifecycleEvent("plugin_loaded", {"name": plugin.name, "permissions": requested_permissions.__dict__})
        )
        return plugin.name

    def unload(self, plugin_name: str) -> None:
        loaded = self._plugins.pop(plugin_name, None)
        if not loaded:
            return

        try:
            loaded.plugin.shutdown(loaded.ctx_proxy)  # type: ignore[arg-type]
        except Exception as exc:
            logger.exception("Plugin shutdown failed for %s: %s", plugin_name, exc)
            self.ctx.event_bus.publish(
                PluginLifecycleEvent("plugin_shutdown_failed", {"name": plugin_name, "error": str(exc)})
            )
        finally:
            loaded.ctx_proxy.cleanup()

        self.ctx.event_bus.publish(PluginLifecycleEvent("plugin_unloaded", {"name": plugin_name}))

    def reload(self, plugin_name: str) -> str | None:
        loaded = self._plugins.get(plugin_name)
        if not loaded:
            raise KeyError(f"Plugin not loaded: {plugin_name}")
        source = loaded.source_path
        self.unload(plugin_name)
        return self.load_from_path(source)

    def load_all(self) -> list[str]:
        loaded: list[str] = []
        for plugin_path in self.discover():
            name = self.load_from_path(plugin_path)
            if name:
                loaded.append(name)
        return loaded

    def list_loaded(self) -> list[str]:
        return sorted(self._plugins.keys())

    @staticmethod
    def _extract_permissions(plugin: Plugin) -> PluginPermissions:
        permissions = getattr(plugin, "permissions", None)
        if permissions is None:
            return PluginPermissions()
        if isinstance(permissions, PluginPermissions):
            return permissions
        raise TypeError("Plugin.permissions must be PluginPermissions")

    @staticmethod
    def _extract_plugin(module: ModuleType) -> Plugin:
        plugin = getattr(module, "plugin", None)
        if plugin is None:
            raise ValueError("Plugin module must expose 'plugin' instance")
        if not hasattr(plugin, "name") or not hasattr(plugin, "setup") or not hasattr(plugin, "shutdown"):
            raise TypeError("Plugin instance must define name/setup/shutdown")
        return plugin

    @staticmethod
    def _import_module(module_name: str, plugin_path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(module_name, plugin_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot create import spec for {plugin_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
