from __future__ import annotations

import importlib
import os
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON_DIR = ROOT / "python"
MODULES_DIR = PYTHON_DIR / "modules"

# Keep python/modules and python at the front so they win import precedence.
# ROOT must come before MODULES_DIR so root-level packages (e.g. agent/) are not
# shadowed by python/modules/agent/.
for path in [MODULES_DIR, ROOT, PYTHON_DIR]:
    path_str = str(path)
    if path_str in sys.path:
        sys.path.remove(path_str)
    if path.exists():
        sys.path.insert(0, path_str)

# Legacy import aliases used by part of the test-suite.
_aliases = {
    "agent.loop": "modules.agent.loop",
    "agent.sinks": "modules.agent.sinks",
    "agent.event_schema": "modules.agent.event_schema",
    "llm": "modules.llm",
    "llm.temporal": "modules.llm.temporal",
    "llm.llm_module": "modules.llm.llm_module",
    "llm.breaker": "modules.llm.breaker",
    "llm.errors": "modules.llm.errors",
    "config": "modules.config",
}

for legacy, canonical in _aliases.items():
    if legacy in sys.modules:
        continue
    try:
        sys.modules[legacy] = importlib.import_module(canonical)
    except Exception as exc:
        warnings.warn(
            f"Legacy alias {legacy!r} -> {canonical!r} failed: {exc}",
            ImportWarning,
            stacklevel=1,
        )

os.environ.setdefault("LS_APP", "console")
