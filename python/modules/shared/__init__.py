from __future__ import annotations

from typing import TYPE_CHECKING

from .config_loader import load_config, get_config
from .bootstrap import RuntimeContext, bootstrap_app
from .event_bus import EventBus

__all__ = [
    "load_config",
    "get_config",
    "RuntimeContext",
    "bootstrap_app",
    "EventBus",
    "check_system_resources",
    "format_latency",
    "is_question",
]

if TYPE_CHECKING:
    from .utils import check_system_resources, format_latency, is_question


def __getattr__(name: str):
    if name in ("check_system_resources", "format_latency", "is_question"):
        from . import utils as _utils
        return getattr(_utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
