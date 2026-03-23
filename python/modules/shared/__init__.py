from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = [
    "load_config",
    "get_config",
    "RuntimeContext",
    "bootstrap_app",
    "EventBus",
    "ServiceRegistry",
    "RuntimeManifest",
    "build_manifest",
    "DynamicModuleLoader",
    "RuntimeModule",
    "ModuleLifecycleEvent",
    "PluginManager",
    "Plugin",
    "PluginLifecycleEvent",
    "PluginPermissions",
    "MonitorService",
    "MonitorAlert",
    "InterviewUtterance",
    "ensure_interview_item",
    "check_system_resources",
    "format_latency",
    "is_question",
]

if TYPE_CHECKING:
    from .config_loader import load_config, get_config
    from .bootstrap import RuntimeContext, bootstrap_app
    from .event_bus import EventBus
    from .service_registry import ServiceRegistry
    from .runtime_manifest import RuntimeManifest, build_manifest
    from .module_loader import DynamicModuleLoader, RuntimeModule, ModuleLifecycleEvent
    from .plugin_manager import PluginManager, Plugin, PluginLifecycleEvent, PluginPermissions
    from .monitoring import MonitorService, MonitorAlert
    from .interview_schema import InterviewUtterance, ensure_interview_item
    from .utils import check_system_resources, format_latency, is_question


def __getattr__(name: str):
    if name in ("load_config", "get_config"):
        from .config_loader import load_config, get_config
        return load_config if name == "load_config" else get_config
    if name in ("RuntimeContext", "bootstrap_app"):
        from .bootstrap import RuntimeContext, bootstrap_app
        return RuntimeContext if name == "RuntimeContext" else bootstrap_app
    if name == "EventBus":
        from .event_bus import EventBus
        return EventBus
    if name == "ServiceRegistry":
        from .service_registry import ServiceRegistry
        return ServiceRegistry
    if name in ("RuntimeManifest", "build_manifest"):
        from .runtime_manifest import RuntimeManifest, build_manifest
        return RuntimeManifest if name == "RuntimeManifest" else build_manifest
    if name in ("DynamicModuleLoader", "RuntimeModule", "ModuleLifecycleEvent"):
        from .module_loader import DynamicModuleLoader, RuntimeModule, ModuleLifecycleEvent
        return {
            "DynamicModuleLoader": DynamicModuleLoader,
            "RuntimeModule": RuntimeModule,
            "ModuleLifecycleEvent": ModuleLifecycleEvent,
        }[name]
    if name in ("PluginManager", "Plugin", "PluginLifecycleEvent", "PluginPermissions"):
        from .plugin_manager import PluginManager, Plugin, PluginLifecycleEvent, PluginPermissions
        return {
            "PluginManager": PluginManager,
            "Plugin": Plugin,
            "PluginLifecycleEvent": PluginLifecycleEvent,
            "PluginPermissions": PluginPermissions,
        }[name]
    if name in ("MonitorService", "MonitorAlert"):
        from .monitoring import MonitorService, MonitorAlert
        return MonitorService if name == "MonitorService" else MonitorAlert
    if name in ("InterviewUtterance", "ensure_interview_item"):
        from .interview_schema import InterviewUtterance, ensure_interview_item
        return InterviewUtterance if name == "InterviewUtterance" else ensure_interview_item
    if name in ("check_system_resources", "format_latency", "is_question"):
        from . import utils as _utils
        return getattr(_utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
