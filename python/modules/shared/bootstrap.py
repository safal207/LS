from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from .config_loader import load_config
from .event_bus import EventBus
from .service_registry import ServiceRegistry
from .runtime_manifest import RuntimeManifest, build_manifest


@dataclass(frozen=True)
class RuntimeContext:
    """Runtime container for top-level LS/GhostGPT applications."""

    app_name: str
    root: Path
    config: Dict[str, Any]
    event_bus: EventBus = field(default_factory=EventBus)
    services: ServiceRegistry = field(default_factory=ServiceRegistry)
    manifest: RuntimeManifest | None = None


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
    cfg = load_config(app)
    manifest = build_manifest(app, cfg)
    return RuntimeContext(app_name=app, root=root, config=cfg, manifest=manifest)
