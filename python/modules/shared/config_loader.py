from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}
_APP_ALIASES_CACHE: Dict[str, str] | None = None
_CACHE_LOCK = threading.Lock()


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


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_app_aliases() -> Dict[str, str]:
    global _APP_ALIASES_CACHE
    with _CACHE_LOCK:
        if _APP_ALIASES_CACHE is not None:
            return _APP_ALIASES_CACHE

    default_aliases = {
        "console": "console",
        "ghostgpt": "ghostgpt",
        "ghost_gui": "ghostgpt",
        "interview_copilot": "ghostgpt",
        "operator_runtime": "ghostgpt",
    }

    registry = _load_yaml(_repo_root() / "config" / "apps.yaml")
    apps = registry.get("apps") if isinstance(registry, dict) else None
    if not isinstance(apps, dict):
        computed = default_aliases
    else:
        aliases: Dict[str, str] = {}
        for app_name, app_cfg in apps.items():
            if not isinstance(app_name, str) or not app_name.strip():
                raise ValueError("Invalid app name in config/apps.yaml")
            normalized_name = app_name.strip().lower()
            aliases[normalized_name] = normalized_name

            if not isinstance(app_cfg, dict):
                raise ValueError(f"Invalid app config in config/apps.yaml for '{app_name}'")
            app_aliases = app_cfg.get("aliases", [])
            if not isinstance(app_aliases, list):
                raise ValueError(f"'aliases' must be a list for app '{app_name}'")

            for alias in app_aliases:
                if not isinstance(alias, str) or not alias.strip():
                    raise ValueError(f"Alias must be a non-empty string for app '{app_name}'")
                aliases[alias.strip().lower()] = normalized_name
        computed = aliases or default_aliases

    with _CACHE_LOCK:
        if _APP_ALIASES_CACHE is not None:
            return _APP_ALIASES_CACHE
        _APP_ALIASES_CACHE = computed
        return _APP_ALIASES_CACHE


def _normalize_app_name(app: str) -> str:
    app_key = app.strip().lower()
    aliases = _load_app_aliases()
    if app_key in aliases:
        return aliases[app_key]
    raise ValueError(f"Unknown app config: {app}. Available apps: {sorted(set(aliases.values()))}")


def _detect_app(default: str = "console") -> str:
    env_app = os.getenv("LS_APP")
    if env_app:
        return _normalize_app_name(env_app)
    argv0 = (sys.argv[0] if sys.argv else "").lower()
    if "ghostgpt" in argv0:
        return "ghostgpt"
    return _normalize_app_name(default)


def _validate_runtime_schema(config: Dict[str, Any], app: str) -> None:
    required_top_level = {
        "hardware": dict,
        "audio": dict,
        "stt": dict,
        "llm": dict,
        "agent": dict,
    }
    for section, expected_type in required_top_level.items():
        if section not in config:
            raise ValueError(f"Invalid config for '{app}': missing top-level section '{section}'")
        if not isinstance(config[section], expected_type):
            raise ValueError(
                f"Invalid config for '{app}': section '{section}' must be {expected_type.__name__}"
            )

    numeric_checks: list[tuple[list[str], type, float | None]] = [
        (["hardware", "max_ram_usage_mb"], int, 1),
        (["hardware", "target_latency_sec"], (int, float), 0),
        (["audio", "sample_rate"], int, 1),
        (["audio", "chunk_duration"], (int, float), 0),
        (["llm", "ram_threshold_gb"], (int, float), 0),
    ]

    for path, expected_type, min_value in numeric_checks:
        current: Any = config
        for key in path:
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"Invalid config for '{app}': missing key '{'.'.join(path)}'")
            current = current[key]
        if not isinstance(current, expected_type):
            type_name = expected_type.__name__ if isinstance(expected_type, type) else "number"
            raise ValueError(f"Invalid config for '{app}': key '{'.'.join(path)}' must be {type_name}")
        if min_value is not None and float(current) <= min_value:
            raise ValueError(f"Invalid config for '{app}': key '{'.'.join(path)}' must be > {min_value}")


def load_config(app: str) -> Dict[str, Any]:
    normalized_app = _normalize_app_name(app)
    with _CACHE_LOCK:
        if normalized_app in _CONFIG_CACHE:
            return _CONFIG_CACHE[normalized_app]

    root = _repo_root()
    cfg = _load_yaml(root / "config" / "base.yaml")
    cfg = _deep_merge(cfg, _load_yaml(root / "config" / f"{normalized_app}.yaml"))
    cfg = _deep_merge(cfg, _load_yaml(root / "config" / "local.yaml"))

    groq_key = os.getenv("GROQ_API_KEY", "")
    cfg.setdefault("llm", {}).setdefault("groq", {})
    if groq_key:
        cfg["llm"]["groq"]["api_key"] = groq_key
    else:
        cfg["llm"]["groq"].setdefault("api_key", "")

    _validate_runtime_schema(cfg, normalized_app)

    os.environ.setdefault("LS_APP", normalized_app)
    with _CACHE_LOCK:
        cached = _CONFIG_CACHE.get(normalized_app)
        if cached is not None:
            return cached
        _CONFIG_CACHE[normalized_app] = cfg
    return cfg


def get_config(app: str | None = None) -> Dict[str, Any]:
    if not app:
        app = _detect_app()
    return load_config(app)
