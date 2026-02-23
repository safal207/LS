from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional


def build_default_trace_payloads(question: str, thread_id: str) -> tuple[dict, dict, dict]:
    """Stub payload builder until real LTP/LRI metrics are wired from runtime context."""
    now_iso = datetime.now(timezone.utc).isoformat()
    lce = {
        "v": 1,
        "intent": {"type": "answer", "goal": question},
        "affect": {"pad": [0.4, 0.2, 0.1], "tags": ["focused"]},
        "memory": {"thread": thread_id, "t": now_iso},
        "qos": {"coherence": 0.92},
    }
    ltp_trace = {
        "thread_id": thread_id,
        "drift": 0.08,
        "admissible_futures": ["A", "B"],
    }
    lri_core = {
        "invariants": ["non_reductive", "consent_first"],
        "emotional_drift": 0.12,
        "resonance_map": {"focus": 0.88},
        "stabilizer": "active",
    }
    return lce, ltp_trace, lri_core


def save_causal_trace(
    cause: str,
    solution: str,
    lce: dict,
    ltp_trace: dict,
    lri_core: dict,
    *,
    confidence: float = 0.92,
    get_registry_manager: Callable[[], object | None],
    save_to_codex: Callable[[dict], object],
) -> None:
    reg = get_registry_manager()
    if reg is None:
        return

    reg.save_causal_trace(cause, solution, lce, ltp_trace, lri_core, confidence)
    save_to_codex({
        **(lce if isinstance(lce, dict) else {}),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": "causal_trace",
        "cause": cause,
        "solution": solution,
        "ltp_trace": ltp_trace,
        "lri_core": lri_core,
        "confidence": confidence,
        "source": "registry::causal_memory",
    })


def replay_thread(thread_id: str, *, get_registry_manager: Callable[[], object | None]) -> list:
    reg = get_registry_manager()
    if reg is None:
        return []
    try:
        result = reg.replay_thread(thread_id)
        return result if isinstance(result, list) else []
    except Exception:
        return []


def extract_replay_thread_id(user_input: str) -> Optional[str]:
    for raw in user_input.split():
        token = raw.strip().strip(".,!?;:()[]{}<>\"'")
        lower = token.lower()
        if lower.startswith("thread-") and len(token) > 7:
            return token
        if lower.startswith("test-") and len(token) > 5:
            return token
    return None


def replay_thread_ui(thread_id: str, *, replay_loader: Callable[[str], list]) -> str:
    trace = replay_loader(thread_id)
    if not trace:
        return f"❌ Тред {thread_id} не найден."

    output = [f"🔄 Replay тред **{thread_id}** ({len(trace)} записей):"]
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        ts = entry.get("ts", "—")
        cause = str(entry.get("cause", "—"))[:80]
        solution = str(entry.get("solution", "—"))[:80]
        drift = float(entry.get("ltp_trace", {}).get("drift", 0.0) or 0.0)
        coherence = float(entry.get("lce", {}).get("qos", {}).get("coherence", 0.0) or 0.0)
        lri_core = entry.get("lri_core", {}) if isinstance(entry.get("lri_core", {}), dict) else {}
        emotional_drift = float(lri_core.get("emotional_drift", 0.0) or 0.0)
        stabilizer = lri_core.get("stabilizer", "—")
        resonance_focus = float(lri_core.get("resonance_map", {}).get("focus", 0.0) or 0.0)
        invariants = lri_core.get("invariants", [])
        inv_preview = ", ".join(str(v) for v in invariants[:2]) if isinstance(invariants, list) else "—"
        output.append(f"• {ts} | drift:{drift:.2f} | emo_drift:{emotional_drift:.2f} | coherence:{coherence:.2f}")
        output.append(f"  LRI: stabilizer={stabilizer} | resonance.focus={resonance_focus:.2f} | invariants={inv_preview}")
        output.append(f"  Причина: {cause}")
        output.append(f"  Решение: {solution}\n")
    return "\n".join(output)


def handle_replay_command(user_input: str, *, replay_ui_renderer: Callable[[str], str]) -> Optional[str]:
    lower = user_input.lower()
    if "replay" not in lower and "переиграй" not in lower:
        return None

    thread_id = extract_replay_thread_id(user_input)
    if thread_id is None:
        return None
    return replay_ui_renderer(thread_id)
