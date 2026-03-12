from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from modules.shared.config_loader import load_config
from modules.shared.event_bus import EventBus


@dataclass(frozen=True)
class RuntimeContext:
    """Runtime container for top-level LS/GhostGPT applications."""

    app_name: str
    root: Path
    config: Dict[str, Any]
    event_bus: EventBus = field(default_factory=EventBus)


def setup_runtime_paths(entry_file: str) -> Path:
    """Ensure repository roots are available in sys.path.

    Returns the repository root path for optional reuse.
    """
    root = Path(entry_file).resolve().parents[2]
    python_root = root / "python"
    modules_root = python_root / "modules"

    for path in (python_root, modules_root, root):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

    return root


def bootstrap_app(entry_file: str, app: str) -> RuntimeContext:
    """Prepare runtime environment and return a full runtime context."""
    root = setup_runtime_paths(entry_file)
    os.environ.setdefault("LS_APP", app)
    cfg = load_config(app)
    return RuntimeContext(app_name=app, root=root, config=cfg)
