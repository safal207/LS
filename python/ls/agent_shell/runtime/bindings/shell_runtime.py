from __future__ import annotations

from importlib import import_module
from typing import Any


# Ordered bindings to the authoritative shell runtime lineage.
# Rebase can keep/adjust this list without touching MCP façade code.
SHELL_RUNTIME_CANDIDATES = (
    "ls.agent_shell.runtime.task_manager:TaskManager",
    "ls.agent_shell.runtime.runtime_factory:build_runtime",
    "ls.agent_shell.core.runtime:build_runtime",
)


def _load_callable(target: str) -> Any:
    module_name, _, attr = target.partition(":")
    module = import_module(module_name)
    return getattr(module, attr)


def build_shell_runtime() -> Any:
    errors: list[str] = []
    for target in SHELL_RUNTIME_CANDIDATES:
        try:
            candidate = _load_callable(target)
            runtime = candidate() if callable(candidate) else candidate
            return runtime
        except Exception as exc:
            errors.append(f"{target} -> {exc}")
    details = "; ".join(errors) if errors else "no candidates configured"
    raise ValueError(f"Could not bind shell runtime. Tried: {details}")
