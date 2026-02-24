from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from llm.qwen_handler import (  # noqa: F401, E402
    collect_windows_context,
    get_registry_manager,
    replay_thread,
    replay_thread_ui,
    save_causal_trace,
    save_to_codex,
)

__all__ = ["collect_windows_context", "save_to_codex", "get_registry_manager", "save_causal_trace", "replay_thread", "replay_thread_ui", "init_stealth"]


def init_stealth(*, enable_auto_start: bool = True):
    """Initialize stealth bridge; auto-start is enabled by default (opt-out via enable_auto_start=False)."""
    if not isinstance(enable_auto_start, bool):
        raise TypeError(f"enable_auto_start must be a bool, got {type(enable_auto_start)}")
    reg = get_registry_manager()
    if reg and enable_auto_start:
        cmd = f'{sys.executable} {ROOT / "apps" / "ghostgpt" / "ghost_gui.py"} --stealth'
        reg.enable_auto_start(cmd)
    return reg
