#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "python" / "modules"
SHARED = MODULES / "shared"
for candidate in (ROOT, MODULES, SHARED):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from config_loader import load_config  # noqa: E402


def _nested_get(mapping: dict[str, Any], path: list[str], default: Any = "") -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _split_backends(value: Any) -> set[str]:
    if isinstance(value, str):
        return {item.strip().lower() for item in value.split(",") if item.strip()}
    if isinstance(value, list):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    return set()


def _effective_secret(cfg: dict[str, Any], env_name: str, path: list[str]) -> bool:
    env_value = os.getenv(env_name, "").strip()
    if env_value:
        return True
    config_value = str(_nested_get(cfg, path, "")).strip()
    return bool(config_value)


def _needs_ollama(llm: dict[str, Any]) -> bool:
    backend = str(llm.get("backend", "")).strip().lower()
    if backend == "local":
        return True

    if "local" in _split_backends(llm.get("fallback_backend", "")):
        return True

    meritocracy = llm.get("meritocracy", {})
    if isinstance(meritocracy, dict) and _as_bool(meritocracy.get("enabled", False)):
        return "local" in _split_backends(meritocracy.get("backends", []))

    return False


def check_ollama(host: str, timeout_sec: float = 3.0) -> tuple[bool, str]:
    url = f"{host.rstrip('/')}/api/tags"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
            models = payload.get("models", [])
            names = [model.get("name", "?") for model in models if isinstance(model, dict)]
            return True, f"{len(names)} model(s): {', '.join(names) if names else 'none'}"
    except urllib.error.URLError as exc:
        return False, f"unreachable: {exc}"
    except Exception as exc:  # pragma: no cover - defensive smoke check
        return False, f"error: {exc}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check the effective LLM profile and dependencies.")
    parser.add_argument(
        "--app",
        default=os.getenv("LS_APP", "console"),
        help="Application config to load via config_loader (default: LS_APP or console).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.app)
    llm = cfg.get("llm", {}) if isinstance(cfg, dict) else {}
    if not isinstance(llm, dict):
        raise ValueError("llm config must be a mapping")

    backend = llm.get("backend", "<unset>")
    fallback = llm.get("fallback_backend", "<unset>")
    model_name = llm.get("model_name", "<unset>")

    gonka_enabled = _as_bool(_nested_get(llm, ["gonka", "enabled"], False))
    mimo_enabled = _as_bool(_nested_get(llm, ["mimo", "enabled"], False))
    use_groq = _as_bool(llm.get("use_groq", False))

    groq_ready = _effective_secret(cfg, "GROQ_API_KEY", ["llm", "groq", "api_key"])
    gonka_ready = _effective_secret(cfg, "GONKA_API_KEY", ["llm", "gonka", "api_key"])
    mimo_ready = _effective_secret(cfg, "MIMO_API_KEY", ["llm", "mimo", "api_key"])

    ollama_host = str(_nested_get(llm, ["ollama", "host"], "http://localhost:11434"))
    ollama_required = _needs_ollama(llm)
    ollama_ok = False
    ollama_msg = "skipped"
    if ollama_required:
        ollama_ok, ollama_msg = check_ollama(ollama_host)

    print("=== Profile Smoke Check ===")
    print(f"app={args.app}")
    print(f"backend={backend}")
    print(f"fallback_backend={fallback}")
    print(f"model_name={model_name}")
    print(f"gonka_enabled={gonka_enabled} gonka_ready={gonka_ready}")
    print(f"use_groq={use_groq} groq_ready={groq_ready}")
    print(f"mimo_enabled={mimo_enabled} mimo_ready={mimo_ready}")
    print(
        f"ollama_required={ollama_required} "
        f"ollama_host={ollama_host} "
        f"status={'ok' if ollama_ok else 'skip' if not ollama_required else 'fail'} "
        f"({ollama_msg})"
    )

    warnings: list[str] = []
    if gonka_enabled and not gonka_ready:
        warnings.append("gonka enabled but no effective Gonka API key is configured")
    if use_groq and not groq_ready:
        warnings.append("use_groq=true but no effective Groq API key is configured")
    if mimo_enabled and not mimo_ready:
        warnings.append("mimo enabled but no effective MiMo API key is configured")
    if ollama_required and not ollama_ok:
        warnings.append("local backend is reachable in config, but Ollama is unreachable")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f" - {item}")
        return 2

    print("\nSmoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
