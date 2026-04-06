from __future__ import annotations

from importlib import import_module
import os

from .protocol import TaskRuntime


class RuntimeBindingError(ValueError):
    """Raised when MCP façade cannot bind to a configured shell runtime."""


def resolve_task_runtime() -> TaskRuntime:
    """Resolve runtime factory from env.

    MCP façade intentionally does not ship a default runtime core to avoid
    drift from the authoritative shell runtime. Set:
      LS_TASK_RUNTIME_FACTORY=<module>:<callable>
    where callable returns a TaskRuntime-compatible object.
    """

    target = os.getenv("LS_TASK_RUNTIME_FACTORY")
    if not target:
        raise RuntimeBindingError("LS_TASK_RUNTIME_FACTORY is required for MCP runtime binding")

    module_name, sep, attr = target.partition(":")
    if not sep or not module_name or not attr:
        raise RuntimeBindingError("LS_TASK_RUNTIME_FACTORY must be in '<module>:<callable>' format")

    module = import_module(module_name)
    factory = getattr(module, attr)
    runtime = factory()
    return runtime
