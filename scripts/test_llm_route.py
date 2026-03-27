from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = REPO_ROOT / "python"
MODULES_DIR = PYTHON_DIR / "modules"

for candidate in (str(PYTHON_DIR), str(MODULES_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from config import (  # noqa: E402
    GONKA_API_KEY,
    GONKA_BASE_URL,
    GONKA_ENABLED,
    GONKA_MODEL,
    GROQ_API_KEY,
    GROQ_BASE_URL,
    GROQ_MODEL,
    LLM_BACKEND,
    LLM_FALLBACK_BACKEND,
    MIMO_API_KEY,
    MIMO_BASE_URL,
    MIMO_ENABLED,
    MIMO_MODEL,
    MAX_TOKENS,
    SYSTEM_PROMPT,
    TEMPERATURE,
)
from modules.llm.quality import evaluate_llm_answer_quality  # noqa: E402
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
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare Gonka, cloud, and local backends independently and score them.",
    )
    parser.add_argument(
        "--thread-context",
        default=None,
        help="Optional conversation thread context for quality scoring.",
    )
    parser.add_argument(
        "--require-all",
        action="store_true",
        help="Fail fast if any compared backend is not configured and ready.",
    )
    return parser.parse_args()


def _backend_status() -> list[dict[str, object]]:
    status = []
    status.append(
        {
            "name": "gonka",
            "enabled": bool(GONKA_ENABLED),
            "configured": bool(GONKA_API_KEY and GONKA_BASE_URL and GONKA_MODEL),
            "model": GONKA_MODEL,
            "missing": [
                name
                for name, ok in (
                    ("GONKA_ENABLED=true", bool(GONKA_ENABLED)),
                    ("GONKA_API_KEY", bool(GONKA_API_KEY)),
                    ("GONKA_BASE_URL", bool(GONKA_BASE_URL)),
                    ("GONKA_MODEL", bool(GONKA_MODEL)),
                )
                if not ok
            ],
        }
    )
    status.append(
        {
            "name": "mimo",
            "enabled": bool(MIMO_ENABLED),
            "configured": bool(MIMO_API_KEY and MIMO_BASE_URL and MIMO_MODEL),
            "model": MIMO_MODEL,
            "missing": [
                name
                for name, ok in (
                    ("MIMO_ENABLED=true", bool(MIMO_ENABLED)),
                    ("MIMO_API_KEY", bool(MIMO_API_KEY)),
                    ("MIMO_BASE_URL", bool(MIMO_BASE_URL)),
                    ("MIMO_MODEL", bool(MIMO_MODEL)),
                )
                if not ok
            ],
        }
    )
    status.append(
        {
            "name": "cloud",
            "enabled": bool(GROQ_API_KEY),
            "configured": bool(GROQ_API_KEY and GROQ_BASE_URL and GROQ_MODEL),
            "model": GROQ_MODEL,
            "missing": [
                name
                for name, ok in (
                    ("GROQ_API_KEY", bool(GROQ_API_KEY)),
                    ("GROQ_BASE_URL", bool(GROQ_BASE_URL)),
                    ("GROQ_MODEL", bool(GROQ_MODEL)),
                )
                if not ok
            ],
        }
    )
    status.append(
        {
            "name": "local",
            "enabled": True,
            "configured": True,
            "model": backend_model_name("local"),
            "missing": [],
        }
    )
    return status


def backend_model_name(name: str) -> str:
    if name == "gonka":
        return GONKA_MODEL
    if name == "mimo":
        return MIMO_MODEL
    if name == "cloud":
        return GROQ_MODEL
    if name == "local":
        return "qwen2.5:1.5b"
    return ""


def _print_backend_status() -> list[dict[str, object]]:
    status = _backend_status()
    print("backend.status:")
    for item in status:
        ready = bool(item["enabled"] and item["configured"])
        print(
            f"- {item['name']}: ready={ready} enabled={item['enabled']} "
            f"configured={item['configured']} model={item['model'] or '<unset>'}"
        )
        if item["missing"]:
            print(f"  missing: {', '.join(item['missing'])}")
    print("")
    return status


def main() -> int:
    args = _parse_args()
    backend = build_llm_backend()
    route = backend.route

    print("route.primary =", backend.primary)
    print("route.fallback =", backend.fallback_chain)
    print("route.effective =", route)

    if args.dry_run:
        _print_backend_status()
        return 0

    if args.compare:
        return _compare_backends(
            backend=backend,
            question=args.question,
            system_prompt=args.system_prompt,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            thread_context=args.thread_context,
            require_all=args.require_all,
        )

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


def _compare_backends(
    *,
    backend,
    question: str,
    system_prompt: str,
    temperature: float,
    max_tokens: int,
    thread_context: str | None,
    require_all: bool,
) -> int:
    route = backend.route
    scores = []
    print("compare.route =", route)
    print("compare.question =", question)
    print("compare.thread_context =", thread_context or question)
    print("")
    status = _print_backend_status()
    unavailable = [item["name"] for item in status if not (item["enabled"] and item["configured"])]
    if require_all and unavailable:
        print("compare.error = missing required backend configuration")
        print("compare.unavailable =", ", ".join(unavailable))
        return 2

    for backend_name in ("meritocracy", "gonka", "mimo", "cloud", "local"):
        candidate = backend.backends.get(backend_name)
        if candidate is None:
            continue
        response = candidate.generate(
            messages=[{"role": "user", "content": question}],
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            metadata={"source": "scripts/test_llm_route.py", "backend": backend_name},
        )
        quality = evaluate_llm_answer_quality(
            question=question,
            answer=response.text or "",
            thread_context=thread_context or question,
        )
        scores.append((backend_name, response, quality))
        print(f"[{backend_name}] provider={response.provider} model={response.model}")
        print(f"[{backend_name}] ok={response.ok} latency_ms={round(float(response.latency_ms), 2)}")
        print(f"[{backend_name}] error={response.error}")
        print(
            f"[{backend_name}] quality="
            f"adequacy={quality.adequacy} "
            f"relevance={quality.relevance} "
            f"thread_relevance={quality.thread_relevance} "
            f"coherence={quality.coherence} "
            f"hallucination_risk={quality.hallucination_risk} "
            f"overall={quality.overall}"
        )
        print(f"[{backend_name}] notes={', '.join(quality.notes)}")
        print(f"[{backend_name}] quality.object=")
        print(json.dumps(quality.to_dict(), ensure_ascii=False, indent=2))
        meritocracy_info = (response.raw or {}).get("meritocracy") if isinstance(response.raw, dict) else None
        if meritocracy_info:
            print(f"[{backend_name}] meritocracy.selected_backend = {meritocracy_info.get('selected_backend')}")
            print(f"[{backend_name}] meritocracy.selected_model = {meritocracy_info.get('selected_model')}")
            print(f"[{backend_name}] meritocracy.selected_provider = {meritocracy_info.get('selected_provider')}")
        print(f"[{backend_name}] answer={response.text}")
        print("")

    if not scores:
        print("No backends available for comparison.")
        return 1

    ranked = sorted(scores, key=lambda item: item[2].overall, reverse=True)
    print("ranking:")
    for idx, (backend_name, response, quality) in enumerate(ranked, start=1):
        print(
            f"{idx}. {backend_name} | provider={response.provider} | model={response.model} | "
            f"overall={quality.overall} | relevance={quality.relevance} | "
            f"thread={quality.thread_relevance} | coherence={quality.coherence} | "
            f"hallucination_risk={quality.hallucination_risk}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
