from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except Exception as exc:  # pragma: no cover - import guard
    raise RuntimeError("PyYAML is required for config loading") from exc

_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a mapping: {path}")
    return data


def _detect_app(default: str = "console") -> str:
    env_app = os.getenv("LS_APP")
    if env_app:
        return env_app
    argv0 = (sys.argv[0] if sys.argv else "").lower()
    if "ghostgpt" in argv0:
        return "ghostgpt"
    return default


def load_config(app: str) -> Dict[str, Any]:
    if app not in {"console", "ghostgpt"}:
        raise ValueError(f"Unknown app config: {app}")
    if app in _CONFIG_CACHE:
        return _CONFIG_CACHE[app]

    root = Path(__file__).resolve().parents[3]
    cfg = _load_yaml(root / "config" / "base.yaml")
    cfg = _deep_merge(cfg, _load_yaml(root / "config" / f"{app}.yaml"))
    cfg = _deep_merge(cfg, _load_yaml(root / "config" / "local.yaml"))

    groq_key = os.getenv("GROQ_API_KEY", "")
    cfg.setdefault("llm", {}).setdefault("groq", {})
    if groq_key:
        cfg["llm"]["groq"]["api_key"] = groq_key
    else:
        cfg["llm"]["groq"].setdefault("api_key", "")

    os.environ.setdefault("LS_APP", app)
    _CONFIG_CACHE[app] = cfg
    return cfg


def get_config(app: str | None = None) -> Dict[str, Any]:
    if not app:
        app = _detect_app()
    return load_config(app)
