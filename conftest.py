from __future__ import annotations

import importlib
import os
import warnings
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON_DIR = ROOT / "python"
MODULES_DIR = PYTHON_DIR / "modules"

root_str = str(ROOT)
python_str = str(PYTHON_DIR)
modules_str = str(MODULES_DIR)

if modules_str in sys.path:
    sys.path.remove(modules_str)
if root_str not in sys.path:
    sys.path.insert(0, root_str)
if PYTHON_DIR.exists() and python_str not in sys.path:
    sys.path.insert(1, python_str)

# Legacy import aliases used by part of the test-suite.
_aliases = {
    "agent": "modules.agent",
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
