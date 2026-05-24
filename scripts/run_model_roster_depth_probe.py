from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "python"
MODULES_DIR = PYTHON_DIR / "modules"
SCRIPTS_DIR = ROOT / "scripts"
for candidate in (str(PYTHON_DIR), str(MODULES_DIR), str(SCRIPTS_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)


from config import (  # noqa: E402
    GONKA_API_KEY,
    GONKA_ENABLED,
    GONKA_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_BACKEND,
    LLM_FALLBACK_BACKEND,
    LLM_LIGHT_MODEL,
    LLM_MODEL_NAME,
    MIMO_API_KEY,
    MIMO_ENABLED,
    MIMO_MODEL,
    OLLAMA_HOST,
    SYSTEM_PROMPT,
    TEMPERATURE,
)
from llm.backends.router import build_llm_backend  # noqa: E402
from modules.llm.quality import evaluate_llm_answer_quality  # noqa: E402
from run_pr_role_market_demo import AVAILABLE_ACTORS, ROLE_ACTOR_ASSIGNMENTS  # noqa: E402


METRIC_VERSION = "model_roster_depth_probe.v0.1"
DEFAULT_QUESTION = (
    "Explain the LS Depth Economy roles: executor 1+1=2, designer 1+1=3, "
    "customer-consumer 1+1=n. When should LS deepen a task?"
)
DEFAULT_THREAD_CONTEXT = (
    "LS Depth Economy: executor correctness, designer synergy, customer-consumer depth, "
    "Amygdala holds high-risk memory/action updates for human review."
)


def _ollama_tags(timeout_sec: float = 0.7) -> set[str]:
    url = f"{str(OLLAMA_HOST).rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=timeout_sec) as response:  # noqa: S310 - local Ollama probe only.
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return set()
    models = payload.get("models") if isinstance(payload, dict) else []
    names: set[str] = set()
    if isinstance(models, list):
        for item in models:
            if isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
    return names


def _ollama_status(model_name: str, tags: set[str]) -> dict[str, Any]:
    aliases = {model_name}
    if ":" not in model_name:
        aliases.add(f"{model_name}:latest")
    available = any(name == alias or name.startswith(f"{model_name}:") for name in tags for alias in aliases)
    if available:
        return {
            "runtime_status": "available",
            "ready_now": True,
            "missing": [],
            "probe": "ollama_tags",
        }
    if tags:
        return {
            "runtime_status": "not_installed",
            "ready_now": False,
            "missing": [model_name],
            "probe": "ollama_tags",
        }
    return {
        "runtime_status": "not_observed",
        "ready_now": False,
        "missing": ["ollama_tags_unavailable"],
        "probe": "ollama_tags",
    }


def _actor_runtime_status(actor_id: str, actor: dict[str, Any], ollama_models: set[str]) -> dict[str, Any]:
    model_name = str(actor.get("model_name") or "")
    if actor_id == "codex-self-use":
        return {
            "runtime_status": "manual_in_current_codex_session",
            "ready_now": True,
            "missing": [],
            "probe": "codex_session",
        }
    if actor_id == "human_operator":
        return {
            "runtime_status": "manual_review",
            "ready_now": True,
            "missing": [],
            "probe": "human_operator",
        }
    if actor.get("provider") == "ollama":
        return _ollama_status(model_name, ollama_models)
    if actor_id == "gonka":
        missing = []
        if not GONKA_ENABLED:
            missing.append("GONKA_ENABLED=true")
        if not GONKA_API_KEY:
            missing.append("GONKA_API_KEY")
        ready = not missing
        return {
            "runtime_status": "configured" if ready else "configured_disabled",
            "ready_now": ready,
            "missing": missing,
            "probe": "config",
        }
    if actor_id == "mimo":
        missing = []
        if not MIMO_ENABLED:
            missing.append("MIMO_ENABLED=true")
        if not MIMO_API_KEY:
            missing.append("MIMO_API_KEY")
        ready = not missing
        return {
            "runtime_status": "configured" if ready else "configured_disabled",
            "ready_now": ready,
            "missing": missing,
            "probe": "config",
        }
    return {
        "runtime_status": "unknown",
        "ready_now": False,
        "missing": ["runtime_probe_not_defined"],
        "probe": "none",
    }


def build_roster() -> list[dict[str, Any]]:
    ollama_models = _ollama_tags()
    roster = []
    for actor_id, actor in AVAILABLE_ACTORS.items():
        status = _actor_runtime_status(actor_id, actor, ollama_models)
        roster.append(
            {
                "actor_id": actor_id,
                "actor_type": actor.get("actor_type"),
                "provider": actor.get("provider"),
                "model_name": actor.get("model_name"),
                "execution_mode": actor.get("execution_mode"),
                "source": actor.get("source"),
                **status,
            }
        )
    return roster


def build_role_assignments() -> list[dict[str, Any]]:
    return [
        {
            "role": role,
            "actor_id": assignment["actor_id"],
            "reason": assignment["reason"],
        }
        for role, assignment in ROLE_ACTOR_ASSIGNMENTS.items()
    ]


def build_route_backend_status() -> list[dict[str, Any]]:
    return [
        {
            "backend": "gonka",
            "model_name": GONKA_MODEL,
            "ready_now": bool(GONKA_ENABLED and GONKA_API_KEY),
            "missing": [
                name
                for name, ok in (
                    ("GONKA_ENABLED=true", bool(GONKA_ENABLED)),
                    ("GONKA_API_KEY", bool(GONKA_API_KEY)),
                )
                if not ok
            ],
        },
        {
            "backend": "mimo",
            "model_name": MIMO_MODEL,
            "ready_now": bool(MIMO_ENABLED and MIMO_API_KEY),
            "missing": [
                name
                for name, ok in (
                    ("MIMO_ENABLED=true", bool(MIMO_ENABLED)),
                    ("MIMO_API_KEY", bool(MIMO_API_KEY)),
                )
                if not ok
            ],
        },
        {
            "backend": "cloud",
            "model_name": GROQ_MODEL,
            "ready_now": bool(GROQ_API_KEY),
            "missing": [] if GROQ_API_KEY else ["GROQ_API_KEY"],
        },
        {
            "backend": "local",
            "model_name": LLM_MODEL_NAME,
            "fallback_model_name": LLM_LIGHT_MODEL,
            "ready_now": True,
            "missing": [],
        },
    ]


def _live_probe(*, question: str, thread_context: str, max_tokens: int) -> dict[str, Any]:
    backend = build_llm_backend()
    response = backend.generate(
        messages=[{"role": "user", "content": question}],
        system_prompt=SYSTEM_PROMPT,
        temperature=TEMPERATURE,
        max_tokens=max_tokens,
        metadata={
            "source": "scripts/run_model_roster_depth_probe.py",
            "intent": "batch",
            "probe": METRIC_VERSION,
        },
    )
    quality = evaluate_llm_answer_quality(
        question=question,
        answer=response.text or "",
        thread_context=thread_context,
    )
    route_info = (response.raw or {}).get("route") if isinstance(response.raw, dict) else {}
    attempts = route_info.get("attempts") if isinstance(route_info, dict) else []
    return {
        "enabled": True,
        "question": question,
        "thread_context": thread_context,
        "route": {
            "primary": backend.primary,
            "fallback_chain": list(backend.fallback_chain),
            "effective": list(route_info.get("effective") or backend.route) if isinstance(route_info, dict) else backend.route,
            "attempts": attempts or [],
        },
        "response": {
            "ok": response.ok,
            "provider": response.provider,
            "model": response.model,
            "latency_ms": round(float(response.latency_ms), 2),
            "was_fallback_used": response.was_fallback_used,
            "fallback_from": response.fallback_from,
            "fallback_to": response.fallback_to,
            "error": response.error,
            "text": response.text,
        },
        "quality": quality.to_dict(),
    }


def build_probe_payload(
    *,
    live: bool = False,
    question: str = DEFAULT_QUESTION,
    thread_context: str = DEFAULT_THREAD_CONTEXT,
    max_tokens: int = 180,
) -> dict[str, Any]:
    roster = build_roster()
    live_result = (
        _live_probe(question=question, thread_context=thread_context, max_tokens=max_tokens)
        if live
        else {
            "enabled": False,
            "question": question,
            "thread_context": thread_context,
            "reason": "pass --live to call the configured LLM route",
        }
    )
    available_now = [item["actor_id"] for item in roster if item["ready_now"]]
    unavailable_now = [item["actor_id"] for item in roster if not item["ready_now"]]
    return {
        "demo": "ls_model_roster_depth_probe",
        "metric_version": METRIC_VERSION,
        "question": question,
        "thread_context": thread_context,
        "configured_route": {
            "LLM_BACKEND": LLM_BACKEND,
            "LLM_FALLBACK_BACKEND": LLM_FALLBACK_BACKEND,
            "backend_status": build_route_backend_status(),
        },
        "roster": roster,
        "role_actor_assignments": build_role_assignments(),
        "live_probe": live_result,
        "interpretation": {
            "available_now": available_now,
            "unavailable_now": unavailable_now,
            "current_boundary": (
                "The roster exists, but live multi-model testing requires configured Gonka/MiMo or cloud keys. "
                "Without them, LS can still test local routes and human/Codex review boundaries."
            ),
            "recommended_use_now": (
                "Use local Qwen for shallow L1 checks and keep L2-L4 Depth Economy decisions under Codex/human review "
                "until stronger configured backends are available."
            ),
        },
    }


def _print_text(payload: dict[str, Any]) -> None:
    print("LS model roster depth probe")
    print(f"Metric version: {payload['metric_version']}")
    print()
    print("Roster:")
    for item in payload["roster"]:
        ready = "ready" if item["ready_now"] else "not ready"
        print(f"- {item['actor_id']}: {item['provider']} / {item['model_name']} -> {ready} ({item['runtime_status']})")
        if item["missing"]:
            print(f"  missing: {', '.join(item['missing'])}")
    print()
    if payload["live_probe"]["enabled"]:
        probe = payload["live_probe"]
        response = probe["response"]
        quality = probe["quality"]
        print("Live route:")
        print(f"- provider/model: {response['provider']} / {response['model']}")
        print(f"- fallback: {response['was_fallback_used']} ({response['fallback_from']} -> {response['fallback_to']})")
        print(f"- quality overall: {quality['overall']} | thread: {quality['thread_relevance']}")
        print(f"- answer: {response['text']}")
    else:
        print("Live route: skipped; pass --live to call the configured backend route.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the LS model roster against the Depth Economy prompt.")
    parser.add_argument("--live", action="store_true", help="Call the configured LLM backend route.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--question", default=DEFAULT_QUESTION, help="Question to test.")
    parser.add_argument("--thread-context", default=DEFAULT_THREAD_CONTEXT, help="Thread context for quality scoring.")
    parser.add_argument("--max-tokens", type=int, default=180, help="Generation max tokens for --live.")
    args = parser.parse_args()

    payload = build_probe_payload(
        live=args.live,
        question=args.question,
        thread_context=args.thread_context,
        max_tokens=args.max_tokens,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
