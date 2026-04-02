from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class RuntimeManifest:
    """Describes runtime profile/version/limits for a running app."""

    app_name: str
    runtime_version: str = "1.0"
    features: Dict[str, bool] = field(default_factory=dict)
    limits: Dict[str, Any] = field(default_factory=dict)
    transport_mode: str = "local"


def build_manifest(app_name: str, config: Dict[str, Any]) -> RuntimeManifest:
    runtime_cfg = config.get("runtime", {}) if isinstance(config, dict) else {}
    return RuntimeManifest(
        app_name=app_name,
        runtime_version=str(runtime_cfg.get("version", "1.0")),
        features=dict(runtime_cfg.get("features", {})),
        limits=dict(runtime_cfg.get("limits", {})),
        transport_mode=str(runtime_cfg.get("transport_mode", "local")),
    )
