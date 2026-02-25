from __future__ import annotations

import importlib
import importlib.util
import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CODEX_ROOT = _REPO_ROOT / "codex"
_CODEX_WINDOWS_PATH = _CODEX_ROOT / "events" / "windows"
_CODEX_INDEX_PATH = _CODEX_ROOT / "index.json"
_CODEX_CAUSAL_PATH = _CODEX_ROOT / "causal_memory"
_CODEX_CAUSAL_INDEX_PATH = _CODEX_CAUSAL_PATH / "index.json"
_MAX_CODEX_EVENTS = 20

_RUST_MODULE = None
_TRACKER = None
_REGISTRY_MANAGER = None


def load_rust_module():
    global _RUST_MODULE
    if _RUST_MODULE is not None:
        return _RUST_MODULE

    for module_name in ("rust_core", "ghostgpt_core"):
        if importlib.util.find_spec(module_name) is not None:
            _RUST_MODULE = importlib.import_module(module_name)
            return _RUST_MODULE
    return None


def get_focus_tracker():
    global _TRACKER
    if _TRACKER is not None:
        return _TRACKER

    rust_module = load_rust_module()
    if rust_module is None:
        return None

    tracker_cls = getattr(rust_module, "FocusTracker", None)
    if tracker_cls is None:
        return None

    _TRACKER = tracker_cls()
    return _TRACKER


@lru_cache(maxsize=1)
def get_registry_manager(yaml_path: str = "config/base.yaml"):
    """Singleton-style cache for RegistryManager. One instance per process and path."""
    rust_module = load_rust_module()
    if rust_module is None:
        return None

    manager_cls = getattr(rust_module, "RegistryManager", None)
    return manager_cls(yaml_path) if manager_cls is not None else None


def save_to_codex(event_data: dict) -> Optional[Path]:
    if not isinstance(event_data, dict):
        return None

    # Codex mirror can be disabled via registry config (registry is SOT)
    reg = get_registry_manager()
    if reg and reg.get_config("enable_codex_mirror") == "false":
        return None

    timestamp = event_data.get("timestamp") or datetime.now(timezone.utc).isoformat()
    safe_ts = timestamp.replace(":", "").replace("-", "").replace(".", "")
    event_type = str(event_data.get("event_type", "focus_change"))

    if event_type.startswith("causal_"):
        target_dir = _CODEX_CAUSAL_PATH
        index_path = _CODEX_CAUSAL_INDEX_PATH
        prefix = "causal_trace"
        provider = "causal_memory_v1"
    else:
        target_dir = _CODEX_WINDOWS_PATH
        index_path = _CODEX_INDEX_PATH
        prefix = "focus_event"
        provider = "windows_context_v1"

    target_dir.mkdir(parents=True, exist_ok=True)
    event_file = target_dir / f"{prefix}_{safe_ts}.json"
    event_file.write_text(json.dumps(event_data, ensure_ascii=False, indent=2), encoding="utf-8")

    index_payload = {
        "provider": provider,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "max_in_memory": 10,
        "max_index_entries": _MAX_CODEX_EVENTS,
        "events": [],
    }
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                index_payload.update(existing)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            logger.warning("Failed to parse codex index, rebuilding from scratch")

    events = index_payload.get("events", [])
    if not isinstance(events, list):
        events = []

    events.insert(
        0,
        {
            "timestamp": timestamp,
            "event_type": event_type,
            "path": str(event_file),
            "confusion_score": event_data.get("confusion_score", 0.0),
            "confidence": event_data.get("confidence", 0.9),
        },
    )

    index_payload["events"] = events[:_MAX_CODEX_EVENTS]
    index_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    index_path.write_text(json.dumps(index_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return event_file


def collect_windows_context(session_id: str = "default") -> Optional[dict]:
    tracker = get_focus_tracker()
    if tracker is None:
        return None

    active_window = tracker.get_active_window()
    if not isinstance(active_window, dict):
        return None

    reg = get_registry_manager()
    raw_threshold = reg.get_config("confusion_threshold") if reg else "0.75"
    try:
        confusion_threshold = float(raw_threshold or "0.75")
    except (TypeError, ValueError):
        confusion_threshold = 0.75

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "focus_change",
        "session_id": session_id,
        "active_window": {
            "title": active_window.get("title", ""),
            "class_name": active_window.get("class_name", ""),
            "hwnd": active_window.get("hwnd", "0x0"),
            "process_name": active_window.get("process_name", ""),
        },
        "text_snippet": active_window.get("text_snippet", ""),
        "cursor_position": active_window.get("cursor_position", {"line": 0, "column": 0}),
        "confusion_score": float(active_window.get("confusion_score", 0.0)),
        "fuzzy_factors": active_window.get("fuzzy_factors", {}),
        "confidence": float(active_window.get("confidence", 0.9)),
        "source": "ghostgpt_core::focus_tracker",
    }

    if event["confusion_score"] > confusion_threshold:
        event["event_type"] = "confusion_ping"

    save_to_codex(event)
    if reg:
        reg.save_last_event_id(f"event_{int(datetime.now(timezone.utc).timestamp())}")
    return event
