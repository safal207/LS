from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from llm.qwen_handler import collect_windows_context, save_to_codex  # noqa: F401

__all__ = ["collect_windows_context", "save_to_codex"]
