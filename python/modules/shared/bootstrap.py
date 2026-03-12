from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, Any

from modules.shared.config_loader import load_config


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


def bootstrap_app(entry_file: str, app: str) -> Dict[str, Any]:
    """Prepare runtime environment for a top-level app and load merged config."""
    setup_runtime_paths(entry_file)
    os.environ.setdefault("LS_APP", app)
    return load_config(app)
