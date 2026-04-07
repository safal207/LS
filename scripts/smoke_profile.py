#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import yaml


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def bool_env(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def check_ollama(host: str, timeout_sec: float = 3.0) -> tuple[bool, str]:
    url = f"{host.rstrip('/')}/api/tags"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
            models = payload.get("models", [])
            names = [m.get("name", "?") for m in models if isinstance(m, dict)]
            return True, f"{len(names)} model(s): {', '.join(names) if names else 'none'}"
    except urllib.error.URLError as exc:
        return False, f"unreachable: {exc}"
    except Exception as exc:  # pragma: no cover - defensive smoke check
        return False, f"error: {exc}"


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    local_cfg = load_yaml(repo_root / "config" / "local.yaml")
    llm = local_cfg.get("llm", {}) if isinstance(local_cfg, dict) else {}

    backend = llm.get("backend", "<unset>")
    fallback = llm.get("fallback_backend", "<unset>")
    model_name = llm.get("model_name", "<unset>")

    gonka_enabled = bool((llm.get("gonka", {}) or {}).get("enabled", False))
    mimo_enabled = bool((llm.get("mimo", {}) or {}).get("enabled", False))
    use_groq = bool(llm.get("use_groq", False))

    groq_key = bool(os.getenv("GROQ_API_KEY"))
    gonka_key = bool(os.getenv("GONKA_API_KEY"))
    mimo_key = bool(os.getenv("MIMO_API_KEY"))

    ollama_host = ((llm.get("ollama", {}) or {}).get("host") or "http://localhost:11434")
    ollama_ok, ollama_msg = check_ollama(str(ollama_host))

    print("=== Profile Smoke Check ===")
    print(f"backend={backend}")
    print(f"fallback_backend={fallback}")
    print(f"model_name={model_name}")
    print(f"gonka_enabled={gonka_enabled} has_GONKA_API_KEY={gonka_key}")
    print(f"use_groq={use_groq} has_GROQ_API_KEY={groq_key}")
    print(f"mimo_enabled={mimo_enabled} has_MIMO_API_KEY={mimo_key}")
    print(f"ollama_host={ollama_host} status={'ok' if ollama_ok else 'fail'} ({ollama_msg})")

    warnings: list[str] = []
    if gonka_enabled and not gonka_key:
        warnings.append("gonka enabled but GONKA_API_KEY missing")
    if use_groq and not groq_key:
        warnings.append("use_groq=true but GROQ_API_KEY missing")
    if mimo_enabled and not mimo_key:
        warnings.append("mimo enabled but MIMO_API_KEY missing")
    if not ollama_ok:
        warnings.append("ollama is unreachable")

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print(f" - {item}")
        return 2

    print("\n✅ Smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
