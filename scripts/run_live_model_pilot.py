from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = ROOT / "scripts"
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"
for path in (SCRIPTS_ROOT, PYTHON_ROOT, MODULES_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from modules.llm.quality import evaluate_llm_answer_quality  # noqa: E402
from run_model_roster_depth_probe import (  # noqa: E402
    DEFAULT_QUESTION,
    DEFAULT_THREAD_CONTEXT,
    AVAILABLE_ACTORS,
    build_probe_payload as build_roster_payload,
    build_multi_actor_probe_payload,
)
from run_network_trajectory_demo import (  # noqa: E402
    METRIC_VERSION as TRAJECTORY_METRIC_VERSION,
    build_demo_payload as build_trajectory_payload,
)

try:
    from ls.agent_shell.trail_network import TrailNetworkBridge  # noqa: E402
    _HAS_ROUTE_MEMORY = True
except ImportError:
    TrailNetworkBridge = None  # type: ignore[assignment]
    _HAS_ROUTE_MEMORY = False


METRIC_VERSION = "live_model_pilot.v0.2"
ROUTE_MEMORY_VERSION = "route_memory.v0"
SAMPLE_ANSWER = (
    "LS should deepen a task when the decision affects memory, action, trust, "
    "or repeated work. The executor checks correctness, the designer looks for "
    "synergy, the customer-consumer layer checks usefulness, and the conductor "
    "should hold the route for review when context or evidence is weak."
)


def _round(value: float) -> float:
    return round(float(value), 4)


def _ready_ratio(roster: list[dict[str, Any]]) -> float:
    if not roster:
        return 0.0
    ready = sum(1 for actor in roster if actor.get("ready_now"))
    return _round(ready / len(roster))


def _route_event_id(*, actor_id: str, question: str, answer: str, mode: str) -> str:
    digest = hashlib.sha256(
        f"{METRIC_VERSION}|{mode}|{actor_id}|{question}|{answer}".encode("utf-8")
    ).hexdigest()
    return f"e6-{digest[:16]}"


def _sample_response() -> dict[str, Any]:
    return {
        "ok": True,
        "provider": "sample",
        "model": "deterministic-sample",
        "latency_ms": 0.0,
        "was_fallback_used": False,
        "fallback_from": None,
        "fallback_to": None,
        "error": None,
        "text": SAMPLE_ANSWER,
    }


def _select_response(roster_payload: dict[str, Any], *, live: bool) -> tuple[str, dict[str, Any]]:
    live_probe = roster_payload.get("live_probe", {})
    if live and live_probe.get("enabled"):
        response = dict(live_probe.get("response") or {})
        actor_id = str(response.get("provider") or "configured-live-route")
        if response.get("model"):
            actor_id = f"{actor_id}:{response['model']}"
        return actor_id, response
    return "sample-deterministic-actor", _sample_response()


def _pilot_score(
    *,
    quality: dict[str, Any],
    readiness_ratio: float,
    trajectory_summary: dict[str, Any],
) -> float:
    return _round(
        0.42 * float(quality["overall"])
        + 0.18 * float(quality["thread_relevance"])
        + 0.18 * readiness_ratio
        + 0.22 * float(trajectory_summary["harmony_index"])
    )


def _decision(*, live: bool, response: dict[str, Any], pilot_score: float) -> str:
    if not live:
        return "sample_pipeline_ready"
    if not response.get("ok"):
        return "live_route_failed"
    if pilot_score >= 0.55:
        return "live_route_captured"
    return "live_route_needs_review"


def _question_hash(question: str, thread_context: str) -> str:
    return hashlib.sha256(f"{question}|{thread_context}".encode("utf-8")).hexdigest()[:12]


def _build_route_key(*, question: str, thread_context: str, actor_ids: list[str]) -> str:
    qh = _question_hash(question, thread_context)
    sorted_actors = sorted(a for a in actor_ids if a)
    return f"live_model_pilot/{qh}>{'>'.join(sorted_actors)}" if sorted_actors else f"live_model_pilot/{qh}"


def _persist_route_outcome(
    bridge: Any,
    *,
    route_key: str,
    question: str,
    actor_calls: list[dict[str, Any]],
    pilot_score: float,
    quality: dict[str, Any],
) -> bool:
    for call in actor_calls:
        actor_id = call.get("actor_id", "")
        role = call.get("role", "")
        resp = call.get("response", {})
        q = call.get("quality", {})
        if actor_id and role:
            try:
                bridge.submit_contribution({
                    "route_key": route_key,
                    "actor": actor_id,
                    "role": role,
                    "contribution_type": "agent_output",
                    "quality": q,
                    "note": f"live_model_pilot v0.2 | score={pilot_score}",
                })
            except Exception:
                return False
    try:
        outcome = bridge.record_outcome({
            "route_key": route_key,
            "task_text": question,
            "quality": quality,
            "graph_mode": "live_model_pilot",
            "selected_backend": "cooperative",
        })
        return outcome.get("status") in ("route_memory_updated",)
    except Exception:
        return False


def _lookup_existing_route(bridge: Any, *, route_key: str) -> dict[str, Any] | None:
    try:
        result = bridge.recommend_route({
            "task_type": route_key.split(">")[0] if ">" in route_key else "live_model_pilot",
            "available_backends": ["local", "gonka", "mimo"],
        })
        route_stats = result.get("route_stats", {})
        if route_stats and int(route_stats.get("runs", 0)) > 0:
            return route_stats
    except Exception:
        pass
    return None


def build_pilot_payload(
    *,
    live: bool = False,
    question: str = DEFAULT_QUESTION,
    thread_context: str = DEFAULT_THREAD_CONTEXT,
    cycles: int = 6,
    max_tokens: int = 180,
) -> dict[str, Any]:
    if cycles < 2:
        raise ValueError("cycles must be at least 2")

    roster_payload = build_roster_payload(
        live=live,
        question=question,
        thread_context=thread_context,
        max_tokens=max_tokens,
    )
    actor_id, response = _select_response(roster_payload, live=live)
    answer = str(response.get("text") or "")
    quality = evaluate_llm_answer_quality(
        question=question,
        answer=answer,
        thread_context=thread_context,
    ).to_dict()
    trajectory = build_trajectory_payload(cycles=cycles)
    readiness_ratio = _ready_ratio(roster_payload["roster"])

    bridge: Any = None
    route_key: str | None = None
    route_memory_used: bool = False
    route_memory_health: str | None = None
    durable_state_written: bool = False
    if live and _HAS_ROUTE_MEMORY:
        actor_ids = [item["actor_id"] for item in roster_payload["roster"] if item["ready_now"]]
        route_key = _build_route_key(question=question, thread_context=thread_context, actor_ids=actor_ids)
        bridge = TrailNetworkBridge()

    score = _pilot_score(
        quality=quality,
        readiness_ratio=readiness_ratio,
        trajectory_summary=trajectory["summary"],
    )
    decision = _decision(live=live, response=response, pilot_score=score)
    route_event = {
        "event_id": _route_event_id(
            actor_id=actor_id,
            question=question,
            answer=answer,
            mode="live" if live else "sample",
        ),
        "event_type": "e6_live_model_pilot",
        "actor_id": actor_id,
        "decision": decision,
        "pilot_precision_proxy": score,
        "route_key": route_key,
        "durable_state_written": durable_state_written,
        "external_action_allowed": False,
        "evidence": [
            {
                "kind": "answer_quality",
                "overall": quality["overall"],
                "thread_relevance": quality["thread_relevance"],
                "notes": quality["notes"],
            },
            {
                "kind": "roster_readiness",
                "ready_ratio": readiness_ratio,
                "ready_actors": roster_payload["interpretation"]["available_now"],
                "unavailable_actors": roster_payload["interpretation"]["unavailable_now"],
            },
            {
                "kind": "trajectory_context",
                "metric_version": trajectory["metric_version"],
                "conductor_decision": trajectory["summary"]["decision"],
                "harmony_index": trajectory["summary"]["harmony_index"],
                "conductor_velocity_multiplier": trajectory["summary"]["conductor_velocity_multiplier"],
            },
        ],
    }

    multi_actor = build_multi_actor_probe_payload(
        question=question,
        thread_context=thread_context,
        max_tokens=max_tokens,
    ) if live else None

    route_calls = multi_actor["actor_calls"] if multi_actor else []
    route_answered = [c for c in route_calls if c["response"]["ok"]]
    route_quality_scores = [c["quality"]["overall"] for c in route_answered if c.get("quality")]
    route_avg_quality = _round(sum(route_quality_scores) / len(route_quality_scores)) if route_quality_scores else 0.0
    route_best_quality = _round(max(route_quality_scores)) if route_quality_scores else 0.0
    route_won = route_best_quality > float(quality["overall"]) if route_quality_scores else None

    if bridge and route_key and route_won:
        durable_state_written = _persist_route_outcome(
            bridge,
            route_key=route_key,
            question=question,
            actor_calls=route_calls,
            pilot_score=score,
            quality=quality,
        )
        route_event["durable_state_written"] = durable_state_written
    if bridge and route_key and not route_won:
        existing = _lookup_existing_route(bridge, route_key=route_key)
        if existing:
            route_memory_used = True
            route_memory_health = existing.get("route_health")

    return {
        "demo": "ls_live_model_pilot",
        "metric_version": METRIC_VERSION,
        "mode": "live" if live else "sample",
        "interpretation_boundary": (
            "E6 Live Model Pilot captures one answer route against the LS roster, "
            "quality proxy, and conductor trajectory context. It is not model "
            "training, not a leaderboard, and not production safety evidence by itself."
        ),
        "task": {
            "question": question,
            "thread_context": thread_context,
        },
        "actor": {
            "actor_id": actor_id,
            "provider": response.get("provider"),
            "model": response.get("model"),
            "live_call": live,
        },
        "response": response,
        "quality": quality,
        "roster": {
            "metric_version": roster_payload["metric_version"],
            "ready_ratio": readiness_ratio,
            "ready_actors": roster_payload["interpretation"]["available_now"],
            "unavailable_actors": roster_payload["interpretation"]["unavailable_now"],
            "configured_route": roster_payload["configured_route"],
        },
        "multi_actor_route": {
            "enabled": live,
            "actors_probed": multi_actor["summary"]["actors_probed"] if multi_actor else 0,
            "actors_responded": multi_actor["summary"]["actors_responded"] if multi_actor else 0,
            "roles_assigned": multi_actor["summary"]["roles_assigned"] if multi_actor else [],
            "actor_calls": route_calls,
            "route_quality": {
                "average": route_avg_quality,
                "best": route_best_quality,
                "route_won_vs_single": route_won,
            },
        } if live else None,
        "network_context": {
            "trajectory_metric_version": TRAJECTORY_METRIC_VERSION,
            "cycles": trajectory["cycles"],
            "conductor_policy": trajectory["conductor_policy"],
            "summary": trajectory["summary"],
            "co_learning": trajectory.get("co_learning"),
        },
        "route_event": route_event,
        "route_memory": {
            "version": ROUTE_MEMORY_VERSION,
            "available": _HAS_ROUTE_MEMORY,
            "used": route_memory_used,
            "route_key": route_key,
            "durable_state_written": durable_state_written,
            "health": route_memory_health,
        },
        "summary": {
            "decision": decision,
            "pilot_precision_proxy": score,
            "answer_quality_overall": quality["overall"],
            "thread_relevance": quality["thread_relevance"],
            "ready_ratio": readiness_ratio,
            "conductor_harmony_index": trajectory["summary"]["harmony_index"],
            "route_won_vs_single": route_won,
            "route_best_quality": route_best_quality if route_quality_scores else None,
            "route_avg_quality": route_avg_quality if route_quality_scores else None,
            "route_memory_used": route_memory_used,
            "route_memory_health": route_memory_health,
            "next_step": (
                "Run with --live on a configured route and compare multiple actors."
                if not live
                else (
                    "Route persisted to route memory. Repeat the same task to test route recall."
                    if durable_state_written
                    else "Route results captured, but route memory requires TrailNetworkBridge."
                    if not _HAS_ROUTE_MEMORY
                    else "Route did not improve over single answer. Adjust actor roles or question."
                )
            ),
        },
    }


def _print_text(payload: dict[str, Any]) -> None:
    summary = payload["summary"]
    actor = payload["actor"]
    print("LS Live Model Pilot")
    print(f"Metric version: {payload['metric_version']}")
    print(f"Mode: {payload['mode']}")
    print(f"Decision: {summary['decision']}")
    print(f"Pilot precision proxy: {summary['pilot_precision_proxy']:.4f}")
    print(f"Actor: {actor['actor_id']} ({actor['provider']} / {actor['model']})")
    print(f"Quality overall: {summary['answer_quality_overall']:.4f}")
    print(f"Thread relevance: {summary['thread_relevance']:.4f}")
    print(f"Ready ratio: {summary['ready_ratio']:.4f}")
    print(f"Conductor harmony index: {summary['conductor_harmony_index']:.4f}")
    print(f"Route event: {payload['route_event']['event_id']}")
    rm = payload.get("route_memory", {})
    if rm.get("route_key"):
        print(f"Route key: {rm['route_key']}")
        if rm["durable_state_written"]:
            print("Route memory: persisted")
        elif rm["used"]:
            print(f"Route memory: existing route recalled (health: {rm['health']})")
    if summary["route_won_vs_single"] is not None:
        won = summary["route_won_vs_single"]
        print(f"Multi-actor route {'WON' if won else 'LOST'} vs single answer")
        print(f"  best route quality: {summary['route_best_quality']:.4f}")
        print(f"  avg route quality: {summary['route_avg_quality']:.4f}")
    print()
    print(payload["response"].get("text") or "<empty answer>")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the LS E6 live model pilot.")
    parser.add_argument("--live", action="store_true", help="Call the configured LLM backend route.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--thread-context", default=DEFAULT_THREAD_CONTEXT)
    parser.add_argument("--cycles", type=int, default=6)
    parser.add_argument("--max-tokens", type=int, default=180)
    args = parser.parse_args()

    payload = build_pilot_payload(
        live=args.live,
        question=args.question,
        thread_context=args.thread_context,
        cycles=args.cycles,
        max_tokens=args.max_tokens,
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
