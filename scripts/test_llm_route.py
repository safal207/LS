from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = REPO_ROOT / "python"
MODULES_DIR = PYTHON_DIR / "modules"

for candidate in (str(PYTHON_DIR), str(MODULES_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from config import (  # noqa: E402
    LLM_BACKEND,
    LLM_FALLBACK_BACKEND,
    MAX_TOKENS,
    SYSTEM_PROMPT,
    TEMPERATURE,
)
from llm.backends.router import build_llm_backend  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test active LLM backend route.")
    parser.add_argument(
        "--question",
        default="Why did you choose this stack and how did you evaluate the trade-offs?",
        help="User question to send through the active LLM route.",
    )
    parser.add_argument(
        "--system-prompt",
        default=SYSTEM_PROMPT,
        help="Optional system prompt override. Defaults to config.SYSTEM_PROMPT.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=MAX_TOKENS,
        help="Generation max tokens.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=TEMPERATURE,
        help="Generation temperature.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print resolved route, do not call the backend.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    backend = build_llm_backend()
    route = backend.route

    print("route.primary =", backend.primary)
    print("route.fallback =", backend.fallback_chain)
    print("route.effective =", route)

    if args.dry_run:
        return 0

    response = backend.generate(
        messages=[{"role": "user", "content": args.question}],
        system_prompt=args.system_prompt,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        metadata={"source": "scripts/test_llm_route.py"},
    )

    print("response.ok =", response.ok)
    print("response.provider =", response.provider)
    print("response.model =", response.model)
    print("response.latency_ms =", round(float(response.latency_ms), 2))
    print("response.was_fallback_used =", response.was_fallback_used)
    print("response.fallback_from =", response.fallback_from)
    print("response.fallback_to =", response.fallback_to)
    print("response.error =", response.error)
    print("response.text =")
    print(response.text)
    print("response.raw =")
    print(json.dumps(response.raw, ensure_ascii=False, indent=2) if response.raw else "null")
    route_info = (response.raw or {}).get("route") if isinstance(response.raw, dict) else None
    if route_info:
        print("route.trace =")
        print(json.dumps(route_info, ensure_ascii=False, indent=2))
    return 0 if response.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
