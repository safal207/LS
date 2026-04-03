# -*- coding: utf-8 -*-
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

from config import (
    GRAPH_CARE_CYCLES_ENABLED,
    GRAPH_CARE_CYCLES_MIN_QUALITY,
    GRAPH_CARE_CYCLES_MIN_TRUST,
    GRAPH_CARE_CYCLES_RETIRE_TRUST,
    GRAPH_COALITION_ENABLED,
    GRAPH_COALITION_STORE_PATH,
    GRAPH_DERIVED_MODULE_ENABLED,
    GRAPH_DERIVED_MODULE_MIN_QUALITY,
    GRAPH_DERIVED_MODULE_MIN_TRUST,
    GRAPH_DERIVED_MODULE_STORE_PATH,
    GRAPH_TRAIL_DECAY,
    GRAPH_TRAIL_ENABLED,
    GRAPH_TRAIL_EXPLORATION_RATE,
    GRAPH_TRAIL_STORE_PATH,
    MAX_TOKENS,
    TEMPERATURE,
)
from shared.interview_schema import ensure_interview_item

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

try:
    from graph import CareCycleRunner as _CareCycleRunner
    from graph import CooperativeGraphEngine as _CooperativeGraphEngine
    from graph import CoalitionRegistry as _CoalitionRegistry
    from graph import DerivedModuleRegistry as _DerivedModuleRegistry
    from graph import GraphMemoryRuntime as _GraphMemoryRuntime
    from graph import PathExecutionRecord as _PathExecutionRecord
    from graph import PathSelector as _PathSelector
    from graph import RouteStatsStore as _RouteStatsStore
    from graph import TrailUpdater as _TrailUpdater
    _GRAPH_OK = True
except Exception:
    _GRAPH_OK = False
    _CareCycleRunner = None  # type: ignore[assignment]
    _CooperativeGraphEngine = None  # type: ignore[assignment]
    _CoalitionRegistry = None  # type: ignore[assignment]
    _DerivedModuleRegistry = None  # type: ignore[assignment]
    _GraphMemoryRuntime = None  # type: ignore[assignment]
    _PathExecutionRecord = None  # type: ignore[assignment]
    _PathSelector = None  # type: ignore[assignment]
    _RouteStatsStore = None  # type: ignore[assignment]
    _TrailUpdater = None  # type: ignore[assignment]

try:
    from graph.relational_field import RelationalFieldAnalyzer as _RelationalFieldAnalyzer
    _RELATIONAL_OK = True
except Exception:
    _RELATIONAL_OK = False
    _RelationalFieldAnalyzer = None  # type: ignore[assignment]

try:
    from graph.alignment import InteractionAlignmentAnalyzer as _InteractionAlignmentAnalyzer
    _ALIGNMENT_OK = True
except Exception:
    _ALIGNMENT_OK = False
    _InteractionAlignmentAnalyzer = None  # type: ignore[assignment]

try:
    from modules.agent.alignment_guidance import (
        build_alignment_guidance as _build_alignment_guidance,
    )
    _ALIGNMENT_GUIDANCE_OK = True
except ImportError:
    try:
        from agent.alignment_guidance import (
            build_alignment_guidance as _build_alignment_guidance,
        )
        _ALIGNMENT_GUIDANCE_OK = True
    except ImportError:
        _ALIGNMENT_GUIDANCE_OK = False
        _build_alignment_guidance = None  # type: ignore[assignment]
    except Exception as exc:
        logger.debug(
            "ResonanceAgent: unexpected alignment guidance import failure (agent.*): %s",
            exc,
        )
        _ALIGNMENT_GUIDANCE_OK = False
        _build_alignment_guidance = None  # type: ignore[assignment]
except Exception as exc:
    logger.debug(
        "ResonanceAgent: unexpected alignment guidance import failure (modules.*): %s",
        exc,
    )
    _ALIGNMENT_GUIDANCE_OK = False
    _build_alignment_guidance = None  # type: ignore[assignment]

try:
    from agent.softening_detector import SofteningAnalysis as _SofteningAnalysis
    from agent.softening_detector import analyze_softening_signals as _analyze_softening_signals
    _SOFTENING_DETECTOR_OK = True
except ImportError:
    try:
        from modules.agent.softening_detector import SofteningAnalysis as _SofteningAnalysis
        from modules.agent.softening_detector import analyze_softening_signals as _analyze_softening_signals
        _SOFTENING_DETECTOR_OK = True
    except ImportError:
        _SOFTENING_DETECTOR_OK = False
        _SofteningAnalysis = None  # type: ignore[assignment,misc]
        _analyze_softening_signals = None  # type: ignore[assignment]

try:
    from network.cognitive_adequacy import CognitiveAdequacyCore as _CognitiveAdequacyCore
    from network.control_center import NetworkControlCenter as _NetworkControlCenter
    from network.observer import NetworkObserver as _NetworkObserver
    from network.orientation_center import OrientationCenter as _NetworkOrientationCenter
    _NETWORK_OK = True
except Exception:
    _NETWORK_OK = False
    _CognitiveAdequacyCore = None  # type: ignore[assignment]
    _NetworkControlCenter = None  # type: ignore[assignment]
    _NetworkObserver = None  # type: ignore[assignment]
    _NetworkOrientationCenter = None  # type: ignore[assignment]


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
        llm_backend = None,
        graph_runtime = None,
        weights_path: str = "",
        log_path:     str = "",
        log_max_mb:   float = 50.0,
        orientation:  str = "",
    ) -> None:
        self._anchor      = list(anchor or [])
        self._llm_fn      = llm_fn
        self._llm_backend = llm_backend
        self._graph_runtime = graph_runtime or (
            _GraphMemoryRuntime() if _GRAPH_OK and _GraphMemoryRuntime else None
        )
        self._cooperative_engine = (
            _CooperativeGraphEngine(getattr(llm_backend, "backends", {}))
            if _GRAPH_OK and _CooperativeGraphEngine and llm_backend is not None and hasattr(llm_backend, "backends")
            else None
        )
        self._coalition_registry = None
        if GRAPH_COALITION_ENABLED and _GRAPH_OK and _CoalitionRegistry:
            try:
                self._coalition_registry = _CoalitionRegistry(GRAPH_COALITION_STORE_PATH)
                self._coalition_registry.seed_default()
            except Exception as exc:
                logger.debug("ResonanceAgent: coalition registry init failed: %s", exc)
                self._coalition_registry = None
        self._derived_module_registry = None
        if GRAPH_DERIVED_MODULE_ENABLED and _GRAPH_OK and _DerivedModuleRegistry:
            try:
                self._derived_module_registry = _DerivedModuleRegistry(GRAPH_DERIVED_MODULE_STORE_PATH)
            except Exception as exc:
                logger.debug("ResonanceAgent: derived module registry init failed: %s", exc)
                self._derived_module_registry = None
        self._care_cycle_runner = None
        if GRAPH_CARE_CYCLES_ENABLED and self._derived_module_registry and _GRAPH_OK and _CareCycleRunner:
            try:
                self._care_cycle_runner = _CareCycleRunner(
                    self._derived_module_registry,
                    min_quality=GRAPH_CARE_CYCLES_MIN_QUALITY,
                    min_trust=GRAPH_CARE_CYCLES_MIN_TRUST,
                    retire_trust=GRAPH_CARE_CYCLES_RETIRE_TRUST,
                )
            except Exception as exc:
                logger.debug("ResonanceAgent: care cycle init failed: %s", exc)
                self._care_cycle_runner = None
        self._route_stats_store = (
            _RouteStatsStore(GRAPH_TRAIL_STORE_PATH)
            if (GRAPH_TRAIL_ENABLED or GRAPH_COALITION_ENABLED or GRAPH_DERIVED_MODULE_ENABLED) and _GRAPH_OK and _RouteStatsStore
            else None
        )
        self._path_selector = (
            _PathSelector(
                self._route_stats_store,
                coalition_registry=self._coalition_registry,
                exploration_rate=GRAPH_TRAIL_EXPLORATION_RATE,
            )
            if self._route_stats_store and _PathSelector
            else None
        )
        self._trail_updater = (
            _TrailUpdater(self._route_stats_store, decay=GRAPH_TRAIL_DECAY)
            if self._route_stats_store and _TrailUpdater
            else None
        )
        self._orientation_center = (
            _NetworkOrientationCenter(
                graph_runtime=self._graph_runtime,
                path_selector=self._path_selector,
                derived_module_registry=self._derived_module_registry,
                llm_backend=self._llm_backend,
                adequacy_core=(_CognitiveAdequacyCore() if _NETWORK_OK and _CognitiveAdequacyCore else None),
                observer_core=(_NetworkObserver() if _NETWORK_OK and _NetworkObserver else None),
                derived_min_quality=GRAPH_DERIVED_MODULE_MIN_QUALITY,
                derived_min_trust=GRAPH_DERIVED_MODULE_MIN_TRUST,
            )
            if _NETWORK_OK and _NetworkOrientationCenter and (
                self._graph_runtime or self._path_selector or self._derived_module_registry
            )
            else None
        )
        self._control_center = (
            _NetworkControlCenter(
                orientation_center=self._orientation_center,
                observer_core=(_NetworkObserver() if _NETWORK_OK and _NetworkObserver else None),
            )
            if _NETWORK_OK and _NetworkControlCenter and self._orientation_center
            else None
        )
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
        self._relational_analyzer = (
            _RelationalFieldAnalyzer()
            if _RELATIONAL_OK and _RelationalFieldAnalyzer
            else None
        )
        self._alignment_analyzer = (
            _InteractionAlignmentAnalyzer()
            if _ALIGNMENT_OK and _InteractionAlignmentAnalyzer
            else None
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
        self._alignment_metrics_lock = threading.Lock()
        self._alignment_outcome_metrics: dict[str, float | int] = {
            "observed_cycles": 0,
            "guidance_added_count": 0,
            "guidance_effective_count": 0,
            "guidance_no_effect_count": 0,
            "_pre_tension_sum": 0.0,
            "_post_resonance_sum": 0.0,
            "_post_goal_alignment_sum": 0.0,
            # per-signal softening counters (advisory observability only)
            "softening_detected_count": 0,
            "softening_neutral_count": 0,
            "_signal_bridge_phrase": 0,
            "_signal_acknowledgment": 0,
            "_signal_proposal_framing": 0,
            "_signal_pacing_marker": 0,
            "_signal_dialogue_invitation": 0,
            "_signal_dialogue_invitation_structural": 0,
        }

        logger.info(
            "ResonanceAgent ready — anchor=%d items  llm=%s  learner=%s",
            len(self._anchor),
            "yes" if (llm_backend or llm_fn) else "dry-run",
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
        item: dict = ensure_interview_item({
            "type": "question",
            "text": text,
            "confidence": 1.0,
            "source": "text_input",
            "words": [],
            "_words": [],
            "_asr_confidence": 1.0,
            "clean_text": text,
            "_clean_text": text,
            "_original_text": text,
            "_corrected_text": text,
            "_anchor_context": list(self._anchor),
        }, default_source="text_input")
        return self._run_pipeline(item)

    def process_item(self, item: dict) -> dict:
        """Process a pre-built pipeline item (e.g. from SmartEar output queue).

        ``item["text"]`` must be set.  ``_anchor_context`` is merged with
        ``self._anchor`` if not already present.
        """
        item = ensure_interview_item(item, default_source="smart_ear")
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
            # BUG-16 fix: use 0.0 as default when cycle is not in cache so the
            # learner receives a genuine "unknown/failed" signal instead of a
            # neutral 0.5 that would incorrectly reinforce absent cycles.
            score = cached.get("_resonance_score", 0.0) if cached else 0.0
            self._learner.learn({
                "resonance_score": score,
                "copilot": {
                    "active_rules": (
                        (cached.get("_copilot_output") or {}).get("active_rules") or []
                    ),
                },
                "user_feedback": feedback_text,
            })

    def get_alignment_outcome_metrics(self) -> dict:
        """Return aggregate observability counters for soft-alignment outcomes."""
        _SIGNAL_KEYS = (
            "bridge_phrase", "acknowledgment", "proposal_framing",
            "pacing_marker", "dialogue_invitation", "dialogue_invitation_structural",
        )
        with self._alignment_metrics_lock:
            observed = int(self._alignment_outcome_metrics.get("observed_cycles", 0) or 0)
            guidance_added = int(self._alignment_outcome_metrics.get("guidance_added_count", 0) or 0)
            pre_tension_sum = float(self._alignment_outcome_metrics.get("_pre_tension_sum", 0.0) or 0.0)
            post_resonance_sum = float(self._alignment_outcome_metrics.get("_post_resonance_sum", 0.0) or 0.0)
            post_goal_sum = float(self._alignment_outcome_metrics.get("_post_goal_alignment_sum", 0.0) or 0.0)
            effective = int(self._alignment_outcome_metrics.get("guidance_effective_count", 0) or 0)
            no_effect = int(self._alignment_outcome_metrics.get("guidance_no_effect_count", 0) or 0)
            softening_detected = int(self._alignment_outcome_metrics.get("softening_detected_count", 0) or 0)
            softening_neutral = int(self._alignment_outcome_metrics.get("softening_neutral_count", 0) or 0)
            signal_counts = {
                sig: int(self._alignment_outcome_metrics.get(f"_signal_{sig}", 0) or 0)
                for sig in _SIGNAL_KEYS
            }

        return {
            "observed_cycles": observed,
            "guidance_added_count": guidance_added,
            "guidance_effective_count": effective,
            "guidance_no_effect_count": no_effect,
            "guidance_effect_rate": (effective / guidance_added) if guidance_added else 0.0,
            "avg_pre_tension_score": (pre_tension_sum / observed) if observed else 0.0,
            "avg_post_resonance_score": (post_resonance_sum / observed) if observed else 0.0,
            "avg_post_goal_alignment_score": (post_goal_sum / observed) if observed else 0.0,
            # softening observability (advisory only)
            "softening_detected_count": softening_detected,
            "softening_neutral_count": softening_neutral,
            "softening_signal_counts": signal_counts,
        }

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

        # Stage 9b — Relational field observation (MVP, no routing side-effects)
        if self._relational_analyzer:
            try:
                snapshot = self._relational_analyzer.analyze(
                    text=text,
                    participants=list(item.get("participants") or []),
                    interaction_scope=str(
                        item.get("interaction_scope")
                        or item.get("_interaction_scope")
                        or "human-human"
                    ),
                    context={
                        "intent": item.get("_intent") or item.get("intent"),
                        "why": item.get("_why") or item.get("why"),
                        "cycle_id": item.get("_cycle_id"),
                    },
                )
                item["_relational_field"] = snapshot.to_dict()
                if self._graph_runtime and hasattr(
                    self._graph_runtime, "remember_relational_snapshot"
                ):
                    self._graph_runtime.remember_relational_snapshot(snapshot)
            except Exception as exc:
                logger.debug("ResonanceAgent: relational field analysis failed: %s", exc)

        # Stage 9c — Interaction alignment report (MVP, inspectable only)
        if self._alignment_analyzer:
            try:
                alignment_report = self._alignment_analyzer.analyze(
                    participants=list(item.get("participants") or []),
                    context={
                        "intent": item.get("_intent") or item.get("intent"),
                        "why": item.get("_why") or item.get("why"),
                        "interaction_scope": (
                            item.get("interaction_scope")
                            or item.get("_interaction_scope")
                            or "unknown"
                        ),
                        "cycle_id": item.get("_cycle_id"),
                    },
                )
                item["_alignment_report"] = alignment_report.to_dict()
            except Exception as exc:
                logger.debug("ResonanceAgent: alignment analysis failed: %s", exc)

        graph_decision = None
        available_backends: list[str] = []
        intent_tag = self._intent_tag(item)
        why_tag = self._why_tag(item)
        orientation_plan = None
        if self._control_center:
            try:
                orientation_plan = self._control_center.create_plan(
                    item,
                    thread_context=item.get("thread_context"),
                    intent=intent_tag,
                    why_tag=why_tag,
                )
                item["_network_plan"] = orientation_plan.to_dict()
                if orientation_plan.graph_decision:
                    item["_graph_runtime"] = orientation_plan.graph_decision
                    if orientation_plan.graph_decision.get("prior_answer"):
                        item["_graph_prior_answer"] = orientation_plan.graph_decision["prior_answer"]
                    if orientation_plan.graph_decision.get("prior_case"):
                        item["_graph_prior_case"] = orientation_plan.graph_decision["prior_case"]
                if orientation_plan.derived_module:
                    item["_derived_module"] = orientation_plan.derived_module
                if orientation_plan.path_decision:
                    item["_path_selection"] = orientation_plan.path_decision
                if orientation_plan.adequacy_report:
                    item["_adequacy_report"] = orientation_plan.adequacy_report
                if orientation_plan.observer_report:
                    item["_observer_report"] = orientation_plan.observer_report
                graph_meta = orientation_plan.graph_decision or {}
                graph_mode = graph_meta.get("mode")
                if graph_mode:
                    class _PlanGraphDecision:
                        def __init__(self, meta: dict):
                            self.mode = meta.get("mode")
                            self.matched_case_id = meta.get("matched_case_id")
                            self.similarity = meta.get("similarity")
                            self.prior_answer = meta.get("prior_answer")
                            self.prior_case = meta.get("prior_case")
                            self.reason = meta.get("reason")
                    graph_decision = _PlanGraphDecision(graph_meta)
                available_backends = orientation_plan.available_backends or []
            except Exception as exc:
                logger.debug("ResonanceAgent: network control center failed: %s", exc)

        if not available_backends and self._llm_backend is not None and hasattr(self._llm_backend, "backends"):
            available_backends = [
                name for name in ("gonka", "mimo", "cloud", "local")
                if name in getattr(self._llm_backend, "backends", {})
            ]

        derived_module = item.get("_derived_module")
        if derived_module is not None and hasattr(derived_module, "to_dict"):
            derived_module = derived_module.to_dict()

        path_decision = item.get("_path_selection")
        original_primary = None
        original_fallback = None
        if (
            self._path_selector
            and graph_decision
            and graph_decision.mode != "reuse"
            and derived_module is None
            and self._llm_backend is not None
            and hasattr(self._llm_backend, "backends")
            and path_decision is None
        ):
            try:
                default_backend = getattr(self._llm_backend, "primary", None)
                path_decision = self._path_selector.choose_route(
                    graph_mode=graph_decision.mode,
                    available_backends=available_backends,
                    default_backend=default_backend,
                    intent=intent_tag,
                    why_tag=why_tag,
                )
                item["_path_selection"] = path_decision.to_dict()
            except Exception as exc:
                logger.debug("ResonanceAgent: path selector failed: %s", exc)

        if path_decision and hasattr(path_decision, "to_dict"):
            item["_path_selection"] = path_decision.to_dict()
            selected_backend = path_decision.selected_backend
        elif isinstance(path_decision, dict):
            selected_backend = path_decision.get("selected_backend")
        else:
            selected_backend = None

        if self._graph_runtime and not (graph_decision and graph_decision.mode == "reuse"):
            try:
                self._graph_runtime.inject_resonance_hints(
                    item,
                    thread_context=item.get("thread_context"),
                    top_k=3,
                )
            except Exception as exc:
                logger.debug("ResonanceAgent: resonance hints injection failed: %s", exc)
                item["_resonance_hints"] = []

        if selected_backend and selected_backend != "cooperative" and hasattr(self._llm_backend, "primary"):
            original_primary = getattr(self._llm_backend, "primary", None)
            original_fallback = list(getattr(self._llm_backend, "fallback_chain", []))
            ordered_fallbacks = [
                backend
                for backend in original_fallback
                if backend != selected_backend
            ]
            self._llm_backend.primary = selected_backend
            self._llm_backend.fallback_chain = ordered_fallbacks

        cooperative_result = None
        if (
            self._cooperative_engine
            and path_decision
            and (
                (hasattr(path_decision, "route_key") and path_decision.route_key in {"full_run>local>gonka>mimo", "refine>local>gonka>mimo"})
                or (isinstance(path_decision, dict) and path_decision.get("route_key") in {"full_run>local>gonka>mimo", "refine>local>gonka>mimo"})
            )
        ):
            try:
                cooperative_route_key = path_decision.route_key if hasattr(path_decision, "route_key") else path_decision.get("route_key")
                cooperative_result = self._cooperative_engine.run(
                    item,
                    cooperative_route_key,
                    thread_context=item.get("thread_context"),
                    goal_vector=((item.get("_network_plan") or {}).get("goal_vector") or None),
                )
                item["_cooperative"] = cooperative_result.to_dict()
            except Exception as exc:
                logger.debug("ResonanceAgent: cooperative engine failed: %s", exc)
                cooperative_result = None

        # Phase 2 — build system prompt and call LLM
        t0 = time.perf_counter()
        if graph_decision and graph_decision.mode == "reuse" and graph_decision.prior_answer:
            final_output = graph_decision.prior_answer
            item["_llm_backend"] = {
                "provider": "graph_reuse",
                "model": "",
                "latency_ms": 0.0,
                "error": None,
                "was_fallback_used": False,
                "fallback_from": None,
                "fallback_to": None,
            }
        elif derived_module is not None:
            module_meta = derived_module.to_dict() if hasattr(derived_module, "to_dict") else dict(derived_module)
            derived_output = self._call_derived_module(item, module_meta)
            if derived_output:
                final_output = derived_output
            else:
                try:
                    final_output = self._call_llm(item)
                except Exception as exc:
                    logger.warning("ResonanceAgent: derived module fallback LLM call failed: %s", exc)
                    final_output = item.get("_copilot_output", {}).get("pre_prompt", "")
        elif cooperative_result and cooperative_result.success and cooperative_result.final_answer:
            final_output = cooperative_result.final_answer
            participant_backends = [p.get("backend") for p in cooperative_result.participants]
            item["_llm_backend"] = {
                "provider": "cooperative",
                "model": cooperative_result.route_key,
                "latency_ms": 0.0,
                "error": None,
                "was_fallback_used": False,
                "fallback_from": None,
                "fallback_to": None,
                "participants": participant_backends,
            }
            if original_primary is not None and hasattr(self._llm_backend, "primary"):
                self._llm_backend.primary = original_primary
                self._llm_backend.fallback_chain = original_fallback or []
        else:
            try:
                final_output = self._call_llm(item)
            except Exception as exc:
                logger.warning("ResonanceAgent: LLM call failed: %s", exc)
                final_output = item.get("_copilot_output", {}).get("pre_prompt", "")
            finally:
                if original_primary is not None and hasattr(self._llm_backend, "primary"):
                    self._llm_backend.primary = original_primary
                    self._llm_backend.fallback_chain = original_fallback or []
        generation_time = time.perf_counter() - t0

        # After LLM: update resonance_score with response quality signal
        base_score = item.get("_resonance_score", 0.5)
        response_score = self._rate_response(final_output, item)
        goal_alignment_score = self._goal_alignment_score(final_output, item)
        item["_goal_alignment_score"] = goal_alignment_score
        final_score = round((base_score * 0.55 + response_score * 0.25 + goal_alignment_score * 0.20), 3)
        item["_resonance_score"] = final_score
        self._record_alignment_outcome(
            item,
            response_text=final_output,
            response_score=response_score,
            goal_alignment_score=goal_alignment_score,
        )

        # Phase 2 — complete log cycle
        if self._logger and log_cycle_id:
            try:
                self._logger.complete_cycle(
                    cycle_id=log_cycle_id,
                    output=final_output,
                    generation_time=generation_time,
                    llm_metadata=item.get("_llm_backend"),
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

        if self._graph_runtime and final_output:
            try:
                llm_meta = item.get("_llm_backend") or {}
                contributors = []
                if cooperative_result and cooperative_result.participants:
                    for participant in cooperative_result.participants:
                        contributors.append(
                            {
                                "backend": participant.get("backend", "unknown"),
                                "model": participant.get("model", ""),
                                "role": participant.get("role", "answer"),
                            }
                        )
                else:
                    provider = llm_meta.get("provider")
                    model = llm_meta.get("model")
                    if provider or model:
                        contributors.append(
                            {
                                "backend": provider or "unknown",
                                "model": model or "",
                                "role": "answer",
                            }
                        )
                self._graph_runtime.remember_success(
                    item,
                    answer_text=final_output,
                    thread_context=item.get("thread_context"),
                    answer_quality={
                        "resonance_score": item.get("_resonance_score", 0.5),
                        "goal_alignment_score": item.get("_goal_alignment_score", 0.5),
                    },
                    contributors=contributors,
                )
            except Exception as exc:
                logger.debug("ResonanceAgent: graph remember failed: %s", exc)

        if self._trail_updater and _PathExecutionRecord:
            try:
                llm_meta = item.get("_llm_backend") or {}
                graph_meta = item.get("_graph_runtime") or {}
                route_key = "reuse" if graph_meta.get("mode") == "reuse" else None
                if not route_key:
                    route_key = (
                        (item.get("_path_selection") or {}).get("route_key")
                        or f"{graph_meta.get('mode', 'full_run')}>{llm_meta.get('provider', 'unknown')}"
                    )
                quality = {
                    "overall": item.get("_resonance_score", 0.5),
                    "resonance_score": item.get("_resonance_score", 0.5),
                    "goal_alignment_score": item.get("_goal_alignment_score", 0.5),
                }
                record = _PathExecutionRecord(
                    route_key=route_key,
                    question_text=item.get("text", ""),
                    graph_mode=graph_meta.get("mode", "full_run"),
                    selected_backend=str(llm_meta.get("provider", "unknown")),
                    quality=quality,
                    latency_ms=float(llm_meta.get("latency_ms") or generation_time * 1000),
                )
                route_stats, reward = self._trail_updater.update(record)
                item["_trail_route"] = route_stats.to_dict()
                item["_trail_reward"] = reward
            except Exception as exc:
                logger.debug("ResonanceAgent: trail update failed: %s", exc)

        if self._coalition_registry:
            try:
                path_meta = item.get("_path_selection") or {}
                route_key = path_meta.get("route_key")
                if route_key and route_key != "reuse" and not str(route_key).startswith("derived>"):
                    coalition = self._coalition_registry.update_after_run(
                        route_key=route_key,
                        quality_score=float(item.get("_resonance_score", 0.5) or 0.5),
                        success=bool(final_output),
                        intent=intent_tag,
                        why_tag=why_tag,
                    )
                    item["_coalition"] = coalition.to_dict()
            except Exception as exc:
                logger.debug("ResonanceAgent: coalition update failed: %s", exc)

        if self._derived_module_registry and final_output:
            try:
                quality_score = float(item.get("_resonance_score", 0.5) or 0.5)
                existing_module = item.get("_derived_module") or {}
                if existing_module.get("module_id"):
                    updated_module = self._derived_module_registry.mark_used(
                        existing_module["module_id"],
                        quality_score=quality_score,
                        success=bool(final_output),
                    )
                    if updated_module is not None:
                        item["_derived_module"] = updated_module.to_dict()
                else:
                    path_meta = item.get("_path_selection") or {}
                    route_key = path_meta.get("route_key") or ""
                    cooperative_like = ">" in route_key and route_key.count(">") >= 2
                    if cooperative_like and quality_score >= GRAPH_DERIVED_MODULE_MIN_QUALITY:
                        parent_coalition_id = ((item.get("_coalition") or {}).get("coalition_id") or route_key.replace(">", "-"))
                        preferred_backend = "local" if "local" in available_backends else (available_backends[0] if available_backends else "local")
                        module = self._derived_module_registry.create_or_update_from_success(
                            parent_coalition_id=parent_coalition_id,
                            source_route_key=route_key,
                            domain=intent_tag or "generic",
                            task_type=why_tag or "generic",
                            preferred_backend=preferred_backend,
                            policy_type="prompt_policy",
                            policy_text=self._build_derived_policy(item, final_output, route_key=route_key),
                            quality_score=quality_score,
                        )
                        item["_derived_module"] = module.to_dict()
            except Exception as exc:
                logger.debug("ResonanceAgent: derived module update failed: %s", exc)

        if self._care_cycle_runner:
            try:
                derived_meta = item.get("_derived_module") or {}
                module_id = derived_meta.get("module_id")
                if module_id:
                    care_result = self._care_cycle_runner.review(module_id)
                    if care_result is not None:
                        item["_care_cycle"] = care_result.to_dict()
                        refreshed = self._derived_module_registry.get_module(module_id) if self._derived_module_registry else None
                        if refreshed is not None:
                            item["_derived_module"] = refreshed.to_dict()
            except Exception as exc:
                logger.debug("ResonanceAgent: care cycle failed: %s", exc)

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
        if self._llm_backend:
            response = self._llm_backend.generate(
                messages=[{"role": "user", "content": user}],
                system_prompt=system,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                metadata={
                    "cycle_id": item.get("_cycle_id"),
                    "source": item.get("source", "resonance_agent"),
                },
            )
            item["_llm_backend"] = response.to_dict()
            if response.ok:
                return response.text
            raise RuntimeError(response.error or "LLM backend failed")
        if self._llm_fn:
            text = self._llm_fn(user, system)
            item["_llm_backend"] = {
                "provider": "callable",
                "model": "",
                "latency_ms": 0.0,
                "error": None,
                "was_fallback_used": False,
                "fallback_from": None,
                "fallback_to": None,
            }
            return text
        # Dry-run: return the pre_prompt so the caller can see the overlay
        copilot = item.get("_copilot_output") or {}
        item["_llm_backend"] = {
            "provider": "dry_run",
            "model": "",
            "latency_ms": 0.0,
            "error": None,
            "was_fallback_used": False,
            "fallback_from": None,
            "fallback_to": None,
        }
        return copilot.get("pre_prompt") or "ответь по существу"

    def _intent_tag(self, item: dict) -> str | None:
        intent = item.get("_intent", item.get("intent"))
        if isinstance(intent, dict):
            value = intent.get("type") or intent.get("intent")
            return str(value).strip() if value else None
        return str(intent).strip() if intent else None

    def _why_tag(self, item: dict) -> str | None:
        strategy = item.get("_why_strategy") or {}
        if isinstance(strategy, dict):
            value = strategy.get("micro_trigger") or strategy.get("strategy")
            if value:
                return str(value).strip()
        why = item.get("_why")
        if isinstance(why, dict):
            value = why.get("reason") or why.get("why")
            if value:
                return str(value).strip()
        return str(why).strip() if isinstance(why, str) and why else None

    def _build_derived_policy(self, item: dict, final_output: str, *, route_key: str) -> str:
        intent_tag = self._intent_tag(item) or "generic"
        why_tag = self._why_tag(item) or "generic"
        thread_context = item.get("thread_context") or self._orientation or ""
        style_example = (final_output or "").strip()
        if len(style_example) > 400:
            style_example = style_example[:400].rstrip() + "..."
        parts = [
            "Role: derived micro-module.",
            "Answer the interview question briefly, precisely, and without fluff.",
            "Do not invent numbers, projects, cases, or facts.",
            "Keep the response aligned with the question, why-context, and conversation thread.",
            f"Domain: {intent_tag}.",
            f"Task type: {why_tag}.",
            f"Parent route: {route_key}.",
        ]
        if thread_context:
            parts.append(f"Conversation context:\\n{thread_context}")
        if style_example:
            parts.append(f"Style reference from a successful answer:\\n{style_example}")
        return "\\n\\n".join(parts)

    def _call_derived_module(self, item: dict, module_meta: dict) -> str | None:
        if self._llm_backend is None or not hasattr(self._llm_backend, "backends"):
            return None
        backend_name = str(module_meta.get("preferred_backend") or "local")
        backend = getattr(self._llm_backend, "backends", {}).get(backend_name)
        if backend is None:
            return None
        system_prompt = str(module_meta.get("policy_text") or "").strip()
        if not system_prompt:
            return None
        prior_answer = item.get("_graph_prior_answer")
        if prior_answer:
            system_prompt += f"\\n\\nBase draft from memory:\\n{prior_answer}"
        response = backend.generate(
            messages=[{"role": "user", "content": item.get("text", "")}],
            system_prompt=system_prompt,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            metadata={
                "cycle_id": item.get("_cycle_id"),
                "source": "derived_module",
                "module_id": module_meta.get("module_id"),
            },
        )
        if not response.ok:
            return None
        response_dict = response.to_dict()
        response_dict["provider"] = "derived_module"
        response_dict["model"] = str(module_meta.get("module_id") or response.model)
        response_dict["derived_backend"] = backend_name
        item["_llm_backend"] = response_dict
        return response.text

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

        graph = item.get("_graph_runtime") or {}
        prior_answer = item.get("_graph_prior_answer")
        path_selection = item.get("_path_selection") or {}
        network_plan = item.get("_network_plan") or {}
        need_profile = network_plan.get("need_profile") or {}
        goal_vector = network_plan.get("goal_vector") or {}
        if graph.get("mode") == "refine" and prior_answer:
            parts.append(
                "Есть похожий прошлый кейс. Используй его как черновую базу, "
                "но адаптируй под текущий вопрос и контекст."
            )
            parts.append(f"Base draft from memory:\n{prior_answer}")
        if path_selection.get("route_key"):
            parts.append(
                "Маршрут решения выбран по истории успешных путей: "
                f"{path_selection.get('route_key')}."
            )
        resonance_hints = item.get("_resonance_hints") or []
        if resonance_hints:
            hint_lines: list[str] = []
            for idx, hint in enumerate(resonance_hints[:3], start=1):
                if not isinstance(hint, dict):
                    continue
                fields = [
                    f"intent={hint.get('intent')}" if hint.get("intent") else None,
                    f"why={hint.get('why')}" if hint.get("why") else None,
                    f"route={hint.get('route_key')}" if hint.get("route_key") else None,
                    f"path={hint.get('causal_path')}" if hint.get("causal_path") else None,
                    f"pattern={hint.get('answer_pattern')}" if hint.get("answer_pattern") else None,
                    (
                        f"res={float(hint.get('resonance_score')):.2f}"
                        if hint.get("resonance_score") is not None
                        else None
                    ),
                    (
                        f"align={float(hint.get('alignment_score')):.2f}"
                        if hint.get("alignment_score") is not None
                        else None
                    ),
                ]
                compact = "; ".join(part for part in fields if part)
                if compact:
                    hint_lines.append(f"{idx}) {compact}")
            if hint_lines:
                parts.append(
                    "Слабые подсказки из resonance-memory (используй как soft guidance, не копируй дословно):\n"
                    + "\n".join(hint_lines)
                )
        relational = item.get("_relational_field") or {}
        try:
            tension_score = float(relational.get("tension_score", 0.0) or 0.0)
            alignment_score = float(relational.get("alignment_score", 0.0) or 0.0)
        except (TypeError, ValueError, AttributeError):
            tension_score = 0.0
            alignment_score = 0.0
        if (
            isinstance(relational, dict)
            and tension_score > 0.7
            and alignment_score < 0.4
        ):
            parts.append(
                "В поле есть напряжение. Не дави на решение сразу; "
                "сначала признай разницу восприятия и снизь конфликтность формулировок."
            )
        alignment_report = item.get("_alignment_report") or {}
        alignment_guidance = self._build_alignment_guidance(alignment_report)
        item["_alignment_guidance"] = alignment_guidance
        if alignment_guidance:
            parts.append(alignment_guidance)
        if need_profile:
            parts.append(
                "Профиль потребности сети: "
                f"priority={need_profile.get('priority')}, "
                f"route_bias={need_profile.get('route_bias')}, "
                f"compute_budget={need_profile.get('compute_budget')}."
            )
        if goal_vector:
            parts.append(
                "Целевой профиль ответа: "
                f"style={goal_vector.get('style')}, "
                f"strategy_bias={goal_vector.get('strategy_bias')}, "
                f"target_relevance={goal_vector.get('target_relevance')}, "
                f"target_thread_alignment={goal_vector.get('target_thread_alignment')}, "
                f"target_hallucination_max={goal_vector.get('target_hallucination_max')}, "
                f"target_latency_ms={goal_vector.get('target_latency_ms')}."
            )
            style = goal_vector.get("style")
            strategy_bias = goal_vector.get("strategy_bias")
            if style == "concise":
                parts.append("Отвечай кратко, плотно и без лишней воды.")
            elif style == "careful":
                parts.append("Отвечай осторожно, не выдумывай детали и явно держи связь с вопросом.")
            elif style == "structured":
                parts.append("Строй ответ структурно: решение, причина, trade-off, итог.")
            if strategy_bias == "speed_first":
                parts.append("Приоритет: быстрый и ясный ответ без лишних ветвлений.")
            elif strategy_bias == "verify_first":
                parts.append("Приоритет: точность и проверяемость важнее скорости и красноречия.")
            elif strategy_bias == "cooperative_reasoning":
                parts.append("Приоритет: показать рассуждение и trade-offs, а не просто вывод.")
            elif strategy_bias == "grounded":
                parts.append("Приоритет: grounded answer without invented metrics or fake projects.")

        return "\n\n".join(parts)

    def _build_alignment_guidance(self, alignment_report: dict) -> str:
        if not isinstance(alignment_report, dict):
            return ""
        suggested_mode = str(alignment_report.get("suggested_mode") or "steady")
        requires_softening = bool(alignment_report.get("requires_softening", False))
        requires_clarification = bool(alignment_report.get("requires_clarification", False))
        requires_grounding = bool(alignment_report.get("requires_grounding", False))

        guidance_parts: list[str] = []
        if requires_softening:
            guidance_parts.append(
                "Alignment guidance: начни с мягкой валидации позиции собеседника, затем предложи следующий шаг."
            )
        if requires_clarification:
            guidance_parts.append(
                "Alignment guidance: добавь короткий уточняющий фрейм, чтобы синхронизировать ожидания перед решением."
            )
        if requires_grounding:
            guidance_parts.append(
                "Alignment guidance: опирайся на факты из вопроса и не форсируй вывод без контекста."
            )
        if not guidance_parts and suggested_mode in {"soften", "clarify", "ground"}:
            guidance_parts.append(
                f"Alignment guidance: используй режим {suggested_mode} и держи ответ кооперативным."
            )
        return " ".join(guidance_parts)

    @staticmethod
    def _run_softening_detector(text: str) -> "dict":
        """
        Run language-agnostic softening detector (advisory only).
        Falls back to a neutral result if the module is unavailable.
        """
        if _SOFTENING_DETECTOR_OK and _analyze_softening_signals is not None:
            try:
                result = _analyze_softening_signals(text)
                return result.to_dict()
            except Exception as exc:
                logger.debug("softening_detector failed: %s", exc)
        # Graceful fallback — keeps backward-compat with old bool field
        return {
            "softening_detected": False,
            "score": 0.0,
            "signals": [],
            "reason": "detector_unavailable",
        }

    def _record_alignment_outcome(
        self,
        item: dict,
        *,
        response_text: str,
        response_score: float,
        goal_alignment_score: float,
    ) -> None:
        report = item.get("_alignment_report") or {}
        guidance = str(item.get("_alignment_guidance") or "")
        pre_tension_score = 0.0
        if isinstance(report, dict):
            try:
                pre_tension_score = float(report.get("tension_score", 0.0) or 0.0)
            except (TypeError, ValueError):
                pre_tension_score = 0.0

        # Language-agnostic softening detection (replaces old Russian-only heuristic)
        softening = self._run_softening_detector(response_text)
        response_softened: bool = bool(softening.get("softening_detected", False))
        softening_signals: list = list(softening.get("signals") or [])
        effect_reason: str | None = softening.get("reason")

        guidance_applied = bool(guidance)
        effect_observed = guidance_applied and (
            response_softened
            or goal_alignment_score >= 0.65
            or (response_score >= 0.62 and pre_tension_score >= 0.45)
        )

        item["_alignment_outcome"] = {
            "guidance_added": guidance_applied,
            "pre_tension_score": round(pre_tension_score, 3),
            "post_resonance_score": round(float(item.get("_resonance_score", 0.0) or 0.0), 3),
            "post_goal_alignment_score": round(float(goal_alignment_score or 0.0), 3),
            "response_softened": response_softened,
            "softening_score": round(float(softening.get("score", 0.0) or 0.0), 3),
            "softening_signals": softening_signals,
            "effect_reason": effect_reason,
            "guidance_effective": effect_observed,
        }

        with self._alignment_metrics_lock:
            self._alignment_outcome_metrics["observed_cycles"] = int(
                self._alignment_outcome_metrics.get("observed_cycles", 0) or 0
            ) + 1
            self._alignment_outcome_metrics["_pre_tension_sum"] = float(
                self._alignment_outcome_metrics.get("_pre_tension_sum", 0.0) or 0.0
            ) + pre_tension_score
            self._alignment_outcome_metrics["_post_resonance_sum"] = float(
                self._alignment_outcome_metrics.get("_post_resonance_sum", 0.0) or 0.0
            ) + float(item.get("_resonance_score", 0.0) or 0.0)
            self._alignment_outcome_metrics["_post_goal_alignment_sum"] = float(
                self._alignment_outcome_metrics.get("_post_goal_alignment_sum", 0.0) or 0.0
            ) + float(goal_alignment_score or 0.0)
            # softening counters
            if response_softened:
                self._alignment_outcome_metrics["softening_detected_count"] = int(
                    self._alignment_outcome_metrics.get("softening_detected_count", 0) or 0
                ) + 1
            else:
                self._alignment_outcome_metrics["softening_neutral_count"] = int(
                    self._alignment_outcome_metrics.get("softening_neutral_count", 0) or 0
                ) + 1
            for sig in softening_signals:
                key = f"_signal_{sig}"
                self._alignment_outcome_metrics[key] = int(
                    self._alignment_outcome_metrics.get(key, 0) or 0
                ) + 1
            if guidance_applied:
                self._alignment_outcome_metrics["guidance_added_count"] = int(
                    self._alignment_outcome_metrics.get("guidance_added_count", 0) or 0
                ) + 1
                if effect_observed:
                    self._alignment_outcome_metrics["guidance_effective_count"] = int(
                        self._alignment_outcome_metrics.get("guidance_effective_count", 0) or 0
                    ) + 1
                else:
                    self._alignment_outcome_metrics["guidance_no_effect_count"] = int(
                        self._alignment_outcome_metrics.get("guidance_no_effect_count", 0) or 0
                    ) + 1

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

        # Anchor citation bonus — also record which anchors were cited (BUG-15 fix)
        anchor_bonus = 0.0
        if anchor_ctx:
            resp_lower = response.lower()
            cited = [a for a in anchor_ctx if a and a.split(":")[0].lower() in resp_lower]
            if cited:
                anchor_bonus = 0.10
            item["_cited_anchors"] = cited  # stored for _build_output

        return round(min(1.0, length_score * 0.9 + anchor_bonus), 3)

    def _goal_alignment_score(self, response: str, item: dict) -> float:
        goal_vector = ((item.get("_network_plan") or {}).get("goal_vector") or {})
        if not response:
            return 0.2
        if not goal_vector:
            return 0.5

        text = response.strip()
        lower = text.lower()
        words = len(text.split())
        score = 0.25

        style = goal_vector.get("style")
        if style == "concise":
            score += 0.35 if words <= 60 else 0.15 if words <= 90 else 0.0
        elif style == "careful":
            risky_markers = any(token in text for token in ("%", "$", "x", "X"))
            score += 0.30 if not risky_markers else 0.10
        elif style == "structured":
            structured = any(sep in text for sep in ("\n", ":", ";", " - "))
            score += 0.35 if structured else 0.15

        strategy_bias = goal_vector.get("strategy_bias")
        if strategy_bias == "speed_first":
            score += 0.25 if words <= 45 else 0.10
        elif strategy_bias == "verify_first":
            score += 0.25 if not any(ch.isdigit() for ch in text) else 0.10
        elif strategy_bias == "cooperative_reasoning":
            score += 0.25 if any(marker in lower for marker in ("потому что", "однако", "но", "компромисс", "trade-off")) else 0.10
        elif strategy_bias == "grounded":
            score += 0.25 if not any(ch.isdigit() for ch in text) else 0.05

        target_latency_ms = float(goal_vector.get("target_latency_ms") or 0.0)
        if target_latency_ms and target_latency_ms <= 5500:
            score += 0.10 if words <= 50 else 0.0

        return round(min(1.0, score), 3)

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
        llm_meta  = item.get("_llm_backend") or {}
        path_meta = item.get("_path_selection") or {}
        graph_meta = item.get("_graph_runtime") or {}
        trail_meta = item.get("_trail_route") or {}
        coalition_meta = item.get("_coalition") or {}
        derived_meta = item.get("_derived_module") or {}
        care_meta = item.get("_care_cycle") or {}
        orientation_meta = item.get("_network_plan") or {}
        adequacy_meta = item.get("_adequacy_report") or {}
        observer_meta = item.get("_observer_report") or {}
        alignment_meta = item.get("_alignment_report") or {}
        alignment_outcome = item.get("_alignment_outcome") or {}
        fallback_route_key = (
            "reuse"
            if graph_meta.get("mode") == "reuse"
            else f"{graph_meta.get('mode', 'full_run')}>{llm_meta.get('provider', 'unknown')}"
        )

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
            # BUG-15 fix: return only anchors actually cited in the LLM output,
            # not the full context list (use _cited_anchors set by _rate_response).
            "anchor_used":     item.get("_cited_anchors") or [],
            # Body cues for UI overlay
            "empathy_cues":    copilot.get("empathy_cues"),
            "pre_prompt":      copilot.get("pre_prompt", ""),
            "intervention_level": copilot.get("intervention_level", "low"),
            # Interviewer model
            "interviewer_profile": item.get("_interviewer_profile"),
            # Output
            "final_output":    final_output,
            "generation_time": round(generation_time, 4),
            "llm_provider":    llm_meta.get("provider"),
            "llm_model":       llm_meta.get("model"),
            "llm_latency_ms":  llm_meta.get("latency_ms"),
            "llm_error":       llm_meta.get("error"),
            "llm_fallback_used": llm_meta.get("was_fallback_used", False),
            "llm_fallback_from": llm_meta.get("fallback_from"),
            "llm_fallback_to": llm_meta.get("fallback_to"),
            "graph_mode":      graph_meta.get("mode"),
            "graph_matched_case_id": graph_meta.get("matched_case_id"),
            "graph_similarity": graph_meta.get("similarity"),
            "graph_reason":    graph_meta.get("reason"),
            "was_reused":      graph_meta.get("mode") == "reuse",
            "was_refined":     graph_meta.get("mode") == "refine",
            "orientation_reason": orientation_meta.get("reason"),
            "orientation_confidence": orientation_meta.get("confidence"),
            "orientation_route_key": orientation_meta.get("route_key"),
            "orientation_resonance_signal": orientation_meta.get("resonance_signal"),
            "orientation_resonance_unit_count": (orientation_meta.get("resonance_signal") or {}).get("count", 0),
            "need_profile": orientation_meta.get("need_profile"),
            "need_priority": (orientation_meta.get("need_profile") or {}).get("priority"),
            "need_route_bias": (orientation_meta.get("need_profile") or {}).get("route_bias"),
            "goal_vector": orientation_meta.get("goal_vector"),
            "goal_style": (orientation_meta.get("goal_vector") or {}).get("style"),
            "goal_strategy_bias": (orientation_meta.get("goal_vector") or {}).get("strategy_bias"),
            "goal_alignment_score": item.get("_goal_alignment_score"),
            "adequacy_status": adequacy_meta.get("status"),
            "adequacy_risks": adequacy_meta.get("risks"),
            "adequacy_recommendations": adequacy_meta.get("recommendations"),
            "observer_status": observer_meta.get("status"),
            "observer_summary": observer_meta.get("summary"),
            "alignment_report": alignment_meta,
            "alignment_outcome": alignment_outcome,
            "alignment_observability": self.get_alignment_outcome_metrics(),
            "route_key":       path_meta.get("route_key") or trail_meta.get("route_key") or fallback_route_key,
            "route_reason":    path_meta.get("reason") or "trail-fallback",
            "route_pheromone_weight": path_meta.get("pheromone_weight", trail_meta.get("pheromone_weight")),
            "exploration_used": path_meta.get("exploration_used", False),
            "trail_updated":   bool(trail_meta),
            "route_reward":    item.get("_trail_reward"),
            "coalition_used":  bool(coalition_meta),
            "coalition_route_key": coalition_meta.get("route_key"),
            "coalition_trust_score": coalition_meta.get("trust_score"),
            "derived_module_used": bool(derived_meta),
            "derived_module_id": derived_meta.get("module_id"),
            "derived_module_parent_coalition": derived_meta.get("parent_coalition_id"),
            "derived_module_backend": ((item.get("_llm_backend") or {}).get("derived_backend") or derived_meta.get("preferred_backend")),
            "care_cycle_used": bool(care_meta),
            "care_cycle_action": care_meta.get("action"),
            "care_cycle_state": care_meta.get("state"),
            "care_cycle_reason": care_meta.get("reason"),
            "cooperative_used": bool(item.get("_cooperative")),
            "cooperative_route_key": (item.get("_cooperative") or {}).get("route_key"),
            "cooperative_participants": (item.get("_cooperative") or {}).get("participants"),
            "cooperative_success": (item.get("_cooperative") or {}).get("success", False),
            "cooperative_final_source": ((item.get("_cooperative") or {}).get("metadata") or {}).get("final_source"),
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
