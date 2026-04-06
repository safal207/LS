from __future__ import annotations

from importlib import import_module
import os

from .protocol import TaskRuntime


DEFAULT_RUNTIME_FACTORY = "ls.agent_shell.runtime.bindings.shell_runtime:build_shell_runtime"


class RuntimeBindingError(ValueError):
    """Raised when MCP façade cannot bind to a configured shell runtime."""


def resolve_task_runtime() -> TaskRuntime:
    """Resolve runtime factory from env (or shell-runtime default binding)."""

    target = os.getenv("LS_TASK_RUNTIME_FACTORY", DEFAULT_RUNTIME_FACTORY)

    module_name, sep, attr = target.partition(":")
    if not sep or not module_name or not attr:
        raise RuntimeBindingError("LS_TASK_RUNTIME_FACTORY must be in '<module>:<callable>' format")

    try:
        module = import_module(module_name)
        factory = getattr(module, attr)
        runtime = factory()
        required_methods = (
            "plan_task",
            "run_task",
            "resume_task",
            "get_status",
            "get_trace",
            "list_artifacts",
            "approve",
            "reject",
        )
        missing = [name for name in required_methods if not callable(getattr(runtime, name, None))]
        if missing:
            raise RuntimeBindingError(
                f"Runtime '{target}' does not implement required methods: {', '.join(missing)}"
            )
        return runtime
    except RuntimeBindingError:
        raise
    except Exception as exc:
        raise RuntimeBindingError(f"Unable to resolve runtime binding '{target}': {exc}") from exc
