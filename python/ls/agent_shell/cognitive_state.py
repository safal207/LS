from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Phase 2.4 — bilingual emotional intent detection
#
# Two separate concerns are handled here:
#
#   _is_emotional_question()  — TOPIC routing
#       "Is this question about relationship, bond, closeness, trust?"
#       Negation and hesitation do NOT suppress intent.
#       "Ты не чувствуешь связь?" and "Почему нет близости?" are
#       still relational questions — the negation is part of the framing,
#       not evidence that the topic is something else.
#
#   _feedback_matches()  — SENTIMENT / polarity matching (in emotional_memory.py)
#       "Is this feedback positive / distressed / frustrated?"
#       Negation guard IS appropriate here: "not good" ≠ positive signal.
# ──────────────────────────────────────────────────────────────

# Relational topic keywords — EN
# Intentionally excludes high-false-positive generics: "care", "together",
# "moments", "important" — these appear in non-relational technical queries.
# "togetherness" and "caring" (more specific forms) are kept.
_EMOTIONAL_KEYWORDS_EN = frozenset({
    "feel", "feeling", "feelings", "felt", "emotion", "emotional",
    "bond", "bonding", "connection", "connected", "connect",
    "warm", "warmth", "close", "closer", "closeness",
    "relationship", "relate", "trust", "togetherness",
    "caring", "distance", "apart",
})

# Relational topic keywords — RU
_EMOTIONAL_KEYWORDS_RU = frozenset({
    # feel / sense
    "чувствую", "чувствуешь", "чувствуем", "чувствовать", "чувствуется",
    "ощущаю", "ощущаешь", "ощущение",
    "эмоции", "эмоций", "эмоциональный",
    # bond / connection / relationship
    "связь", "связи", "связью", "связан", "связаны",
    "отношения", "отношений", "отношениях", "отношению",
    "близость", "близки", "близко", "близкий", "близости",
    "дистанцию", "дистанция", "расстояние",
    # warmth / temperature of relation
    "тепло", "теплее", "тёплый", "теплый", "тепла",
    "холодно", "холоднее", "отдалились",
    # trust / together
    "доверие", "доверия", "доверяешь", "доверяю", "доверяем",
    "вместе", "общение", "понимание", "понимаешь",
    # moments / important
    "моменты", "момент", "моментов", "моментами",
    "важные", "важный", "важным", "важно", "значимый",
    # care
    "забота", "заботу", "заботишься",
})

# Conversational discourse markers — safe hesitation fillers / interjections only.
# These are stripped before keyword matching so they never block topic routing.
#
# IMPORTANT: only include words that are purely pragmatic (hesitation, hedging)
# and carry NO topic-bearing meaning on their own. Words like "feel", "like",
# "kind", "sort", "как" must NOT be here — they are too often part of the
# sentence's actual meaning (e.g. "How do you feel?", "Как ты ощущаешь связь?").
_DISCOURSE_MARKERS = frozenset({
    # EN — pure hesitation / hedge markers
    "hmm", "hm", "um", "uh", "well", "maybe", "perhaps",
    # RU — interjections, fillers, softeners
    "хм", "мм", "эм", "э", "ну", "ну-ну", "слушай",
    "будто", "как будто", "вроде", "вроде бы", "что ли",
    "мне кажется", "кажется", "наверное", "может", "может быть",
    "типа", "так сказать",
})

# Relational speech patterns — question templates that signal emotional intent
# regardless of whether they contain a direct keyword.
# Each is a substring fragment (after lowercasing + stripping).
_RELATIONAL_PATTERNS_RU = (
    "между нами",      # "что-то между нами изменилось"
    "между нас",
    "ты и я",
    "мы с тобой",
    "наши отношения",
    "наша связь",
    "наше общение",
    "стали ближе",
    "стали дальше",
    "стало теплее",
    "стало холоднее",
    "нет близости",
    "нет доверия",
    "нет связи",
    "нет понимания",
)

_RELATIONAL_PATTERNS_EN = (
    "between us",
    "you and i",
    "our bond",
    "our connection",
    "our relationship",
    "grown closer",
    "grown apart",
    "feel connected",
    "no trust",
    "no connection",
    "no closeness",
)


def _normalise_for_topic(text: str) -> str:
    """Lowercase, strip punctuation, remove discourse markers, collapse whitespace.

    Discourse markers (хм, эм, ну, well, um…) are stripped from the token
    stream so they never block keyword matching — their presence signals
    intimate framing but the topic may still be relational.
    """
    lowered = text.lower()
    # Remove common punctuation
    cleaned = re.sub(r"[.,!?:;\"'«»()\-–—]+", " ", lowered)
    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    # Strip multi-word discourse markers first (longest first to avoid partial overlaps)
    for marker in sorted((m for m in _DISCOURSE_MARKERS if " " in m), key=len, reverse=True):
        collapsed = collapsed.replace(marker, " ")
    collapsed = re.sub(r"\s+", " ", collapsed).strip()
    # Strip single-word discourse markers at token level
    tokens = [t for t in collapsed.split() if t not in _DISCOURSE_MARKERS]
    return " ".join(tokens)


def _detect_language(text: str) -> str:
    """Return 'ru' if *text* contains Cyrillic characters, else 'en'."""
    return "ru" if re.search(r"[а-яёА-ЯЁ]", text) else "en"


# Localized tone names for Russian-language responses.
_TONE_NAMES_RU: dict[str, str] = {
    "warm": "тёплый",
    "calm": "спокойный",
    "reflective": "рефлексивный",
    "joyful": "радостный",
    "supportive": "поддерживающий",
    "tense": "напряжённый",
    "frustrated": "разочарованный",
    "anxious": "тревожный",
    "uncertain": "неопределённый",
    "neutral": "нейтральный",
}


def _is_emotional_question(text: str) -> bool:
    """Return True when the text is about a relational/emotional topic (EN or RU).

    Routing decision only — does not evaluate sentiment polarity.
    Negation (не, нет, not, no) does NOT suppress this check:

        "Ты не чувствуешь связь?"      → True  (topic: bond)
        "Почему между нами нет близости?" → True  (pattern: между нами + нет близости)
        "Хм, наша связь стала теплее?"  → True  (interjection stripped; keyword: связь)
        "How coherent am I?"            → False (no relational topic)
    """
    normalised = _normalise_for_topic(text)

    # 1. Direct keyword match (negation-agnostic for topic routing)
    for token in normalised.split():
        if token in _EMOTIONAL_KEYWORDS_EN or token in _EMOTIONAL_KEYWORDS_RU:
            return True

    # 2. Relational speech pattern match
    for pattern in _RELATIONAL_PATTERNS_RU:
        if pattern in normalised:
            return True
    for pattern in _RELATIONAL_PATTERNS_EN:
        if pattern in normalised:
            return True

    return False


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CognitiveStateBridge:
    """Read-only aggregation over LS cognitive state for MCP exposure."""

    def __init__(self, *, task_manager: Any) -> None:
        self._store_path = Path(
            os.environ.get("GRAPH_MEMORY_STORE_PATH", "data/graph_memory/cases.jsonl")
        )
        self._task_manager = task_manager
        self._cached_store: Any = None  # lazily initialised by _get_store()

    def _get_store(self) -> Any:
        """Return a cached ``MemoryGraphStore`` for this bridge's path.

        Emotional-memory methods share one store instance rather than
        constructing a new one per call.  The process-wide ``RLock``
        (keyed by resolved path) still protects concurrent access.
        """
        from modules.graph.memory_store import MemoryGraphStore
        if self._cached_store is None:
            self._cached_store = MemoryGraphStore(self._store_path)
        return self._cached_store

    def get_resonance_snapshot(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        safe_top_k = max(1, int(top_k or 1))
        safe_threshold = float(min_resonance_score)
        units = self._runtime_resonance_snapshot(
            top_k=safe_top_k,
            min_resonance_score=safe_threshold,
        )
        if units is None:
            units = self._file_resonance_snapshot(
                top_k=safe_top_k,
                min_resonance_score=safe_threshold,
            )
        return {
            "resource": "resonance/snapshot",
            "top_k": safe_top_k,
            "min_resonance_score": safe_threshold,
            "items": units,
            "last_updated": _utc_now(),
        }

    def get_cognitive_state(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        """Backward-compatible aggregate cognitive state payload for MCP tools."""
        resonance_snapshot = self.get_resonance_snapshot(
            top_k=top_k,
            min_resonance_score=min_resonance_score,
        )
        relational_state = self.get_relational_state(
            top_k=top_k,
            min_resonance_score=min_resonance_score,
        )
        alignment = self.get_alignment_current()
        omni = self.get_omni_last_insight()
        return {
            "resource": "cognitive/state",
            # Backward-compatible keys (legacy aggregate contract)
            "resonance": resonance_snapshot,
            "alignment": alignment,
            "omni": omni,
            # Additive keys (new contract)
            "resonance_snapshot": resonance_snapshot,
            "relational_state": relational_state,
            "last_updated": _utc_now(),
        }

    def _runtime_resonance_snapshot(
        self,
        *,
        top_k: int,
        min_resonance_score: float,
    ) -> list[dict[str, Any]] | None:
        if not hasattr(self._task_manager, "get_resonance_snapshot"):
            return None
        try:
            rows = self._task_manager.get_resonance_snapshot(
                top_k=top_k,
                min_resonance_score=min_resonance_score,
            )
        except Exception:
            logger.debug("Runtime resonance snapshot failed", exc_info=True)
            return None

        payload: list[dict[str, Any]] = []
        for row in rows or []:
            if hasattr(row, "to_dict"):
                payload.append(dict(row.to_dict()))
            elif isinstance(row, dict):
                payload.append(dict(row))
            else:
                payload.append({"value": row})
        return payload

    def _file_resonance_snapshot(
        self,
        *,
        top_k: int,
        min_resonance_score: float,
    ) -> list[dict[str, Any]]:
        path = self._store_path.with_name("resonance_units.jsonl")
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = line.strip()
                if not row:
                    continue
                try:
                    payload = dict(json.loads(row))
                except Exception:
                    logger.debug("Skipping malformed resonance JSONL row")
                    continue
                if float(payload.get("resonance_score", 0.0) or 0.0) < min_resonance_score:
                    continue
                items.append(payload)
        items.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
        return items[:top_k]

    def get_alignment_current(self) -> dict[str, Any]:
        if hasattr(self._task_manager, "get_alignment_current"):
            payload = dict(self._task_manager.get_alignment_current())
        else:
            payload = {
                "alignment_state": "unavailable",
                "outcomes": [],
                "softening_detected": False,
                "reason": "Alignment provider is not bound in the current runtime.",
            }

        payload["resource"] = "alignment/current"
        payload.setdefault("last_updated", _utc_now())
        return payload

    def get_omni_last_insight(self) -> dict[str, Any]:
        enabled = str(os.environ.get("QWEN_OMNI_ENABLED", "0")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if not enabled:
            return {
                "resource": "omni/last-insight",
                "enabled": False,
                "insight": None,
                "reason": "QWEN_OMNI_ENABLED is off",
                "last_updated": _utc_now(),
            }

        insight: dict[str, Any] | None = None
        if hasattr(self._task_manager, "get_omni_last_insight"):
            try:
                raw = self._task_manager.get_omni_last_insight()
                insight = dict(raw) if raw else None
            except Exception:
                logger.debug("Runtime omni insight lookup failed", exc_info=True)

        return {
            "resource": "omni/last-insight",
            "enabled": True,
            "insight": insight,
            "last_updated": _utc_now(),
        }

    def get_relational_self_summary(self) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        snapshot = store.get_relational_self().to_dict()
        return {
            "resource": "self/relational-self",
            "snapshot": snapshot,
            "last_updated": _utc_now(),
        }

    def get_coherence_history(self, *, limit: int = 30) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        rows = store.get_coherence_history(limit=int(limit))
        return {
            "resource": "self/coherence-history",
            "items": rows,
            "limit": int(limit),
            "last_updated": _utc_now(),
        }

    def get_constitution_status(self, *, limit: int = 20) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        rows = store.get_constitution_history(limit=int(limit))
        latest = rows[-1] if rows else None
        latest_self = store.get_relational_self()
        latest_action_rows = store.get_council_action_history(limit=1)
        last_action = latest_action_rows[-1] if latest_action_rows else None
        passed = bool((latest or {}).get("constitution", {}).get("passed", True)) if latest else True
        blocked = bool((latest or {}).get("blocked", False)) if latest else False
        coherence = float(latest_self.self_coherence_score or 0.0)
        if (not passed) or blocked:
            identity_state = "at-risk"
            breach_risk = "high"
        elif coherence < 0.65:
            identity_state = "drifting"
            breach_risk = "medium"
        else:
            identity_state = "stable"
            breach_risk = "low"
        if last_action is None:
            last_action_effect = "none"
        else:
            last_action_effect = self._action_effect(last_action)
        return {
            "resource": "self/constitution-status",
            "latest": latest,
            "items": rows,
            "limit": int(limit),
            "identity_state": identity_state,
            "breach_risk": breach_risk,
            "last_action_effect": last_action_effect,
            "last_updated": _utc_now(),
        }

    def get_self_metrics(self, *, window: int = 100) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        metrics = store.get_self_metrics_snapshot(window=int(window))
        return {
            "resource": "self/metrics",
            "metrics": metrics,
            "last_updated": _utc_now(),
        }

    def get_action_history(self, *, limit: int = 30) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        items = store.get_council_action_history(limit=int(limit))
        return {
            "resource": "self/action-history",
            "items": items,
            "limit": int(limit),
            "last_updated": _utc_now(),
        }

    def get_shared_self_current(self) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        shared = store.get_shared_relational_self().to_dict()
        return {
            "resource": "shared-self/current",
            "snapshot": shared,
            "fellowship_registry": store.get_fellowship_registry(),
            "last_updated": _utc_now(),
        }

    def get_emotional_continuity(self) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        payload = store.get_emotional_continuity_state()
        payload["resource"] = "self/emotional-continuity"
        payload["last_updated"] = _utc_now()
        return payload

    def get_live_council_state(self, *, session_id: str) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        payload = store.get_live_council_state()
        if session_id:
            payload["session_id"] = session_id
        payload["resource"] = "council/live"
        payload["last_updated"] = _utc_now()
        return payload

    def propose_shared_insight(
        self,
        *,
        recipient: str,
        source_node_id: str,
        target_node_id: str,
        relation_type: str = "reinforces",
        strength: float = 0.5,
        rationale: str = "",
    ) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        proposal = store.propose_shared_insight(
            recipient=str(recipient or ""),
            source_node_id=str(source_node_id or ""),
            target_node_id=str(target_node_id or ""),
            relation_type=str(relation_type or "reinforces"),
            strength=float(strength),
            rationale=str(rationale or ""),
        )
        return {
            "resource": "shared-self/proposal",
            "proposal": proposal,
            "last_updated": _utc_now(),
        }

    def accept_shared_self(
        self,
        shared_payload: dict[str, Any],
        *,
        selective_merge: bool = True,
    ) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        accepted = store.accept_shared_self(
            shared_payload=dict(shared_payload or {}),
            selective_merge=bool(selective_merge),
        )
        accepted["resource"] = "shared-self/accept"
        accepted["last_updated"] = _utc_now()
        return accepted

    def rollback_self_action(self, *, action_id: str) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        result = store.rollback_council_action(action_id=str(action_id))
        result["resource"] = "self/rollback-action"
        result["last_updated"] = _utc_now()
        return result

    def ask_self(self, question: str) -> dict[str, Any]:
        from modules.graph.memory_store import MemoryGraphStore

        prompt = str(question or "").strip()
        store = MemoryGraphStore(self._store_path)
        snapshot = store.get_relational_self()
        days = 3
        match = re.search(r"(\d+)", prompt)
        if match:
            days = max(1, int(match.group(1)))
        history = store.get_coherence_history(limit=max(10, days * 12))
        if history:
            now = datetime.now(timezone.utc)
            filtered: list[dict[str, Any]] = []
            for row in history:
                timestamp = str(row.get("timestamp") or "")
                try:
                    row_dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if (now - row_dt).total_seconds() <= days * 86400:
                    filtered.append(row)
            if filtered:
                history = filtered
        delta = 0.0
        if len(history) >= 2:
            delta = float(history[-1].get("coherence_score", 0.0) or 0.0) - float(
                history[0].get("coherence_score", 0.0) or 0.0
            )
        direction = "stabilized"
        if delta > 0.02:
            direction = "grew more coherent"
        elif delta < -0.02:
            direction = "lost coherence"

        top_drivers = sorted(
            list(snapshot.change_history or []),
            key=lambda row: abs(float(row.get("delta", 0.0) or 0.0)),
            reverse=True,
        )[:3]
        driver_summary = [
            {
                "cycle_id": row.get("cycle_id"),
                "delta": float(row.get("delta", 0.0) or 0.0),
                "source": row.get("source"),
            }
            for row in top_drivers
        ]
        constitution_rows = store.get_constitution_history(limit=10)
        action_rows = store.get_council_action_history(limit=10)
        causal_trace: list[dict[str, Any]] = []
        prev_node_id: str | None = None
        for row in history[-3:]:
            node_id = f"coherence:{row.get('cycle_id') or row.get('timestamp')}"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "coherence_event",
                    "timestamp": row.get("timestamp"),
                    "coherence_score": row.get("coherence_score"),
                    "cycle_id": row.get("cycle_id"),
                    "confidence": 0.85,
                    "linked_from": prev_node_id,
                }
            )
            prev_node_id = node_id
        if driver_summary:
            node_id = "relation_shift:top_drivers"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "relation_shift",
                    "drivers": driver_summary,
                    "confidence": 0.78,
                    "linked_from": prev_node_id,
                }
            )
            prev_node_id = node_id
        if constitution_rows:
            latest_const = constitution_rows[-1]
            node_id = f"policy:{latest_const.get('cycle_id') or 'latest'}"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "constitution_state",
                    "cycle_id": latest_const.get("cycle_id"),
                    "passed": bool((latest_const.get("constitution") or {}).get("passed", True)),
                    "blocked": bool(latest_const.get("blocked", False)),
                    "policy_decision": dict(latest_const.get("policy_decision") or {}),
                    "confidence": 0.9,
                    "linked_from": prev_node_id,
                }
            )
            prev_node_id = node_id
        if action_rows:
            latest_action = action_rows[-1]
            action_effect = self._action_effect(latest_action)
            node_id = f"action:{latest_action.get('action_id') or 'latest'}"
            causal_trace.append(
                {
                    "node_id": node_id,
                    "type": "applied_action",
                    "action_id": latest_action.get("action_id"),
                    "action": latest_action.get("action"),
                    "rolled_back": bool(latest_action.get("rolled_back", False)),
                    "partially_rolled_back": bool(latest_action.get("partially_rolled_back", False)),
                    "rollback_scope": latest_action.get("rollback_scope"),
                    "action_effect": action_effect,
                    "confidence": 0.88,
                    "linked_from": prev_node_id,
                }
            )

        # ── Phase 2.4: emotional layer ───────────────────────────────
        emotional_summary = dict(snapshot.emotional_summary or {})
        dominant_tone = str(emotional_summary.get("dominant_tone") or "neutral")
        bond_strength = float(emotional_summary.get("bond_strength") or 0.0)
        bond_trend = str(emotional_summary.get("bond_trend") or "stable")
        em_confidence = float(emotional_summary.get("confidence") or 0.0)
        notable_moments = list(emotional_summary.get("notable_moments") or [])

        # Detect emotionally-framed questions (EN + RU) + prompt language
        is_emotional_question = _is_emotional_question(prompt)
        lang = _detect_language(prompt)

        # Append emotional nodes to causal_trace
        if causal_trace:
            prev_node_id = causal_trace[-1].get("node_id")
        else:
            prev_node_id = None

        emotional_entries = store.get_emotional_memory(limit=5)
        for entry in emotional_entries[-2:]:
            em_node_id = f"emotional_event:{entry.get('entry_id') or entry.get('timestamp')}"
            causal_trace.append({
                "node_id": em_node_id,
                "type": "emotional_event",
                "timestamp": entry.get("timestamp"),
                "emotional_tone": entry.get("emotional_tone"),
                "valence": entry.get("valence"),
                "confidence": entry.get("confidence"),
                "trigger_source": entry.get("trigger_source"),
                "linked_from": prev_node_id,
            })
            prev_node_id = em_node_id

        arc_points = store.get_emotional_arc(limit=10)
        if len(arc_points) >= 2:
            node_id = "bond_shift:recent"
            first_bond = float((arc_points[0].get("bond_strength") or 0.0))
            last_bond = float((arc_points[-1].get("bond_strength") or 0.0))
            causal_trace.append({
                "node_id": node_id,
                "type": "bond_shift",
                "bond_strength": bond_strength,
                "bond_trend": bond_trend,
                "bond_delta": round(last_bond - first_bond, 4),
                "arc_length": len(arc_points),
                "confidence": round(em_confidence, 4),
                "linked_from": prev_node_id,
            })
            prev_node_id = node_id

        em_summary_node = "emotional_summary_state:current"
        causal_trace.append({
            "node_id": em_summary_node,
            "type": "emotional_summary_state",
            "dominant_tone": dominant_tone,
            "bond_strength": bond_strength,
            "bond_trend": bond_trend,
            "confidence": em_confidence,
            "linked_from": prev_node_id,
        })

        # Build answer — bilingual, incorporating emotional layer when relevant
        coherence_val = float(snapshot.self_coherence_score or 0.0)
        if lang == "ru":
            # Derive RU text directly from delta — no dependency on EN direction string.
            if delta > 0.02:
                _dir_ru = "стала более согласованной"
            elif delta < -0.02:
                _dir_ru = "потеряла согласованность"
            else:
                _dir_ru = "стабилизировалась"
            base_answer = (
                f"За последние {days} дн. я {_dir_ru}. "
                f"Текущий уровень согласованности: {coherence_val:.2f}."
            )
        else:
            base_answer = (
                f"Over the last {days} day(s) I {direction}. "
                f"Current coherence is {coherence_val:.2f}."
            )

        if is_emotional_question and emotional_summary:
            if lang == "ru":
                _trend_ru = {
                    "warming": "теплеет и укрепляется",
                    "cooling": "охлаждается",
                    "volatile": "нестабилен",
                    "stable": "стабилен",
                }.get(bond_trend, bond_trend)
                _tone_ru = _TONE_NAMES_RU.get(dominant_tone, dominant_tone)
                emotional_answer = (
                    f" Выявленный сигнал связи {_trend_ru} "
                    f"(сила связи {bond_strength:.2f}, преобладающий тон: {_tone_ru})."
                )
                if notable_moments:
                    emotional_answer += (
                        f" Примечательный момент: «{notable_moments[0].get('summary', '')}»."
                    )
            else:
                _trend_en = {
                    "warming": "growing warmer",
                    "cooling": "cooling",
                    "volatile": "fluctuating",
                    "stable": "stable",
                }.get(bond_trend, bond_trend)
                emotional_answer = (
                    f" The inferred relational bond signal is {_trend_en} "
                    f"(bond strength {bond_strength:.2f}, dominant tone: {dominant_tone})."
                )
                if notable_moments:
                    emotional_answer += (
                        f" A notable moment: \"{notable_moments[0].get('summary', '')}\"."
                    )
            answer_text = base_answer + emotional_answer
        else:
            answer_text = base_answer

        return {
            "resource": "self/ask-self",
            "question": prompt,
            "answer": answer_text,
            "coherence_delta": round(delta, 4),
            "coherence_now": float(snapshot.self_coherence_score or 0.0),
            "top_change_drivers": driver_summary,
            "emotional_layer": emotional_summary,
            "causal_trace": causal_trace,
            "last_updated": _utc_now(),
        }

    @staticmethod
    def _action_effect(action_row: dict[str, Any]) -> str:
        if bool(action_row.get("partially_rolled_back", False)) or str(action_row.get("rollback_scope") or "") == "partial":
            return "partially_reverted"
        if bool(action_row.get("rolled_back", False)):
            return "reverted"
        return "applied"

    def get_relational_graph(
        self,
        unit_id: str,
        depth: int = 2,
    ) -> dict[str, Any]:
        """Return a BFS relational subgraph centred on *unit_id*.

        Reads directly from the JSONL store so the result is always current
        even when the runtime hasn't exposed a live accessor.
        """
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        graph = store.get_relational_graph(unit_id=str(unit_id), depth=int(depth))
        graph["resource"] = "resonance/relational-graph"
        graph["last_updated"] = _utc_now()
        return graph

    def get_relational_state(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> dict[str, Any]:
        """Combined snapshot: top resonance units plus their relational edges."""
        from modules.graph.memory_store import MemoryGraphStore

        store = MemoryGraphStore(self._store_path)
        items = store.get_resonance_with_relations(
            top_k=int(top_k),
            min_resonance_score=float(min_resonance_score),
        )
        return {
            "resource": "cognitive/relational-state",
            "top_k": int(top_k),
            "min_resonance_score": float(min_resonance_score),
            "items": items,
            "last_updated": _utc_now(),
        }

    def ask_relational_question(
        self,
        *,
        source_unit_id: str,
        target_unit_id: str,
    ) -> dict[str, Any]:
        """Explain why two units are connected, if an edge exists."""
        from modules.graph.memory_store import MemoryGraphStore

        source_id = str(source_unit_id or "")
        target_id = str(target_unit_id or "")
        store = MemoryGraphStore(self._store_path)
        graph = store.get_relational_graph(source_id, depth=1)
        direct_edge = next(
            (
                edge
                for edge in list(graph.get("edges") or [])
                if str(edge.get("source") or "") == source_id
                and str(edge.get("target") or "") == target_id
            ),
            None,
        )
        if direct_edge is None:
            reverse_graph = store.get_relational_graph(target_id, depth=1)
            reverse_edge = next(
                (
                    edge
                    for edge in list(reverse_graph.get("edges") or [])
                    if str(edge.get("source") or "") == target_id
                    and str(edge.get("target") or "") == source_id
                ),
                None,
            )
            if reverse_edge is not None:
                return {
                    "resource": "cognitive/relational-why",
                    "linked": True,
                    "direction": "reverse",
                    "source_unit_id": source_id,
                    "target_unit_id": target_id,
                    "relation_type": str(reverse_edge.get("relation_type") or "unknown"),
                    "strength": float(reverse_edge.get("strength", 0.0) or 0.0),
                    "explanation": "Units are connected, but the stored edge points in the reverse direction.",
                    "last_updated": _utc_now(),
                }
            return {
                "resource": "cognitive/relational-why",
                "linked": False,
                "source_unit_id": source_id,
                "target_unit_id": target_id,
                "explanation": "No direct relation edge is currently stored between these units.",
                "last_updated": _utc_now(),
            }

        relation_type = str(direct_edge.get("relation_type") or "unknown")
        strength = float(direct_edge.get("strength", 0.0) or 0.0)
        return {
            "resource": "cognitive/relational-why",
            "linked": True,
            "direction": "forward",
            "source_unit_id": source_id,
            "target_unit_id": target_id,
            "relation_type": relation_type,
            "strength": strength,
            "explanation": (
                f"Stored edge indicates '{relation_type}' with strength {strength:.2f} "
                "from source to target."
            ),
            "last_updated": _utc_now(),
        }

    def suggest_new_relation(
        self,
        *,
        source_unit_id: str,
        target_unit_id: str,
        relation_type: str = "reinforces",
        strength: float = 0.5,
        rationale: str | None = None,
    ) -> dict[str, Any]:
        """Create a human-suggested relation edge (idempotent by target+type)."""
        from modules.graph.memory_store import MemoryGraphStore
        from modules.graph.models import RelationalEdge

        source_id = str(source_unit_id or "")
        target_id = str(target_unit_id or "")
        store = MemoryGraphStore(self._store_path)
        source_unit = next(
            (unit for unit in store.list_resonance_units() if unit.unit_id == source_id),
            None,
        )
        if source_unit is None:
            return {
                "resource": "cognitive/relational-suggestion",
                "accepted": False,
                "reason": "source_not_found",
                "source_unit_id": source_id,
                "target_unit_id": target_id,
                "last_updated": _utc_now(),
            }
        existing = next(
            (
                rel
                for rel in list(source_unit.relations or [])
                if isinstance(rel, dict)
                and str(rel.get("target_unit_id") or "") == target_id
                and str(rel.get("relation_type") or "") == str(relation_type or "reinforces")
            ),
            None,
        )
        if existing is not None:
            return {
                "resource": "cognitive/relational-suggestion",
                "accepted": True,
                "created": False,
                "reason": "duplicate_existing_relation",
                "edge": existing,
                "source_unit_id": source_id,
                "target_unit_id": target_id,
                "last_updated": _utc_now(),
            }

        edge = RelationalEdge(
            target_unit_id=target_id,
            relation_type=str(relation_type or "reinforces"),
            strength=max(0.0, min(1.0, float(strength or 0.5))),
            metadata={
                "suggested_via": "mcp",
                "rationale": str(rationale or ""),
                "suggested_at": _utc_now(),
            },
        )
        updated = store.store_relational_edge(source_id, edge)
        return {
            "resource": "cognitive/relational-suggestion",
            "accepted": updated is not None,
            "created": updated is not None,
            "source_unit_id": source_id,
            "target_unit_id": target_id,
            "edge": edge.to_dict(),
            "last_updated": _utc_now(),
        }

    # ──────────────────────────────────────────────────────────────
    # Phase 2.4 — Emotional Memory MCP exposure
    # ──────────────────────────────────────────────────────────────

    def get_emotional_memory(self, *, limit: int = 50) -> dict[str, Any]:
        """Return recent emotional memory entries + current emotional summary."""
        store = self._get_store()
        entries = store.get_emotional_memory(limit=int(limit))
        snapshot = store.get_relational_self()
        return {
            "resource": "self/emotional-memory",
            "entries": entries,
            "emotional_summary": dict(snapshot.emotional_summary or {}),
            "limit": int(limit),
            "last_updated": _utc_now(),
        }

    def get_emotional_arc(self, *, limit: int = 100) -> dict[str, Any]:
        """Return the emotional bond arc trajectory."""
        store = self._get_store()
        arc_points = store.get_emotional_arc(limit=int(limit))
        snapshot = store.get_relational_self()
        emotional_summary = dict(snapshot.emotional_summary or {})
        bond_trend = emotional_summary.get("bond_trend", "stable")
        return {
            "resource": "self/emotional-arc",
            "arc": arc_points,
            "bond_trend": bond_trend,
            "limit": int(limit),
            "last_updated": _utc_now(),
        }

    def get_emotional_insight(self, question: str, *, limit: int = 10) -> dict[str, Any]:
        """Answer an emotionally-framed question about the relational bond.

        Always cites inferred signals — never claims real subjective experience.
        """
        prompt = str(question or "").strip()
        store = self._get_store()
        entries = store.get_emotional_memory(limit=max(limit, 20))
        arc_points = store.get_emotional_arc(limit=50)
        snapshot = store.get_relational_self()
        emotional_summary = dict(snapshot.emotional_summary or {})

        dominant_tone = str(emotional_summary.get("dominant_tone") or "neutral")
        bond_strength = float(emotional_summary.get("bond_strength") or 0.0)
        bond_trend = str(emotional_summary.get("bond_trend") or "stable")
        confidence = float(emotional_summary.get("confidence") or 0.0)

        lang = _detect_language(prompt)

        # Guard: no data yet
        if not entries and not emotional_summary:
            no_data = (
                "Недостаточно данных для анализа эмоционального состояния связи."
                if lang == "ru"
                else "Insufficient data to analyze the relational bond state."
            )
            return {
                "resource": "self/emotional-insight",
                "question": prompt,
                "answer": no_data,
                "dominant_tone": "neutral",
                "bond_strength": 0.0,
                "bond_trend": "stable",
                "supporting_entries": [],
                "causal_trace": [],
                "last_updated": _utc_now(),
            }

        # Build a simple deterministic bilingual answer based on observed signals
        if lang == "ru":
            trend_phrase = {
                "warming": "укреплялась и теплела",
                "cooling": "становилась более холодной",
                "volatile": "показывала нестабильные сигналы",
                "stable": "оставалась стабильной",
            }.get(bond_trend, "оставалась стабильной")
            tone_phrase = {
                "warm": "Выявленный тон — тёплый, что указывает на устойчивое позитивное взаимодействие.",
                "calm": "Выявленный тон — спокойный, отражающий стабильное взаимодействие.",
                "reflective": "Выявленный тон — рефлексивный, указывающий на глубину обмена.",
                "joyful": "Выявленный тон — радостный, определённый по позитивным сигналам обратной связи.",
                "supportive": "Выявленный тон — поддерживающий, определённый по заботливым обменам.",
                "tense": "Выявленный тон — напряжённый, отражающий определённые противоречия или трение.",
                "frustrated": "Выявленный тон — разочарованный, определённый по негативным сигналам.",
                "anxious": "Выявленный тон — тревожный, по маркерам неопределённости.",
                "uncertain": "Выявленный тон — неопределённый, из-за неразрешённых несоответствий.",
                "neutral": "Выявленный тон — нейтральный; сильных направленных сигналов не обнаружено.",
            }.get(dominant_tone, f"Выявленный тон — {_TONE_NAMES_RU.get(dominant_tone, dominant_tone)}.")
            answer = (
                f"На основе выявленных сигналов связь {trend_phrase}. "
                f"{tone_phrase} "
                f"Текущая сила связи: {bond_strength:.2f} (уверенность {confidence:.2f}). "
                f"Данные получены из {len(entries)} записей взаимодействий."
            )
        else:
            trend_phrase = {
                "warming": "has been growing warmer and more stable",
                "cooling": "has shifted toward greater distance",
                "volatile": "has shown fluctuating signals",
                "stable": "has remained consistent",
            }.get(bond_trend, "has remained consistent")
            tone_phrase = {
                "warm": "The dominant inferred tone is warm, suggesting sustained positive alignment.",
                "calm": "The dominant inferred tone is calm, reflecting steady and low-tension engagement.",
                "reflective": "The dominant inferred tone is reflective, indicating depth of inquiry.",
                "joyful": "The dominant inferred tone is joyful, based on positive feedback signals.",
                "supportive": "The dominant inferred tone is supportive, inferred from care-oriented exchanges.",
                "tense": "The dominant inferred tone is tense, reflecting detected contradictions or friction.",
                "frustrated": "The dominant inferred tone is frustrated, based on observed negative signals.",
                "anxious": "The dominant inferred tone is anxious, based on uncertainty markers.",
                "uncertain": "The dominant inferred tone is uncertain, from unresolved policy or coherence gaps.",
                "neutral": "The dominant inferred tone is neutral — no strong directional signal is evident.",
            }.get(dominant_tone, f"The dominant inferred tone is {dominant_tone}.")
            answer = (
                f"Based on inferred signals, the relational bond {trend_phrase}. "
                f"{tone_phrase} "
                f"Bond strength is currently {bond_strength:.2f} (confidence {confidence:.2f}). "
                f"This is derived from {len(entries)} recent interaction records."
            )

        # Build causal_trace with emotional nodes
        causal_trace: list[dict[str, Any]] = []
        prev_node_id: str | None = None
        for entry in entries[-3:]:
            node_id = f"emotional_event:{entry.get('entry_id') or entry.get('timestamp')}"
            causal_trace.append({
                "node_id": node_id,
                "type": "emotional_event",
                "timestamp": entry.get("timestamp"),
                "emotional_tone": entry.get("emotional_tone"),
                "valence": entry.get("valence"),
                "confidence": entry.get("confidence"),
                "trigger_source": entry.get("trigger_source"),
                "linked_from": prev_node_id,
            })
            prev_node_id = node_id

        if arc_points and len(arc_points) >= 2:
            first_bond = float((arc_points[0].get("bond_strength") or 0.0))
            last_bond = float((arc_points[-1].get("bond_strength") or 0.0))
            node_id = "bond_shift:arc_summary"
            causal_trace.append({
                "node_id": node_id,
                "type": "bond_shift",
                "bond_start": round(first_bond, 4),
                "bond_end": round(last_bond, 4),
                "bond_delta": round(last_bond - first_bond, 4),
                "bond_trend": bond_trend,
                "arc_length": len(arc_points),
                "confidence": round(confidence, 4),
                "linked_from": prev_node_id,
            })
            prev_node_id = node_id

        node_id = "emotional_summary_state:current"
        causal_trace.append({
            "node_id": node_id,
            "type": "emotional_summary_state",
            "dominant_tone": dominant_tone,
            "bond_strength": bond_strength,
            "bond_trend": bond_trend,
            "confidence": confidence,
            "linked_from": prev_node_id,
        })

        supporting_entries = entries[-limit:]

        return {
            "resource": "self/emotional-insight",
            "question": prompt,
            "answer": answer,
            "dominant_tone": dominant_tone,
            "bond_strength": bond_strength,
            "bond_trend": bond_trend,
            "supporting_entries": supporting_entries,
            "causal_trace": causal_trace,
            "last_updated": _utc_now(),
        }

    # NOTE: get_cognitive_state is intentionally defined near the top of this class.
