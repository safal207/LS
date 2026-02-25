from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# Coherence smoothing constants (fallback defaults)
_DRIFT_NORMALIZATION = 0.30
_NOISE_NORMALIZATION = 0.08
_BASE_GAIN = 0.12
_DRIFT_GAIN_WEIGHT = 0.35
_NOISE_GAIN_WEIGHT = 0.20
_MIN_GAIN = 0.02
_MAX_GAIN = 0.95

DEFAULT_CAUSAL_CONFIDENCE = 0.92


try:
    from ..web4_runtime.fuzzy import smooth_coherence
except (ImportError, ValueError):
    def smooth_coherence(prev: float, measured: float, drift: float, noise: float) -> float:
        """Fallback coherence smoothing if web4_runtime is unavailable."""
        # Simplified adaptive gain matching web4_runtime.fuzzy logic
        drift_factor = min(1.0, abs(drift) / _DRIFT_NORMALIZATION)
        noise_factor = min(1.0, abs(noise) / _NOISE_NORMALIZATION)
        gain = _BASE_GAIN + (_DRIFT_GAIN_WEIGHT * drift_factor) + (_NOISE_GAIN_WEIGHT * noise_factor)
        gain = max(_MIN_GAIN, min(_MAX_GAIN, gain))
        return max(0.0, min(1.0, prev + gain * (measured - prev)))


def build_default_trace_payloads(
    question: str, thread_id: str, prev_coherence: float = 0.95
) -> tuple[dict, dict, dict]:
    """
    Dynamic payload builder for LTP/LRI metrics.
    Generates realistic metrics with a deterministic drifting seed (30-sec steps).
    Uses a local random instance to avoid side effects.
    """
    import random
    import time

    now = time.time()
    now_iso = datetime.fromtimestamp(now, tz=timezone.utc).isoformat()

    # Deterministic seed + smooth drift over time (every 30 seconds).
    # Note: In tests, this might cause slight seed shifts if executed across a 30s boundary,
    # but the derived coherence ranges in assertions are robust enough to handle this.
    base_seed = hash(str(thread_id)) + int(now / 30)
    rng = random.Random(base_seed)

    # Realistic metric ranges following Version 2.0 architect's refinement
    emotional_drift = round(rng.uniform(0.03, 0.47), 3)
    resonance_focus = round(rng.uniform(0.68, 0.97), 3)
    ltp_drift = round(rng.uniform(0.01, 0.25), 3)

    lri_core = {
        "invariants": ["non_reductive", "consent_first", "agency_preserved"],
        "emotional_drift": emotional_drift,
        "resonance_map": {"focus": resonance_focus},
        "stabilizer": "active" if rng.random() > 0.10 else "recovering",
    }

    # coherence is derived from emotional_drift (LRI) using smooth_coherence
    # we use measured_coherence=0.92 as a base for this trace
    coherence = smooth_coherence(prev_coherence, 0.92, drift=emotional_drift, noise=0.05)

    lce = {
        "v": 1,
        "intent": {"type": "answer", "goal": question},
        "affect": {"pad": [0.4, 0.2, 0.1], "tags": ["focused"]},
        "memory": {"thread": thread_id, "t": now_iso},
        "qos": {"coherence": coherence},
    }

    ltp_trace = {
        "thread_id": thread_id,
        "drift": ltp_drift,
        "admissible_futures": ["A", "B", "C"],
    }

    return lce, ltp_trace, lri_core


def get_causal_trace_confidence(
    get_registry_manager: Callable[[], Any | None],
    default: float = DEFAULT_CAUSAL_CONFIDENCE,
) -> float:
    reg = get_registry_manager()
    if reg is None:
        return default
    try:
        raw = reg.get_config("causal_trace_confidence")
        return float(raw or default)
    except (TypeError, ValueError, AttributeError):
        return default


def save_causal_trace(
    cause: str,
    solution: str,
    lce: dict,
    ltp_trace: dict,
    lri_core: dict,
    *,
    confidence: float = DEFAULT_CAUSAL_CONFIDENCE,
    get_registry_manager: Callable[[], object | None],
    save_to_codex: Callable[[dict], Optional[Path]],
) -> None:
    reg = get_registry_manager()
    if reg is None:
        return

    # Registry first — the single source of truth
    reg.save_causal_trace(cause, solution, lce, ltp_trace, lri_core, confidence)

    # Codex second — acts as a mirror/trace store
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

        ltp_trace = entry.get("ltp_trace") or {}
        drift = float(ltp_trace.get("drift", 0.0) or 0.0)

        lce = entry.get("lce") or {}
        qos = lce.get("qos") or {}
        coherence = float(qos.get("coherence", 0.0) or 0.0)

        lri_core = entry.get("lri_core") or {}
        emotional_drift = float(lri_core.get("emotional_drift", 0.0) or 0.0)
        stabilizer = lri_core.get("stabilizer", "—")
        resonance_map = lri_core.get("resonance_map") or {}
        resonance_focus = float(resonance_map.get("focus", 0.0) or 0.0)
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
