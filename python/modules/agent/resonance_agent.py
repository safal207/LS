"""ResonanceAgent — unified cognitive resonance pipeline agent.

Single entry point that runs the complete pipeline:

    Text / STT  →  Intent  →  WHY  →  Strategy + Anchor  →  Empathy  →
    BodyCopilot  →  ResonanceScorer  →  LLM  →  CognitiveCycleLogger  →
    ResonanceLearner

and returns a single structured dict matching the spec:

    {
      "cycle_id":        "a3f7c1b2",
      "input":           "почему не использовали Redis?",
      "raw_stt":         "почему не использовали Redis?",
      "corrected":       "почему не использовали Redis?",
      "intent":          {"type": "defense", "entity": "Redis", ...},
      "why":             "интервьюер проверяет trade-off reasoning",
      "strategy":        "защити решение + покажи trade-offs",
      "anchor_used":     ["Оптимизировал Redis: 400ms→20ms"],
      "empathy_cues":    {"pause": 1.5, "breath": "inhale", ...},
      "pre_prompt":      "🧠 Сейчас: защити решение  ⏸ 1.5с → inhale ...",
      "final_output":    "Мы рассматривали Redis, однако...",
      "feedback":        null,
      "resonance_score": 0.87
    }

Design
------
* Synchronous, no queues — ``process_text(text)`` blocks until LLM responds.
* Queue-friendly: ``process_item(item)`` accepts a pre-built pipeline item
  (e.g. from SmartEar's output queue).
* The ``llm_fn`` callable is the only dependency on the actual LLM; if None,
  the agent returns the ``pre_prompt`` as ``final_output`` (useful in tests).
* Thread-safe: ``InterviewerProfile`` and ``ResonanceLearner`` are guarded
  internally; the agent itself can be called from multiple threads.
* ``anchor`` list is static per session; pass a new agent per conversation.

Usage::

    from agent.resonance_agent import ResonanceAgent

    def my_llm(prompt: str, system: str) -> str:
        ...  # call Anthropic / OpenAI / Ollama

    agent = ResonanceAgent(
        anchor=[
            "Оптимизировал индексы: 4s → 0.2s",
            "Настроил Kafka для 50k msg/s",
        ],
        llm_fn=my_llm,
        weights_path="logs/resonance_weights.json",
    )

    result = agent.process_text("почему не использовали Redis?")
    print(result["resonance_score"])   # 0.87
    print(result["pre_prompt"])        # shown instantly in UI overlay

    # Later — add user feedback to trigger learning:
    agent.feedback(result["cycle_id"], "ответ слишком длинный")
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy imports (all optional, graceful fallback)
# ---------------------------------------------------------------------------

try:
    from intent.why_strategy import analyze_why_and_strategy as _analyze
    _STRATEGY_OK = True
except Exception:
    _STRATEGY_OK = False
    _analyze = None  # type: ignore[assignment]

try:
    from intent.interviewer_profile import InterviewerProfile as _InterviewerProfile
    _PROFILE_OK = True
except Exception:
    _PROFILE_OK = False
    _InterviewerProfile = None  # type: ignore[assignment]

try:
    from intent.empathy_negotiation import EmpathyNegotiationLayer as _EmpathyLayer
    _EMPATHY_OK = True
except Exception:
    _EMPATHY_OK = False
    _EmpathyLayer = None  # type: ignore[assignment]

try:
    from intent.body_aware_copilot import BodyAwareCopilot as _Copilot
    _COPILOT_OK = True
except Exception:
    _COPILOT_OK = False
    _Copilot = None  # type: ignore[assignment]

try:
    from intent.resonance_scorer import ResonanceScorer as _Scorer
    _SCORER_OK = True
except Exception:
    _SCORER_OK = False
    _Scorer = None  # type: ignore[assignment]

try:
    from cognitive_flow.resonance_learner import ResonanceLearner as _Learner
    _LEARNER_OK = True
except Exception:
    _LEARNER_OK = False
    _Learner = None  # type: ignore[assignment]

try:
    from cognitive_flow.cycle_logger import CognitiveCycleLogger as _CycleLogger
    _LOGGER_OK = True
except Exception:
    _LOGGER_OK = False
    _CycleLogger = None  # type: ignore[assignment]

try:
    from intent.intent_layer import IntentLayer as _IntentLayer
    _INTENT_OK = True
except Exception:
    _INTENT_OK = False
    _IntentLayer = None  # type: ignore[assignment]

try:
    from intent.why_layer import WhyLayer as _WhyLayer
    _WHY_OK = True
except Exception:
    _WHY_OK = False
    _WhyLayer = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# ResonanceAgent
# ---------------------------------------------------------------------------

class ResonanceAgent:
    """Unified cognitive resonance agent.

    Runs all pipeline stages in a single synchronous call and returns the
    complete structured output matching the spec.

    Args:
        anchor:       List of candidate's real experience / achievement strings
                      that are injected as ``_anchor_context``.
        llm_fn:       Callable ``(user_prompt: str, system_prompt: str) → str``.
                      If None, the agent returns ``pre_prompt`` as the response
                      (dry-run / test mode).
        weights_path: Path to ``ResonanceLearner`` JSON weights file.  Empty
                      string disables persistence.
        log_path:     Path to ``CognitiveCycleLogger`` JSONL file.  Empty
                      string disables logging.
        log_max_mb:   Rotate log above this size (MB).
        orientation:  Optional free-text session context injected at the top
                      of every LLM system prompt
                      (e.g. "Senior backend interview, fintech company").
    """

    def __init__(
        self,
        anchor:       Optional[List[str]] = None,
        llm_fn:       Optional[Callable[[str, str], str]] = None,
        weights_path: str = "",
        log_path:     str = "",
        log_max_mb:   float = 50.0,
        orientation:  str = "",
    ) -> None:
        self._anchor      = list(anchor or [])
        self._llm_fn      = llm_fn
        self._orientation = orientation

        # Stage 4 — Intent
        self._intent = _IntentLayer() if _INTENT_OK and _IntentLayer else None

        # Stage 5 — WHY
        self._why = _WhyLayer() if _WHY_OK and _WhyLayer else None

        # Stage 6 — WHY Strategy is a function, not a class (called per item)

        # Stage 6b — InterviewerProfile (shared, mutated per question)
        self._profile = (
            _InterviewerProfile() if _PROFILE_OK and _InterviewerProfile else None
        )

        # Stage 7 — Empathy & Negotiation
        self._empathy = (
            _EmpathyLayer() if _EMPATHY_OK and _EmpathyLayer else None
        )

        # Stage 8 — Body-Aware Copilot
        self._copilot = (
            _Copilot() if _COPILOT_OK and _Copilot else None
        )

        # Stage 9 — Resonance Scorer
        self._scorer = (
            _Scorer() if _SCORER_OK and _Scorer else None
        )

        # Learning
        self._learner = (
            _Learner(path=weights_path) if _LEARNER_OK and _Learner else None
        )

        # Logging
        self._logger = (
            _CycleLogger(path=log_path, max_mb=log_max_mb)
            if _LOGGER_OK and _CycleLogger
            else None
        )

        # Short-lived cache of completed cycle items (last 50) so feedback()
        # can look up the actual resonance_score and active_rules rather than
        # assuming 0.0.  Bounded at _max_cached entries, LRU-evicted by
        # insertion order.  Guarded by _cycles_lock for multi-thread safety
        # (~15 KB/cycle × 50 = ~750 KB worst-case footprint).
        self._recent_cycles: dict[str, dict] = {}
        self._max_cached    = 50
        self._cycles_lock   = threading.Lock()

        logger.info(
            "ResonanceAgent ready — anchor=%d items  llm=%s  learner=%s",
            len(self._anchor),
            "yes" if llm_fn else "dry-run",
            "yes" if self._learner else "no",
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process_text(self, text: str) -> dict:
        """Process a text input through the full pipeline.

        Blocks until the LLM responds (or returns pre_prompt in dry-run mode).

        Args:
            text: User speech / question (post-STT or raw text).

        Returns:
            Complete cycle dict matching the spec, including ``resonance_score``.
        """
        item: dict = {
            "text":            text,
            "_original_text":  text,
            "_corrected_text": text,
            "_anchor_context": list(self._anchor),
        }
        return self._run_pipeline(item)

    def process_item(self, item: dict) -> dict:
        """Process a pre-built pipeline item (e.g. from SmartEar output queue).

        ``item["text"]`` must be set.  ``_anchor_context`` is merged with
        ``self._anchor`` if not already present.
        """
        if "_anchor_context" not in item:
            item["_anchor_context"] = list(self._anchor)
        return self._run_pipeline(item)

    def feedback(self, cycle_id: str, feedback_text: str) -> None:
        """Record user feedback for a completed cycle and trigger learning.

        Looks up the actual resonance_score from the recent-cycle cache so the
        learner receives the correct signal instead of a hard-coded 0.0.
        Positive feedback ("отлично", "good", "yes"…) preserves the original
        score as a reinforcement signal; negative/corrective feedback triggers
        the reversal multiplier inside ResonanceLearner.

        Args:
            cycle_id:      ID returned in the cycle dict (``result["cycle_id"]``).
            feedback_text: Short description of what was wrong / right.
        """
        if self._logger:
            self._logger.add_feedback(cycle_id, feedback_text)
        if self._learner:
            with self._cycles_lock:
                cached = self._recent_cycles.get(cycle_id) or {}
            self._learner.learn({
                "resonance_score": cached.get("resonance_score", 0.5),
                "copilot": {
                    "active_rules": (
                        (cached.get("_copilot_output") or {}).get("active_rules") or []
                    ),
                },
                "user_feedback": feedback_text,
            })

    # ------------------------------------------------------------------
    # Internal pipeline
    # ------------------------------------------------------------------

    def _run_pipeline(self, item: dict) -> dict:
        text = item.get("text", "")

        # Phase 1 — start logging cycle
        cycle_id = str(uuid.uuid4())[:8]
        item["_cycle_id"] = cycle_id
        log_cycle_id: Optional[str] = None
        if self._logger:
            try:
                log_cycle_id = self._logger.start_cycle(item)
                item["_cycle_id"] = log_cycle_id
                cycle_id = log_cycle_id
            except Exception as exc:
                logger.debug("ResonanceAgent: logger.start_cycle failed: %s", exc)

        # Stage 4 — Intent
        if self._intent:
            try:
                item = self._intent.process_item(item)
            except Exception as exc:
                logger.debug("ResonanceAgent: IntentLayer failed: %s", exc)

        # Stage 5 — WHY
        if self._why:
            try:
                item = self._why.process_item(item)
            except Exception as exc:
                logger.debug("ResonanceAgent: WhyLayer failed: %s", exc)

        # Stage 6 — WHY Strategy + Anchor + InterviewerProfile
        if _STRATEGY_OK and _analyze:
            try:
                strategy = _analyze(text)
                if self._profile:
                    self._profile.observe(text, strategy)
                    strategy.apply_interviewer_bias(self._profile)
                    item["_interviewer_profile"] = self._profile.to_dict()
                item["_why_strategy"] = strategy.to_dict()
            except Exception as exc:
                logger.debug("ResonanceAgent: strategy stage failed: %s", exc)

        # Stage 7 — Empathy & Negotiation
        if self._empathy:
            try:
                item = self._empathy.process(item)
            except Exception as exc:
                logger.debug("ResonanceAgent: EmpathyLayer failed: %s", exc)

        # Stage 8 — Body-Aware Copilot
        if self._copilot:
            try:
                item = self._copilot.process(item)
            except Exception as exc:
                logger.debug("ResonanceAgent: Copilot failed: %s", exc)

        # Stage 9 — Resonance Scorer
        if self._scorer:
            try:
                item = self._scorer.process(item)
            except Exception as exc:
                logger.debug("ResonanceAgent: ResonanceScorer failed: %s", exc)

        # Phase 2 — build system prompt and call LLM
        t0 = time.perf_counter()
        try:
            final_output = self._call_llm(item)
        except Exception as exc:
            logger.warning("ResonanceAgent: LLM call failed: %s", exc)
            final_output = item.get("_copilot_output", {}).get("pre_prompt", "")
        generation_time = time.perf_counter() - t0

        # After LLM: update resonance_score with response quality signal
        base_score = item.get("_resonance_score", 0.5)
        response_score = self._rate_response(final_output, item)
        final_score = round((base_score * 0.7 + response_score * 0.3), 3)
        item["_resonance_score"] = final_score

        # Phase 2 — complete log cycle
        if self._logger and log_cycle_id:
            try:
                self._logger.complete_cycle(
                    cycle_id=log_cycle_id,
                    output=final_output,
                    generation_time=generation_time,
                )
            except Exception as exc:
                logger.debug("ResonanceAgent: logger.complete_cycle failed: %s", exc)

        # Learning — unsupervised (no explicit feedback yet)
        if self._learner:
            try:
                self._learner.learn(self._build_cycle_record(
                    item, final_output, generation_time
                ))
            except Exception as exc:
                logger.debug("ResonanceAgent: learner.learn failed: %s", exc)

        result = self._build_output(item, final_output, generation_time, cycle_id)
        # Cache the pipeline item so feedback() can look up the real
        # resonance_score and active_rules (not the sanitised output dict).
        with self._cycles_lock:
            self._recent_cycles[cycle_id] = item
            if len(self._recent_cycles) > self._max_cached:
                # Evict oldest (dict preserves insertion order in 3.7+)
                self._recent_cycles.pop(next(iter(self._recent_cycles)))
        return result

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(self, item: dict) -> str:
        """Assemble the system prompt and call llm_fn."""
        system = self._build_system_prompt(item)
        user   = item.get("text", "")
        if self._llm_fn:
            return self._llm_fn(user, system)
        # Dry-run: return the pre_prompt so the caller can see the overlay
        copilot = item.get("_copilot_output") or {}
        return copilot.get("pre_prompt") or "ответь по существу"

    def _build_system_prompt(self, item: dict) -> str:
        """Assemble the full LLM system prompt from all pipeline stages."""
        parts: list[str] = []

        # 0. Session orientation
        if self._orientation:
            parts.append(f"Контекст сессии: {self._orientation}")

        # 1. Copilot final_prompt (pre-assembled by Stage 8)
        copilot = item.get("_copilot_output") or {}
        fp = copilot.get("final_prompt", "")
        if fp:
            parts.append(fp)

        # 2. Resonance score hint (high score → keep it up; low → extra care)
        score = item.get("_resonance_score", 0.5)
        if score < 0.45:
            parts.append(
                "⚠️ Низкий резонанс — высокое давление.  "
                "Начни с подтверждения, снизь темп, используй короткие фразы."
            )
        elif score >= 0.80:
            parts.append(
                "✅ Высокий резонанс — хороший контакт.  "
                "Продолжай в том же ритме — конкретно и уверенно."
            )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Response quality heuristic (post-LLM resonance update)
    # ------------------------------------------------------------------

    def _rate_response(self, response: str, item: dict) -> float:
        """Return a 0-1 quality score for the LLM response.

        Purely heuristic — no ML.  Used to adjust the resonance_score
        after seeing the actual output (length, anchor usage, etc.).
        """
        if not response:
            return 0.3
        words     = len(response.split())
        answer_t  = (item.get("_why_strategy") or {}).get("answer_type", "short")
        anchor_ctx = item.get("_anchor_context") or []

        # Length appropriateness
        if answer_t in ("short", "brief"):
            length_score = 1.0 if 10 <= words <= 60 else (0.7 if words < 10 else 0.6)
        elif answer_t in ("definition", "reasoning"):
            length_score = 1.0 if 30 <= words <= 150 else 0.7
        else:  # experiential, defense
            length_score = 1.0 if 50 <= words <= 200 else 0.7

        # Anchor citation bonus
        anchor_bonus = 0.0
        if anchor_ctx:
            resp_lower = response.lower()
            if any(a.split(":")[0].lower() in resp_lower for a in anchor_ctx if a):
                anchor_bonus = 0.10

        return round(min(1.0, length_score * 0.9 + anchor_bonus), 3)

    # ------------------------------------------------------------------
    # Output assembly
    # ------------------------------------------------------------------

    def _build_output(
        self,
        item: dict,
        final_output: str,
        generation_time: float,
        cycle_id: str,
    ) -> dict:
        """Build the spec-compliant output dict."""
        strategy  = item.get("_why_strategy")  or {}
        copilot   = item.get("_copilot_output") or {}
        intent    = item.get("_intent")
        why       = item.get("_why")

        return {
            # Identity
            "cycle_id":        cycle_id,
            # Perception
            "input":           item.get("text", ""),
            "raw_stt":         item.get("_original_text", item.get("text", "")),
            "corrected":       item.get("_corrected_text", item.get("text", "")),
            # Interpretation
            "intent":          intent,
            "why":             (
                (why.get("reason") if isinstance(why, dict) else why)
                or strategy.get("micro_trigger", "")
            ),
            # Strategy
            "strategy":        strategy.get("micro_trigger", ""),
            "anchor_used":     item.get("_anchor_context") or [],
            # Body cues for UI overlay
            "empathy_cues":    copilot.get("empathy_cues"),
            "pre_prompt":      copilot.get("pre_prompt", ""),
            "intervention_level": copilot.get("intervention_level", "low"),
            # Interviewer model
            "interviewer_profile": item.get("_interviewer_profile"),
            # Output
            "final_output":    final_output,
            "generation_time": round(generation_time, 4),
            "feedback":        None,
            # Resonance
            "resonance_score":  item.get("_resonance_score", 0.5),
            "resonance_detail": item.get("_resonance_detail"),
        }

    def _build_cycle_record(
        self, item: dict, output: str, generation_time: float
    ) -> dict:
        """Build a minimal cycle record for the learner."""
        copilot = item.get("_copilot_output") or {}
        return {
            "resonance_score": item.get("_resonance_score", 0.5),
            "copilot": {
                "active_rules": copilot.get("active_rules") or [],
            },
            "user_feedback": None,
        }
