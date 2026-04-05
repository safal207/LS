from __future__ import annotations

from importlib import import_module
import os

from .protocol import TaskRuntime
from .task_manager import TaskManager


DEFAULT_FACTORY = "ls.agent_shell.runtime.factory:build_default_runtime"


def build_default_runtime() -> TaskRuntime:
    return TaskManager()


def resolve_task_runtime() -> TaskRuntime:
    """Resolve runtime factory from env to keep MCP layer thin/pluggable.

    Set `LS_TASK_RUNTIME_FACTORY` to `<module>:<callable>` to bind MCP façade
    to an existing runtime implementation from another package.
    """

    target = os.getenv("LS_TASK_RUNTIME_FACTORY", DEFAULT_FACTORY)
    module_name, sep, attr = target.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError("LS_TASK_RUNTIME_FACTORY must be in '<module>:<callable>' format")

    module = import_module(module_name)
    factory = getattr(module, attr)
    runtime = factory()
    return runtime
