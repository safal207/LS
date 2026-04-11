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
* Thread-safe: ``OperatorProfile`` and ``ResonanceLearner`` are guarded
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
import json
import threading
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Callable, List, Optional

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
from shared.operator_schema import ensure_operator_item

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy imports (all optional, graceful fallback)
# ---------------------------------------------------------------------------

try:
    from intent.operator_strategy import analyze_operator_strategy as _analyze
    _STRATEGY_OK = True
except Exception:
    _STRATEGY_OK = False
    _analyze = None  # type: ignore[assignment]

try:
    from intent.operator_profile import OperatorProfile as _OperatorProfile
    _PROFILE_OK = True
except Exception:
    _PROFILE_OK = False
    _OperatorProfile = None  # type: ignore[assignment]

try:
    from intent.operator_empathy import EmpathyNegotiationLayer as _EmpathyLayer
    _EMPATHY_OK = True
except Exception:
    _EMPATHY_OK = False
    _EmpathyLayer = None  # type: ignore[assignment]

try:
    from intent.operator_response_assembler import OperatorResponseAssembler as _Copilot
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
    from modules.agent.relational_policy_engine import (
        evaluate_relational_policy as _evaluate_relational_policy,
    )
    _RELATIONAL_POLICY_OK = True
except ImportError:
    try:
        from agent.relational_policy_engine import (
            evaluate_relational_policy as _evaluate_relational_policy,
        )
        _RELATIONAL_POLICY_OK = True
    except Exception:
        _RELATIONAL_POLICY_OK = False
        _evaluate_relational_policy = None  # type: ignore[assignment]
except Exception:
    _RELATIONAL_POLICY_OK = False
    _evaluate_relational_policy = None  # type: ignore[assignment]

try:
    from ls.cognition.council_contribution_ledger import (
        CouncilContributionLedger as _CouncilContributionLedger,
        CouncilDecision as _CouncilDecision,
        CouncilGoal as _CouncilGoal,
        CouncilNetworkContext as _CouncilNetworkContext,
        CouncilOutcome as _CouncilOutcome,
        CouncilParticipant as _CouncilParticipant,
    )
    _COUNCIL_LEDGER_OK = True
except Exception:
    _COUNCIL_LEDGER_OK = False
    _CouncilContributionLedger = None  # type: ignore[assignment]
    _CouncilDecision = None  # type: ignore[assignment]
    _CouncilGoal = None  # type: ignore[assignment]
    _CouncilNetworkContext = None  # type: ignore[assignment]
    _CouncilOutcome = None  # type: ignore[assignment]
    _CouncilParticipant = None  # type: ignore[assignment]

try:
    from cel.council_sync import apply_council_ledger_to_cel as _apply_council_ledger_to_cel
    from cel.council_sync import quality_score_from_council_outcome as _quality_score_from_council_outcome
    from cel.contribution_api import ContributionLedger as _CELContributionLedger
    from cel.reputation_engine import ReputationEngine as _CELReputationEngine
    _COUNCIL_CEL_SYNC_OK = True
except Exception:
    try:
        from modules.cel.council_sync import apply_council_ledger_to_cel as _apply_council_ledger_to_cel
        from modules.cel.council_sync import quality_score_from_council_outcome as _quality_score_from_council_outcome
        from modules.cel.contribution_api import ContributionLedger as _CELContributionLedger
        from modules.cel.reputation_engine import ReputationEngine as _CELReputationEngine
        _COUNCIL_CEL_SYNC_OK = True
    except Exception:
        _COUNCIL_CEL_SYNC_OK = False
        _apply_council_ledger_to_cel = None  # type: ignore[assignment]
        _quality_score_from_council_outcome = None  # type: ignore[assignment]
        _CELContributionLedger = None  # type: ignore[assignment]
        _CELReputationEngine = None  # type: ignore[assignment]

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
    from agent.alignment_memory import (
        AlignmentMemoryMetrics as _AlignmentMemoryMetrics,
        AlignmentMemoryUnit as _AlignmentMemoryUnit,
        append_alignment_memory_unit as _append_alignment_memory_unit,
        build_alignment_memory_hint as _build_alignment_memory_hint,
        build_alignment_memory_unit as _build_alignment_memory_unit,
        find_relevant_alignment_units as _find_relevant_alignment_units,
        should_store_alignment_memory_unit as _should_store_alignment_memory_unit,
    )
    _ALIGNMENT_MEMORY_OK = True
except ImportError:
    try:
        from modules.agent.alignment_memory import (
            AlignmentMemoryMetrics as _AlignmentMemoryMetrics,
            AlignmentMemoryUnit as _AlignmentMemoryUnit,
            append_alignment_memory_unit as _append_alignment_memory_unit,
            build_alignment_memory_hint as _build_alignment_memory_hint,
            build_alignment_memory_unit as _build_alignment_memory_unit,
            find_relevant_alignment_units as _find_relevant_alignment_units,
            should_store_alignment_memory_unit as _should_store_alignment_memory_unit,
        )
        _ALIGNMENT_MEMORY_OK = True
    except ImportError:
        _ALIGNMENT_MEMORY_OK = False
        _AlignmentMemoryMetrics = None  # type: ignore[assignment,misc]
        _AlignmentMemoryUnit = None  # type: ignore[assignment,misc]
        _append_alignment_memory_unit = None  # type: ignore[assignment]
        _build_alignment_memory_hint = None  # type: ignore[assignment]
        _build_alignment_memory_unit = None  # type: ignore[assignment]
        _find_relevant_alignment_units = None  # type: ignore[assignment]
        _should_store_alignment_memory_unit = None  # type: ignore[assignment]

try:
    from agent.alignment_digest import (
        AlignmentDigestMetrics as _AlignmentDigestMetrics,
        build_alignment_digest as _build_alignment_digest,
    )
    _ALIGNMENT_DIGEST_OK = True
except ImportError:
    try:
        from modules.agent.alignment_digest import (
            AlignmentDigestMetrics as _AlignmentDigestMetrics,
            build_alignment_digest as _build_alignment_digest,
        )
        _ALIGNMENT_DIGEST_OK = True
    except ImportError:
        _ALIGNMENT_DIGEST_OK = False
        _AlignmentDigestMetrics = None  # type: ignore[assignment,misc]
        _build_alignment_digest = None  # type: ignore[assignment]

try:
    from agent.alignment_success_patterns import (
        AlignmentSuccessPatternMetrics as _AlignmentSuccessPatternMetrics,
        build_alignment_success_patterns as _build_alignment_success_patterns,
    )
    _ALIGNMENT_SUCCESS_PATTERNS_OK = True
except ImportError:
    try:
        from modules.agent.alignment_success_patterns import (
            AlignmentSuccessPatternMetrics as _AlignmentSuccessPatternMetrics,
            build_alignment_success_patterns as _build_alignment_success_patterns,
        )
        _ALIGNMENT_SUCCESS_PATTERNS_OK = True
    except ImportError:
        _ALIGNMENT_SUCCESS_PATTERNS_OK = False
        _AlignmentSuccessPatternMetrics = None  # type: ignore[assignment,misc]
        _build_alignment_success_patterns = None  # type: ignore[assignment]

try:
    from agent.alignment_strategy_recommender import (
        AlignmentStrategyRecommendationMetrics as _AlignmentStrategyRecommendationMetrics,
        build_alignment_strategy_recommendations as _build_alignment_strategy_recommendations,
    )
    _ALIGNMENT_RECOMMENDER_OK = True
except ImportError:
    try:
        from modules.agent.alignment_strategy_recommender import (
            AlignmentStrategyRecommendationMetrics as _AlignmentStrategyRecommendationMetrics,
            build_alignment_strategy_recommendations as _build_alignment_strategy_recommendations,
        )
        _ALIGNMENT_RECOMMENDER_OK = True
    except ImportError:
        _ALIGNMENT_RECOMMENDER_OK = False
        _AlignmentStrategyRecommendationMetrics = None  # type: ignore[assignment,misc]
        _build_alignment_strategy_recommendations = None  # type: ignore[assignment]

try:
    from agent.alignment_strategy_feedback import (
        AlignmentStrategyFeedbackMetrics as _AlignmentStrategyFeedbackMetrics,
        build_strategy_feedback_summary as _build_strategy_feedback_summary,
        build_strategy_outcome_feedback as _build_strategy_outcome_feedback,
    )
    _ALIGNMENT_FEEDBACK_OK = True
except ImportError:
    try:
        from modules.agent.alignment_strategy_feedback import (
            AlignmentStrategyFeedbackMetrics as _AlignmentStrategyFeedbackMetrics,
            build_strategy_feedback_summary as _build_strategy_feedback_summary,
            build_strategy_outcome_feedback as _build_strategy_outcome_feedback,
        )
        _ALIGNMENT_FEEDBACK_OK = True
    except ImportError:
        _ALIGNMENT_FEEDBACK_OK = False
        _AlignmentStrategyFeedbackMetrics = None  # type: ignore[assignment,misc]
        _build_strategy_feedback_summary = None  # type: ignore[assignment]
        _build_strategy_outcome_feedback = None  # type: ignore[assignment]


try:
    from agent.alignment_strategy_calibration import (
        AlignmentStrategyCalibrationMetrics as _AlignmentStrategyCalibrationMetrics,
        build_strategy_calibration_summary as _build_strategy_calibration_summary,
    )
    _ALIGNMENT_CALIBRATION_OK = True
except ImportError:
    try:
        from modules.agent.alignment_strategy_calibration import (
            AlignmentStrategyCalibrationMetrics as _AlignmentStrategyCalibrationMetrics,
            build_strategy_calibration_summary as _build_strategy_calibration_summary,
        )
        _ALIGNMENT_CALIBRATION_OK = True
    except ImportError:
        _ALIGNMENT_CALIBRATION_OK = False
        _AlignmentStrategyCalibrationMetrics = None  # type: ignore[assignment,misc]
        _build_strategy_calibration_summary = None  # type: ignore[assignment]

try:
    from agent.alignment_strategy_aggregation import (
        AlignmentStrategyAggregationMetrics as _AlignmentStrategyAggregationMetrics,
        build_strategy_feedback_aggregation_summary as _build_aggregation_summary,
        build_pattern_feedback_stats as _build_pattern_feedback_stats,
        build_strategy_feedback_stats as _build_strategy_feedback_stats,
    )
    _ALIGNMENT_AGGREGATION_OK = True
except ImportError:
    try:
        from modules.agent.alignment_strategy_aggregation import (
            AlignmentStrategyAggregationMetrics as _AlignmentStrategyAggregationMetrics,
            build_strategy_feedback_aggregation_summary as _build_aggregation_summary,
            build_pattern_feedback_stats as _build_pattern_feedback_stats,
            build_strategy_feedback_stats as _build_strategy_feedback_stats,
        )
        _ALIGNMENT_AGGREGATION_OK = True
    except ImportError:
        _ALIGNMENT_AGGREGATION_OK = False
        _AlignmentStrategyAggregationMetrics = None  # type: ignore[assignment,misc]
        _build_aggregation_summary = None  # type: ignore[assignment]
        _build_pattern_feedback_stats = None  # type: ignore[assignment]
        _build_strategy_feedback_stats = None  # type: ignore[assignment]

try:
    from agent.alignment_strategy_reputation import (
        AlignmentStrategyReputationMetrics as _AlignmentStrategyReputationMetrics,
        build_strategy_reputation_overlay as _build_strategy_reputation_overlay,
    )
    _ALIGNMENT_REPUTATION_OK = True
except ImportError:
    try:
        from modules.agent.alignment_strategy_reputation import (
            AlignmentStrategyReputationMetrics as _AlignmentStrategyReputationMetrics,
            build_strategy_reputation_overlay as _build_strategy_reputation_overlay,
        )
        _ALIGNMENT_REPUTATION_OK = True
    except ImportError:
        _ALIGNMENT_REPUTATION_OK = False
        _AlignmentStrategyReputationMetrics = None  # type: ignore[assignment,misc]
        _build_strategy_reputation_overlay = None  # type: ignore[assignment]

try:
    from agent.alignment_recommendation_adoption import (
        AlignmentRecommendationAdoptionMetrics as _AlignmentRecommendationAdoptionMetrics,
        build_recommendation_adoption_summary as _build_adoption_summary,
        build_recommendation_adoption_trace as _build_adoption_trace,
    )
    _ALIGNMENT_ADOPTION_OK = True
except ImportError:
    try:
        from modules.agent.alignment_recommendation_adoption import (
            AlignmentRecommendationAdoptionMetrics as _AlignmentRecommendationAdoptionMetrics,
            build_recommendation_adoption_summary as _build_adoption_summary,
            build_recommendation_adoption_trace as _build_adoption_trace,
        )
        _ALIGNMENT_ADOPTION_OK = True
    except ImportError:
        _ALIGNMENT_ADOPTION_OK = False
        _AlignmentRecommendationAdoptionMetrics = None  # type: ignore[assignment,misc]
        _build_adoption_summary = None  # type: ignore[assignment]
        _build_adoption_trace = None  # type: ignore[assignment]

try:
    from agent.alignment_strategy_playbook import (
        AlignmentStrategyPlaybookMetrics as _AlignmentStrategyPlaybookMetrics,
        build_alignment_strategy_playbook as _build_alignment_strategy_playbook,
    )
    _ALIGNMENT_PLAYBOOK_OK = True
except ImportError:
    try:
        from modules.agent.alignment_strategy_playbook import (
            AlignmentStrategyPlaybookMetrics as _AlignmentStrategyPlaybookMetrics,
            build_alignment_strategy_playbook as _build_alignment_strategy_playbook,
        )
        _ALIGNMENT_PLAYBOOK_OK = True
    except ImportError:
        _ALIGNMENT_PLAYBOOK_OK = False
        _AlignmentStrategyPlaybookMetrics = None  # type: ignore[assignment,misc]
        _build_alignment_strategy_playbook = None  # type: ignore[assignment]

try:
    from agent.multi_party_alignment import (
        MultiPartyAlignmentMetrics as _MultiPartyAlignmentMetrics,
        build_multi_party_alignment_state as _build_multi_party_alignment_state,
    )
    _MULTI_PARTY_ALIGNMENT_OK = True
except ImportError:
    try:
        from modules.agent.multi_party_alignment import (
            MultiPartyAlignmentMetrics as _MultiPartyAlignmentMetrics,
            build_multi_party_alignment_state as _build_multi_party_alignment_state,
        )
        _MULTI_PARTY_ALIGNMENT_OK = True
    except ImportError:
        _MULTI_PARTY_ALIGNMENT_OK = False
        _MultiPartyAlignmentMetrics = None  # type: ignore[assignment,misc]
        _build_multi_party_alignment_state = None  # type: ignore[assignment]

try:
    from agent.bridge_graph import (
        BridgeGraphMetrics as _BridgeGraphMetrics,
        build_bridge_graph_state as _build_bridge_graph_state,
    )
    _BRIDGE_GRAPH_OK = True
except ImportError:
    try:
        from modules.agent.bridge_graph import (
            BridgeGraphMetrics as _BridgeGraphMetrics,
            build_bridge_graph_state as _build_bridge_graph_state,
        )
        _BRIDGE_GRAPH_OK = True
    except ImportError:
        _BRIDGE_GRAPH_OK = False
        _BridgeGraphMetrics = None  # type: ignore[assignment,misc]
        _build_bridge_graph_state = None  # type: ignore[assignment]

try:
    from agent.bridge_stabilization import (
        BridgeStabilizationMetrics as _BridgeStabilizationMetrics,
        build_bridge_stabilization_order as _build_bridge_stabilization_order,
    )
    _BRIDGE_STABILIZATION_OK = True
except ImportError:
    try:
        from modules.agent.bridge_stabilization import (
            BridgeStabilizationMetrics as _BridgeStabilizationMetrics,
            build_bridge_stabilization_order as _build_bridge_stabilization_order,
        )
        _BRIDGE_STABILIZATION_OK = True
    except ImportError:
        _BRIDGE_STABILIZATION_OK = False
        _BridgeStabilizationMetrics = None  # type: ignore[assignment,misc]
        _build_bridge_stabilization_order = None  # type: ignore[assignment]

try:
    from agent.collective_coordination import (
        CollectiveCoordinationMetrics as _CollectiveCoordinationMetrics,
        build_collective_coordination_snapshot as _build_collective_coordination_snapshot,
    )
    _COLLECTIVE_COORDINATION_OK = True
except ImportError:
    try:
        from modules.agent.collective_coordination import (
            CollectiveCoordinationMetrics as _CollectiveCoordinationMetrics,
            build_collective_coordination_snapshot as _build_collective_coordination_snapshot,
        )
        _COLLECTIVE_COORDINATION_OK = True
    except ImportError:
        _COLLECTIVE_COORDINATION_OK = False
        _CollectiveCoordinationMetrics = None  # type: ignore[assignment,misc]
        _build_collective_coordination_snapshot = None  # type: ignore[assignment]

try:
    from agent.bridge_playbook_link import (
        BridgePlaybookMetrics as _BridgePlaybookMetrics,
        build_bridge_playbook_advisory as _build_bridge_playbook_advisory,
    )
    _BRIDGE_PLAYBOOK_LINK_OK = True
except ImportError:
    try:
        from modules.agent.bridge_playbook_link import (
            BridgePlaybookMetrics as _BridgePlaybookMetrics,
            build_bridge_playbook_advisory as _build_bridge_playbook_advisory,
        )
        _BRIDGE_PLAYBOOK_LINK_OK = True
    except ImportError:
        _BRIDGE_PLAYBOOK_LINK_OK = False
        _BridgePlaybookMetrics = None  # type: ignore[assignment,misc]
        _build_bridge_playbook_advisory = None  # type: ignore[assignment]

try:
    from agent.coordination_advisory_summary import (
        CoordinationAdvisorySummaryMetrics as _CoordinationAdvisorySummaryMetrics,
        build_coordination_advisory_summary as _build_coordination_advisory_summary,
    )
    _COORDINATION_ADVISORY_SUMMARY_OK = True
except ImportError:
    try:
        from modules.agent.coordination_advisory_summary import (
            CoordinationAdvisorySummaryMetrics as _CoordinationAdvisorySummaryMetrics,
            build_coordination_advisory_summary as _build_coordination_advisory_summary,
        )
        _COORDINATION_ADVISORY_SUMMARY_OK = True
    except ImportError:
        _COORDINATION_ADVISORY_SUMMARY_OK = False
        _CoordinationAdvisorySummaryMetrics = None  # type: ignore[assignment,misc]
        _build_coordination_advisory_summary = None  # type: ignore[assignment]

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
# Per-cycle alignment outcome helpers (pure, advisory-only)
# ---------------------------------------------------------------------------


def build_effect_reason(
    *,
    signals: list[str],
    softening_detected: bool,
    guidance_applied: bool,
    guidance_effective: bool,
    goal_alignment_score: float,
) -> str:
    """Return a short, deterministic, human-readable reason for the cycle outcome.

    Built entirely from already-computed signals and scores — no LLM, no side
    effects. Never touches route_key / graph_mode / backend selection.
    """
    if softening_detected and signals:
        seen: list[str] = []
        for s in signals:
            if s not in seen:
                seen.append(s)
        label = " + ".join(seen[:3])  # deduplicated, capped at 3
        if guidance_applied and guidance_effective:
            return f"{label} \u2192 cooperative softening (guidance effective)"
        return f"{label} \u2192 cooperative softening"

    if guidance_applied:
        if guidance_effective:
            if goal_alignment_score >= 0.65:
                return "guidance applied \u2192 goal alignment achieved"
            return "guidance applied \u2192 response quality improved"
        return "guidance applied but softening signals were weak"

    return "no clear softening signals detected"


def build_alignment_outcome_snapshot(
    *,
    guidance_applied: bool,
    pre_tension_score: float,
    post_resonance_score: float,
    post_goal_alignment_score: float,
    softening_detected: bool,
    softening_score: float,
    softening_signals: list[str],
    guidance_effective: bool,
) -> dict:
    """Return a compact, stable per-cycle outcome snapshot.

    Keys are backward-compatible with existing consumers.  The ``effect_reason``
    field supersedes the raw detector reason string with a composite explanation
    built from all available cycle signals.
    """
    effect_reason = build_effect_reason(
        signals=softening_signals,
        softening_detected=softening_detected,
        guidance_applied=guidance_applied,
        guidance_effective=guidance_effective,
        goal_alignment_score=post_goal_alignment_score,
    )
    return {
        "guidance_added": guidance_applied,
        "pre_tension_score": round(pre_tension_score, 3),
        "post_resonance_score": round(post_resonance_score, 3),
        "post_goal_alignment_score": round(post_goal_alignment_score, 3),
        "response_softened": softening_detected,
        "softening_score": round(softening_score, 3),
        "softening_signals": list(softening_signals),
        "effect_reason": effect_reason,
        "guidance_effective": guidance_effective,
    }


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

        # Stage 6b — OperatorProfile (shared, mutated per question)
        self._profile = (
            _OperatorProfile() if _PROFILE_OK and _OperatorProfile else None
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

        # Alignment memory — bounded in-memory store + optional JSONL path.
        # Max 100 units; oldest evicted when full. Advisory-only.
        self._alignment_memory_units: list = []
        self._alignment_memory_max = 100
        self._alignment_memory_lock = threading.Lock()
        self._alignment_memory_metrics = (
            _AlignmentMemoryMetrics() if _ALIGNMENT_MEMORY_OK and _AlignmentMemoryMetrics else None
        )
        # JSONL path follows the existing data/graph_memory/ convention.
        # Resolved relative to the store path used by MemoryGraphStore when
        # available; falls back to a path derived from the process cwd.
        _mem_store_path = getattr(self._graph_runtime, "_store", None)
        _mem_store_path = getattr(_mem_store_path, "path", None)
        if _mem_store_path is not None:
            from pathlib import Path as _Path
            self._alignment_memory_path = _Path(_mem_store_path).with_name(
                "alignment_memory_units.jsonl"
            )
        else:
            from pathlib import Path as _Path
            self._alignment_memory_path = (
                _Path("data/graph_memory/alignment_memory_units.jsonl")
            )
        self._council_ledger_dir = Path("artifacts/council-ledger")
        self._council_quality_dir = Path("artifacts/council-quality")
        self._relational_episode_dir = Path("artifacts/relational-episodes")
        self._relation_memory_dir = Path("artifacts/relation-memory")
        self._relational_learning_dir = Path("artifacts/relational-learning")
        self._relational_learning_loop_dir = Path("artifacts/relational-learning-loop")

        # Alignment digest metrics (advisory/observability only)
        self._digest_metrics = (
            _AlignmentDigestMetrics()
            if _ALIGNMENT_DIGEST_OK and _AlignmentDigestMetrics
            else None
        )

        # Alignment success pattern metrics (advisory/observability only)
        self._success_patterns_metrics = (
            _AlignmentSuccessPatternMetrics()
            if _ALIGNMENT_SUCCESS_PATTERNS_OK and _AlignmentSuccessPatternMetrics
            else None
        )

        # Alignment strategy recommendation metrics (advisory/observability only)
        self._recommender_metrics = (
            _AlignmentStrategyRecommendationMetrics()
            if _ALIGNMENT_RECOMMENDER_OK and _AlignmentStrategyRecommendationMetrics
            else None
        )

        # Strategy outcome feedback — bounded in-memory list, advisory/read-only
        self._strategy_feedback_events: list = []
        self._strategy_feedback_max = 200
        self._strategy_feedback_metrics = (
            _AlignmentStrategyFeedbackMetrics()
            if _ALIGNMENT_FEEDBACK_OK and _AlignmentStrategyFeedbackMetrics
            else None
        )

        # Strategy recommendation/adoption/calibration snapshots (bounded, read-only)
        self._strategy_recommendation_events: list = []
        self._strategy_recommendation_max = 200
        self._strategy_adoption_traces: list = []
        self._strategy_adoption_max = 200
        self._strategy_calibration_metrics = (
            _AlignmentStrategyCalibrationMetrics()
            if _ALIGNMENT_CALIBRATION_OK and _AlignmentStrategyCalibrationMetrics
            else None
        )
        self._council_cel_contribution_ledger = (
            _CELContributionLedger() if _COUNCIL_CEL_SYNC_OK and _CELContributionLedger else None
        )
        self._council_cel_reputation_engine = (
            _CELReputationEngine() if _COUNCIL_CEL_SYNC_OK and _CELReputationEngine else None
        )
        self._strategy_playbook_metrics = (
            _AlignmentStrategyPlaybookMetrics()
            if _ALIGNMENT_PLAYBOOK_OK and _AlignmentStrategyPlaybookMetrics
            else None
        )

        # Aggregation, reputation, adoption metrics (advisory/read-only)
        self._aggregation_metrics = (
            _AlignmentStrategyAggregationMetrics()
            if _ALIGNMENT_AGGREGATION_OK and _AlignmentStrategyAggregationMetrics
            else None
        )
        self._reputation_metrics = (
            _AlignmentStrategyReputationMetrics()
            if _ALIGNMENT_REPUTATION_OK and _AlignmentStrategyReputationMetrics
            else None
        )
        self._multi_party_alignment_metrics = (
            _MultiPartyAlignmentMetrics()
            if _MULTI_PARTY_ALIGNMENT_OK and _MultiPartyAlignmentMetrics
            else None
        )
        self._bridge_graph_metrics = (
            _BridgeGraphMetrics()
            if _BRIDGE_GRAPH_OK and _BridgeGraphMetrics
            else None
        )
        self._bridge_stabilization_metrics = (
            _BridgeStabilizationMetrics()
            if _BRIDGE_STABILIZATION_OK and _BridgeStabilizationMetrics
            else None
        )
        self._collective_coordination_metrics = (
            _CollectiveCoordinationMetrics()
            if _COLLECTIVE_COORDINATION_OK and _CollectiveCoordinationMetrics
            else None
        )
        self._bridge_playbook_metrics = (
            _BridgePlaybookMetrics()
            if _BRIDGE_PLAYBOOK_LINK_OK and _BridgePlaybookMetrics
            else None
        )
        self._coordination_advisory_summary_metrics = (
            _CoordinationAdvisorySummaryMetrics()
            if _COORDINATION_ADVISORY_SUMMARY_OK and _CoordinationAdvisorySummaryMetrics
            else None
        )

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
        item: dict = ensure_operator_item({
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
        item = ensure_operator_item(item, default_source="smart_ear")
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
                        ((cached.get("_operator_response_output") or cached.get("_copilot_output") or {}).get("active_rules") or [])
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

    def get_alignment_memory_metrics(self) -> dict:
        """Return aggregate observability counters for alignment memory writes."""
        if self._alignment_memory_metrics is None:
            return {"alignment_memory_available": False}
        with self._alignment_memory_lock:
            d = self._alignment_memory_metrics.to_dict()
            d["units_in_memory"] = len(self._alignment_memory_units)
        return d

    def get_alignment_memory_units(self) -> list:
        """Return a copy of all in-memory alignment memory units as dicts."""
        with self._alignment_memory_lock:
            return [u.to_dict() for u in self._alignment_memory_units]

    def get_alignment_digest(self) -> dict:
        """Return a compact, deterministic session digest over accumulated alignment units.

        Read-only — never modifies units, routing state, or any pipeline field.
        """
        if not (_ALIGNMENT_DIGEST_OK and _build_alignment_digest):
            return {"alignment_digest_available": False}

        with self._alignment_memory_lock:
            units = list(self._alignment_memory_units)

        digest = _build_alignment_digest(units)

        if self._digest_metrics is not None:
            self._digest_metrics.calls_total += 1
            self._digest_metrics.units_processed_total += len(units)
            if digest.get("total_units", 0) == 0:
                self._digest_metrics.empty_total += 1
            else:
                self._digest_metrics.nonempty_total += 1

        return digest

    def get_alignment_digest_metrics(self) -> dict:
        """Return observability counters for the digest build layer."""
        if self._digest_metrics is None:
            return {"alignment_digest_available": False}
        return self._digest_metrics.to_dict()

    def get_alignment_success_patterns(self) -> list:
        """Return repeated successful alignment patterns extracted from session memory.

        Read-only — never modifies units, routing state, or any pipeline field.
        Returns empty list when fewer than min_support matching units exist.
        """
        if not (_ALIGNMENT_SUCCESS_PATTERNS_OK and _build_alignment_success_patterns):
            return []

        with self._alignment_memory_lock:
            units = list(self._alignment_memory_units)

        patterns = _build_alignment_success_patterns(units)

        if self._success_patterns_metrics is not None:
            m = self._success_patterns_metrics
            m.calls_total += 1
            m.units_processed_total += len(units)
            successful = [u for u in units if u.guidance_effective or u.softening_detected or u.effect_reason]
            m.patterns_built_total += len(patterns)
            # skipped = successful groups that didn't meet min_support
            from collections import Counter as _Counter
            from modules.agent.alignment_success_patterns import make_alignment_pattern_key as _mpk
            key_counts = _Counter(_mpk(u) for u in successful)
            m.patterns_skipped_total += sum(1 for c in key_counts.values() if c < 2)
            m.patterns_with_hotspot += sum(1 for p in patterns if p.get("hotspot"))
            m.patterns_with_softening += sum(1 for p in patterns if p.get("softening_signals"))

        return patterns

    def get_alignment_success_pattern_metrics(self) -> dict:
        """Return observability counters for the success pattern build layer."""
        if self._success_patterns_metrics is None:
            return {"alignment_success_patterns_available": False}
        return self._success_patterns_metrics.to_dict()

    def get_alignment_strategy_recommendations(self, item: dict) -> list:
        """Return 0–3 strategy recommendations for the current cycle item.

        Advisory-only — never modifies item, route_key, graph_mode, or
        any session state.  Returns empty list when no patterns qualify.
        """
        if not (_ALIGNMENT_RECOMMENDER_OK and _build_alignment_strategy_recommendations):
            return []

        patterns = self.get_alignment_success_patterns()
        alignment_report = item.get("_alignment_report") or {}
        intent_obj = item.get("_intent") or {}
        if isinstance(intent_obj, dict):
            intent_str = str(intent_obj.get("type") or intent_obj.get("intent") or "")
        elif isinstance(intent_obj, str):
            intent_str = intent_obj
        else:
            intent_str = ""

        recommendations, stats = _build_alignment_strategy_recommendations(
            patterns,
            alignment_report=alignment_report,
            intent=intent_str,
        )

        if self._recommender_metrics is not None:
            m = self._recommender_metrics
            m.calls_total += 1
            m.patterns_considered_total += stats["considered"]
            m.patterns_filtered_total += stats["filtered"]
            m.recommendations_built_total += len(recommendations)
            m.hotspot_overlap_total += stats["hotspot_hits"]
            m.mismatch_overlap_total += stats["mismatch_hits"]
            m.intent_match_total += stats["intent_hits"]
            if recommendations:
                m.nonempty_total += 1
            else:
                m.empty_total += 1

        return recommendations

    def get_alignment_strategy_recommendation_metrics(self) -> dict:
        """Return observability counters for the strategy recommender."""
        if self._recommender_metrics is None:
            return {"alignment_strategy_recommender_available": False}
        return self._recommender_metrics.to_dict()

    def _record_strategy_outcome_feedback(
        self,
        recommendations: list,
        alignment_outcome: dict,
    ) -> None:
        """Append per-recommendation feedback objects to the bounded session list.

        Advisory-only post-cycle reflection — never modifies recommendations,
        alignment_outcome, routing, graph_mode, or any upstream state.
        """
        if not (_ALIGNMENT_FEEDBACK_OK and _build_strategy_outcome_feedback):
            return
        try:
            events = _build_strategy_outcome_feedback(recommendations, alignment_outcome)
        except Exception:
            return
        if not events:
            return
        # Bounded append — evict oldest when full
        with self._alignment_memory_lock:
            for ev in events:
                if len(self._strategy_feedback_events) >= self._strategy_feedback_max:
                    self._strategy_feedback_events.pop(0)
                self._strategy_feedback_events.append(ev)
        # Update metrics
        m = self._strategy_feedback_metrics
        if m is not None:
            m.calls_total += 1
            m.recommendations_processed_total += len(recommendations)
            m.feedback_events_total += len(events)
            for ev in events:
                lbl = ev.get("feedback_label", "neutral")
                if lbl == "effective":
                    m.effective_total += 1
                elif lbl == "ineffective":
                    m.ineffective_total += 1
                else:
                    m.neutral_total += 1

    def get_strategy_outcome_feedback_events(self) -> list:
        """Return a snapshot of session feedback events (read-only copy)."""
        with self._alignment_memory_lock:
            return list(self._strategy_feedback_events)

    def get_strategy_feedback_summary(self) -> dict:
        """Return aggregated feedback summary for this session."""
        if not (_ALIGNMENT_FEEDBACK_OK and _build_strategy_feedback_summary):
            return {"alignment_strategy_feedback_available": False}
        with self._alignment_memory_lock:
            events = list(self._strategy_feedback_events)
        summary = _build_strategy_feedback_summary(events)
        if self._strategy_feedback_metrics is not None:
            self._strategy_feedback_metrics.summary_calls_total += 1
        return summary

    def get_strategy_feedback_metrics(self) -> dict:
        """Return observability counters for the feedback layer."""
        if self._strategy_feedback_metrics is None:
            return {"alignment_strategy_feedback_available": False}
        return self._strategy_feedback_metrics.to_dict()

    def get_alignment_strategy_aggregation(self) -> dict:
        """Return per-pattern and per-strategy aggregation over session feedback events.

        Read-only: never modifies feedback events, recommender state, or pipeline.
        """
        if not (_ALIGNMENT_AGGREGATION_OK and _build_aggregation_summary
                and _build_pattern_feedback_stats and _build_strategy_feedback_stats):
            return {"alignment_strategy_aggregation_available": False}
        with self._alignment_memory_lock:
            events = list(self._strategy_feedback_events)
        pat_stats = _build_pattern_feedback_stats(events)
        strat_stats = _build_strategy_feedback_stats(events)
        summary = _build_aggregation_summary(events)
        m = self._aggregation_metrics
        if m is not None:
            m.calls_total += 1
            m.events_processed_total += len(events)
            m.unique_patterns_total += len(pat_stats)
            m.unique_strategies_total += len(strat_stats)
            if pat_stats or strat_stats:
                m.nonempty_total += 1
            else:
                m.empty_total += 1
        return {
            "pattern_stats": pat_stats,
            "strategy_stats": strat_stats,
            "summary": summary,
        }

    def get_alignment_strategy_aggregation_metrics(self) -> dict:
        """Return observability counters for the aggregation layer."""
        if self._aggregation_metrics is None:
            return {"alignment_strategy_aggregation_available": False}
        return self._aggregation_metrics.to_dict()

    def get_alignment_strategy_reputation_overlay(self, item: dict) -> list:
        """Return advisory reputation overlay for current cycle's recommendations.

        Read-only, no side effects, no routing or ranking changes.
        """
        if not (_ALIGNMENT_REPUTATION_OK and _build_strategy_reputation_overlay):
            return []
        recommendations = self.get_alignment_strategy_recommendations(item)
        aggregation = self.get_alignment_strategy_aggregation()
        try:
            overlays = _build_strategy_reputation_overlay(recommendations, aggregation)
        except Exception:
            return []
        m = self._reputation_metrics
        if m is not None:
            m.calls_total += 1
            m.recommendations_processed_total += len(overlays)
            for ov in overlays:
                lbl = ov.get("reputation_label", "insufficient_data")
                if lbl == "validated_pattern":
                    m.validated_total += 1
                elif lbl == "emerging_pattern":
                    m.emerging_total += 1
                elif lbl == "weak_pattern":
                    m.weak_total += 1
                else:
                    m.insufficient_total += 1
                m.confidence_sum += float(ov.get("advisory_confidence") or 0.0)
                if ov.get("has_pattern_evidence"):
                    m.pattern_evidence_total += 1
                else:
                    m.strategy_only_evidence_total += 1
        return overlays

    def get_alignment_strategy_reputation_metrics(self) -> dict:
        """Return observability counters for the reputation overlay layer."""
        if self._reputation_metrics is None:
            return {"alignment_strategy_reputation_available": False}
        return self._reputation_metrics.to_dict()

    def _record_recommendation_adoption_trace(
        self,
        recommendations: list,
        response_text: str,
        alignment_outcome: dict,
    ) -> None:
        """Build and store per-recommendation adoption traces post-response.

        Uses the lexical-cue matching in alignment_recommendation_adoption when
        available; falls back silently.  Advisory-only.
        """
        if not (_ALIGNMENT_ADOPTION_OK and _build_adoption_trace):
            return
        try:
            traces = _build_adoption_trace(
                recommendations, response_text, alignment_outcome
            )
        except Exception:
            return
        if not traces:
            return
        with self._alignment_memory_lock:
            for tr in traces:
                if len(self._strategy_adoption_traces) >= self._strategy_adoption_max:
                    self._strategy_adoption_traces.pop(0)
                self._strategy_adoption_traces.append(tr)

    def get_recommendation_adoption_traces(self) -> list:
        """Return a snapshot of session adoption traces (read-only copy)."""
        with self._alignment_memory_lock:
            return list(self._strategy_adoption_traces)

    def get_recommendation_adoption_summary(self) -> dict:
        """Return aggregated adoption summary for this session."""
        if not (_ALIGNMENT_ADOPTION_OK and _build_adoption_summary):
            return {"alignment_recommendation_adoption_available": False}
        with self._alignment_memory_lock:
            traces = list(self._strategy_adoption_traces)
        return _build_adoption_summary(traces)

    def get_recommendation_adoption_metrics(self) -> dict:
        """Return observability counters for the adoption trace layer."""
        with self._alignment_memory_lock:
            traces = list(self._strategy_adoption_traces)
        adopted = sum(1 for t in traces if t.get("adoption_label") == "adopted")
        partial = sum(1 for t in traces if t.get("adoption_label") == "partially_adopted")
        not_ad = len(traces) - adopted - partial
        score_sum = sum(float(t.get("adoption_score") or 0.0) for t in traces)
        n = len(traces)
        return {
            "calls_total": n,
            "recommendations_processed_total": n,
            "traces_total": n,
            "adopted_total": adopted,
            "partially_adopted_total": partial,
            "not_adopted_total": not_ad,
            "avg_adoption_score": round(score_sum / n, 4) if n else 0.0,
            "action_matches_total": adopted + partial,
            "unknown_actions_total": 0,
        }

    def _record_strategy_recommendations(self, recommendations: list[dict]) -> None:
        """Append recommendations to bounded session-local history."""
        if not recommendations:
            return
        with self._alignment_memory_lock:
            for rec in recommendations:
                if len(self._strategy_recommendation_events) >= self._strategy_recommendation_max:
                    self._strategy_recommendation_events.pop(0)
                self._strategy_recommendation_events.append(dict(rec))

    def _record_strategy_adoption_traces(
        self,
        recommendations: list[dict],
        final_output: str,
    ) -> None:
        """Deterministically derive session-local adoption traces from final output."""
        if not recommendations:
            return
        output_l = (final_output or "").lower()
        traces: list[dict] = []
        for rec in recommendations:
            if not isinstance(rec, dict):
                continue
            sid = rec.get("strategy_id") or ""
            if not sid:
                continue
            actions = [str(a).lower() for a in (rec.get("recommended_actions") or []) if a]
            if not actions:
                adoption_score = 0.0
            else:
                matches = sum(1 for a in actions if a in output_l)
                adoption_score = matches / len(actions)
            if adoption_score >= 0.67:
                label = "adopted"
            elif adoption_score >= 0.34:
                label = "partially_adopted"
            else:
                label = "not_adopted"
            traces.append({
                "strategy_id": sid,
                "adoption_label": label,
                "adoption_score": round(adoption_score, 4),
            })

        if not traces:
            return
        with self._alignment_memory_lock:
            for tr in traces:
                if len(self._strategy_adoption_traces) >= self._strategy_adoption_max:
                    self._strategy_adoption_traces.pop(0)
                self._strategy_adoption_traces.append(tr)

    def get_strategy_recommendation_events(self) -> list:
        """Return a copy of session recommendation events."""
        with self._alignment_memory_lock:
            return list(self._strategy_recommendation_events)

    def get_strategy_recommendation_adoption_traces(self) -> list:
        """Return a copy of session recommendation adoption traces."""
        with self._alignment_memory_lock:
            return list(self._strategy_adoption_traces)

    def get_strategy_calibration_summary(self) -> dict:
        """Return deterministic per-strategy calibration summary (read-only)."""
        if not (_ALIGNMENT_CALIBRATION_OK and _build_strategy_calibration_summary):
            return {"alignment_strategy_calibration_available": False}
        with self._alignment_memory_lock:
            recommendations = list(self._strategy_recommendation_events)
            feedback_events = list(self._strategy_feedback_events)
            adoption_traces = list(self._strategy_adoption_traces)
        aggregation = {"strategy_stats": {}}
        summary = _build_strategy_calibration_summary(
            recommendations,
            feedback_events,
            adoption_traces,
            aggregation,
        )
        metrics = self._strategy_calibration_metrics
        if metrics is not None:
            overview = summary.get("overview") or {}
            per = summary.get("per_strategy") or []
            metrics.calls_total += 1
            metrics.strategies_processed_total += len(per)
            metrics.well_calibrated_total += int(overview.get("well_calibrated_total") or 0)
            metrics.promising_but_thin_total += int(overview.get("promising_total") or 0)
            metrics.recommended_but_not_adopted_total += int(overview.get("recommended_but_not_adopted_total") or 0)
            metrics.adopted_but_low_outcome_total += int(overview.get("adopted_but_low_outcome_total") or 0)
            metrics.weakly_calibrated_total += int(overview.get("weakly_calibrated_total") or 0)
            metrics.insufficient_data_total += int(overview.get("insufficient_total") or 0)
            if per:
                metrics._adoption_rate_sum += sum(float(r.get("adoption_rate") or 0.0) for r in per) / len(per)
                metrics._effective_rate_sum += sum(float(r.get("effective_rate") or 0.0) for r in per) / len(per)
        return summary

    def get_strategy_calibration_metrics(self) -> dict:
        """Return observability counters for calibration summary builds."""
        if self._strategy_calibration_metrics is None:
            return {"alignment_strategy_calibration_available": False}
        return self._strategy_calibration_metrics.to_dict()

    def build_alignment_strategy_playbook(
        self,
        item: dict,
        recommendations: list[dict],
        calibration_summary: dict | None = None,
    ) -> dict:
        """Build compact strategy playbook from recommendations + current context.

        Advisory-only: never modifies routing, graph_mode, or upstream state.
        """
        if not (_ALIGNMENT_PLAYBOOK_OK and _build_alignment_strategy_playbook):
            return {"alignment_strategy_playbook_available": False}
        cal = calibration_summary if isinstance(calibration_summary, dict) else {}
        playbook = _build_alignment_strategy_playbook(
            recommendations,
            alignment_report=item.get("_alignment_report") or {},
            calibration_summary=cal,
        )
        m = self._strategy_playbook_metrics
        if m is not None:
            m.calls_total += 1
            selected = len(playbook.get("selected_strategy_ids") or [])
            m.strategies_selected_total += selected
            if selected:
                m.nonempty_total += 1
            else:
                m.empty_total += 1
        return playbook

    def get_alignment_strategy_playbook_metrics(self) -> dict:
        """Return observability counters for strategy playbook builds."""
        if self._strategy_playbook_metrics is None:
            return {"alignment_strategy_playbook_available": False}
        return self._strategy_playbook_metrics.to_dict()

    def get_multi_party_alignment_state(
        self,
        item: dict,
        adoption_traces: list | None = None,
    ) -> dict:
        """Build per-party alignment state snapshot for the current cycle.

        Advisory-only — never modifies item, route_key, graph_mode, or any
        upstream state.  Returns a stable schema dict with party-level
        descriptors and a session-level state label.
        """
        if not (_MULTI_PARTY_ALIGNMENT_OK and _build_multi_party_alignment_state):
            return {"multi_party_alignment_available": False}

        report = item.get("_alignment_report") or {} if isinstance(item, dict) else {}
        traces = adoption_traces if isinstance(adoption_traces, list) else []

        state = _build_multi_party_alignment_state(
            report,
            adoption_traces=traces,
        )

        m = self._multi_party_alignment_metrics
        if m is not None:
            m.calls_total += 1
            party_count = state.get("party_count") or 0
            if not report:
                m.empty_report_total += 1
            else:
                m.parties_seen_total += party_count
                m.hotspots_processed_total += len(
                    (report.get("pairwise_hotspots") or [])
                )
            label = state.get("state_label") or "stable"
            if label == "escalating":
                m.escalating_total += 1
            elif label == "diverging":
                m.diverging_total += 1
            elif label == "converging":
                m.converging_total += 1
            else:
                m.stable_total += 1

        return state

    def get_multi_party_alignment_metrics(self) -> dict:
        """Return observability counters for multi-party alignment state builds."""
        if self._multi_party_alignment_metrics is None:
            return {"multi_party_alignment_available": False}
        return self._multi_party_alignment_metrics.to_dict()

    def get_bridge_graph_state(
        self,
        item: dict,
        multi_party_state: dict | None = None,
    ) -> dict:
        """Build a pairwise bridge graph over the current multi-party alignment state.

        Advisory/structural layer only — never modifies item, route_key,
        graph_mode, reuse/refine/full_run, playbook, recommendations, or any
        upstream pipeline state.
        """
        if not (_BRIDGE_GRAPH_OK and _build_bridge_graph_state):
            return {"bridge_graph_available": False}

        mp_state = multi_party_state if isinstance(multi_party_state, dict) else {}
        report = item.get("_alignment_report") or {} if isinstance(item, dict) else {}

        graph = _build_bridge_graph_state(mp_state, report)
        graph_dict = graph.to_dict()

        m = self._bridge_graph_metrics
        if m is not None:
            m.calls_total += 1
            party_count = len(mp_state.get("parties") or [])
            if party_count < 2:
                m.small_input_total += 1
            else:
                m.graph_states_total += 1
            edges = graph.edges
            m.edges_total += len(edges)
            for edge in edges:
                bt = edge.get("bridge_type") or ""
                if bt == "acknowledgment_bridge":
                    m.acknowledgment_bridge_total += 1
                elif bt == "pacing_bridge":
                    m.pacing_bridge_total += 1
                elif bt == "reframing_bridge":
                    m.reframing_bridge_total += 1
                elif bt == "translation_bridge":
                    m.translation_bridge_total += 1
                elif bt == "stabilization_bridge":
                    m.stabilization_bridge_total += 1
                m._strength_sum += float(edge.get("bridge_strength") or 0.0)
                m._priority_sum += float(edge.get("bridge_priority") or 0.0)
            if graph.fragmentation_level == "high":
                m.high_fragmentation_total += 1

        return graph_dict

    def get_bridge_graph_metrics(self) -> dict:
        """Return observability counters for bridge graph builds."""
        if self._bridge_graph_metrics is None:
            return {"bridge_graph_available": False}
        return self._bridge_graph_metrics.to_dict()

    def get_bridge_stabilization_order(
        self,
        item: dict[str, Any],
        bridge_graph_state: dict | None = None,
        multi_party_state: dict | None = None,
    ) -> dict[str, Any]:
        """Build read-only advisory stabilization order from bridge graph edges.

        Advisory-only — never modifies item, route_key, graph_mode, reuse mode,
        backend selection, prompts, playbook, recommendations, or feedback logic.
        """
        if not (_BRIDGE_STABILIZATION_OK and _build_bridge_stabilization_order):
            return {"bridge_stabilization_available": False}

        graph_state = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
        mp_state = multi_party_state if isinstance(multi_party_state, dict) else {}

        order = _build_bridge_stabilization_order(graph_state, multi_party_state=mp_state)
        order_dict = order.to_dict()

        m = self._bridge_stabilization_metrics
        if m is not None:
            m.calls_total += 1
            edges = [e for e in (graph_state.get("edges") or []) if isinstance(e, dict)]
            if not edges:
                m.empty_inputs_total += 1
                return order_dict

            m.orders_total += 1
            ordered_edges = [e for e in (order_dict.get("ordered_edges") or []) if isinstance(e, dict)]
            m.edges_processed_total += len(ordered_edges)
            for edge in ordered_edges:
                label = str(edge.get("stabilization_label") or "")
                if label == "urgent_stabilize":
                    m.urgent_stabilize_total += 1
                elif label == "early_stabilize":
                    m.early_stabilize_total += 1
                elif label == "quick_win":
                    m.quick_win_total += 1
                elif label == "monitor":
                    m.monitor_total += 1
                elif label == "defer":
                    m.defer_total += 1
                m._stabilization_score_sum += float(edge.get("stabilization_score") or 0.0)

            mode = str(order_dict.get("dominant_stabilization_mode") or "")
            if mode == "crisis_first":
                m.crisis_first_total += 1
            elif mode == "high_priority_first":
                m.high_priority_first_total += 1
            elif mode == "quick_wins_first":
                m.quick_wins_first_total += 1
            else:
                m.observe_and_stage_total += 1

        return order_dict

    def get_bridge_stabilization_metrics(self) -> dict[str, Any]:
        """Return observability counters for bridge stabilization order builds."""
        if self._bridge_stabilization_metrics is None:
            return {"bridge_stabilization_available": False}
        return self._bridge_stabilization_metrics.to_dict()

    def get_collective_coordination_snapshot(
        self,
        item: dict[str, Any],
        multi_party_state: dict[str, Any] | None = None,
        bridge_graph_state: dict[str, Any] | None = None,
        bridge_stabilization_order: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build read-only top-level collective coordination scene snapshot."""
        if not (_COLLECTIVE_COORDINATION_OK and _build_collective_coordination_snapshot):
            return {"collective_coordination_available": False}

        mp_state = multi_party_state if isinstance(multi_party_state, dict) else {}
        graph_state = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
        order_state = (
            bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
        )

        snapshot = _build_collective_coordination_snapshot(
            multi_party_state=mp_state,
            bridge_graph_state=graph_state,
            bridge_stabilization_order=order_state,
        )
        snapshot_dict = snapshot.to_dict()

        m = self._collective_coordination_metrics
        if m is not None:
            m.calls_total += 1
            if not mp_state and not graph_state and not order_state:
                m.empty_inputs_total += 1
            m.snapshots_total += 1
            risk = float(snapshot_dict.get("coordination_risk") or 0.0)
            m._coordination_risk_sum += risk
            if risk >= 0.75:
                m.high_risk_total += 1
            elif risk >= 0.45:
                m.medium_risk_total += 1
            else:
                m.low_risk_total += 1

            label = str(snapshot_dict.get("coordination_state_label") or "")
            if label == "coherent":
                m.coherent_total += 1
            elif label == "strained":
                m.strained_total += 1
            elif label == "fragmented":
                m.fragmented_total += 1
            elif label == "unstable":
                m.unstable_total += 1
            elif label == "escalating":
                m.escalating_total += 1

            state = str(mp_state.get("state_label") or "")
            if state == "converging":
                m.converging_total += 1
            elif state == "diverging":
                m.diverging_total += 1
            elif state == "stable":
                m.stable_total += 1

            if snapshot_dict.get("primary_fracture_line"):
                m.nonempty_fracture_line_total += 1
            if [e for e in (order_state.get("urgent_edges") or []) if isinstance(e, dict)]:
                m.urgent_stabilization_total += 1

        return snapshot_dict

    def get_collective_coordination_metrics(self) -> dict[str, Any]:
        """Return observability counters for collective coordination snapshots."""
        if self._collective_coordination_metrics is None:
            return {"collective_coordination_available": False}
        return self._collective_coordination_metrics.to_dict()

    def get_bridge_playbook_advisory(
        self,
        item: dict[str, Any],
        playbook: dict[str, Any] | None = None,
        bridge_graph_state: dict[str, Any] | None = None,
        bridge_stabilization_order: dict[str, Any] | None = None,
        collective_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build read-only bridge-to-playbook advisory from structured layers.

        ``item`` is currently reserved for API consistency with other accessors.
        The advisory itself is derived only from the explicit structured layers.
        """
        if not (_BRIDGE_PLAYBOOK_LINK_OK and _build_bridge_playbook_advisory):
            return {"bridge_playbook_advisory_available": False}

        pb = playbook if isinstance(playbook, dict) else {}
        bg = bridge_graph_state if isinstance(bridge_graph_state, dict) else {}
        bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
        cs = collective_snapshot if isinstance(collective_snapshot, dict) else {}

        advisory = _build_bridge_playbook_advisory(
            playbook=pb,
            bridge_graph_state=bg,
            bridge_stabilization_order=bo,
            collective_snapshot=cs,
        )
        advisory_dict = advisory.to_dict()

        m = self._bridge_playbook_metrics
        if m is not None:
            m.calls_total += 1
            m.advisories_total += 1
            links = [e for e in (advisory_dict.get("step_links") or []) if isinstance(e, dict)]
            m.step_links_total += len(links)
            for link in links:
                label = str(link.get("link_label") or "")
                if label == "strong_fit":
                    m.strong_fit_total += 1
                elif label == "partial_fit":
                    m.partial_fit_total += 1
                elif label == "weak_fit":
                    m.weak_fit_total += 1
                elif label == "unsupported":
                    m.unsupported_total += 1
                elif label == "insufficient_context":
                    m.insufficient_context_total += 1
            m._alignment_score_sum += float(advisory_dict.get("playbook_alignment_score") or 0.0)
            if advisory_dict.get("top_supported_steps"):
                m.nonempty_supported_steps_total += 1
            if advisory_dict.get("top_weak_steps"):
                m.nonempty_weak_steps_total += 1

            alignment_label = str(advisory_dict.get("playbook_alignment_label") or "")
            if alignment_label == "well_aligned":
                m.well_aligned_total += 1
            elif alignment_label == "partially_aligned":
                m.partially_aligned_total += 1
            elif alignment_label == "weakly_aligned":
                m.weakly_aligned_total += 1
            elif alignment_label == "misaligned":
                m.misaligned_total += 1

        return advisory_dict

    def get_bridge_playbook_metrics(self) -> dict[str, Any]:
        """Return observability counters for bridge-to-playbook advisories."""
        if self._bridge_playbook_metrics is None:
            return {"bridge_playbook_advisory_available": False}
        return self._bridge_playbook_metrics.to_dict()

    def get_coordination_advisory_summary(
        self,
        item: dict[str, Any],
        collective_coordination_snapshot: dict[str, Any] | None = None,
        bridge_stabilization_order: dict[str, Any] | None = None,
        bridge_playbook_advisory: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build read-only top-level coordination advisory summary."""
        if not (_COORDINATION_ADVISORY_SUMMARY_OK and _build_coordination_advisory_summary):
            return {"coordination_advisory_summary_available": False}

        cs = collective_coordination_snapshot if isinstance(collective_coordination_snapshot, dict) else {}
        bo = bridge_stabilization_order if isinstance(bridge_stabilization_order, dict) else {}
        pa = bridge_playbook_advisory if isinstance(bridge_playbook_advisory, dict) else {}

        summary = _build_coordination_advisory_summary(
            collective_coordination_snapshot=cs,
            bridge_stabilization_order=bo,
            bridge_playbook_advisory=pa,
        )
        summary_dict = summary.to_dict()

        m = self._coordination_advisory_summary_metrics
        if m is not None:
            m.calls_total += 1
            m.summaries_total += 1
            label = str(summary_dict.get("coordination_advisory_label") or "")
            if label == "ready":
                m.ready_total += 1
            elif label == "fragile":
                m.fragile_total += 1
            elif label == "blocked":
                m.blocked_total += 1
            elif label == "insufficient_context":
                m.insufficient_context_total += 1

            mode = str(summary_dict.get("primary_intervention_mode") or "")
            if mode == "stabilization_first":
                m.stabilization_first_total += 1
            elif mode == "translation_first":
                m.translation_first_total += 1
            elif mode == "reframe_first":
                m.reframe_first_total += 1
            elif mode == "pacing_first":
                m.pacing_first_total += 1
            elif mode == "acknowledge_first":
                m.acknowledge_first_total += 1
            elif mode == "mixed":
                m.mixed_total += 1

            m._readiness_sum += float(summary_dict.get("coordination_readiness") or 0.0)

        return summary_dict

    def get_coordination_advisory_summary_metrics(self) -> dict[str, Any]:
        """Return observability counters for coordination advisory summaries."""
        if self._coordination_advisory_summary_metrics is None:
            return {"coordination_advisory_summary_available": False}
        return self._coordination_advisory_summary_metrics.to_dict()

    def _build_alignment_memory_hint_for_item(self, item: dict) -> str | None:
        """Return a soft advisory hint from past alignment units relevant to item.

        Advisory-only — never modifies item, route_key, or graph_mode.
        Returns None when memory is empty or no relevant units found.
        """
        if not (_ALIGNMENT_MEMORY_OK and _find_relevant_alignment_units and _build_alignment_memory_hint):
            return None

        with self._alignment_memory_lock:
            units = list(self._alignment_memory_units)

        if not units:
            return None

        # Derive query context from already-computed item fields
        intent_obj = item.get("_intent") or {}
        if isinstance(intent_obj, dict):
            query_intent = str(intent_obj.get("type") or intent_obj.get("intent") or "")
        elif isinstance(intent_obj, str):
            query_intent = intent_obj
        else:
            query_intent = ""

        report = item.get("_alignment_report") or {}
        query_hotspot = ""
        if isinstance(report, dict):
            hotspots = report.get("pairwise_hotspots") or []
            if hotspots and isinstance(hotspots[0], dict):
                query_hotspot = str(hotspots[0].get("tension_axis") or "")

        relevant = _find_relevant_alignment_units(
            units,
            query_intent=query_intent,
            query_hotspot=query_hotspot,
            max_results=3,
        )
        hint = _build_alignment_memory_hint(relevant)
        if hint and self._alignment_memory_metrics is not None:
            self._alignment_memory_metrics.retrieved_total += 1
        return hint

    def _maybe_store_alignment_memory_unit(self, item: dict, final_output: str) -> None:
        """Best-effort: build and store an alignment memory unit for this cycle.

        Never raises. Errors are counted in metrics and logged at DEBUG.
        Does NOT modify item, route_key, graph_mode, or any routing state.
        """
        if not (_ALIGNMENT_MEMORY_OK and _build_alignment_memory_unit):
            return

        alignment_outcome: dict = item.get("_alignment_outcome") or {}
        metrics = self._alignment_memory_metrics  # may be None if import failed

        if metrics is not None:
            metrics.builder_calls += 1

        try:
            unit = _build_alignment_memory_unit(item, final_output, alignment_outcome)
        except Exception as exc:
            logger.debug("alignment_memory: build_alignment_memory_unit failed: %s", exc)
            if metrics is not None:
                metrics.save_errors += 1
            return

        if unit is None:
            if metrics is not None:
                metrics.skipped_total += 1
            return

        # Decide whether to store
        should_store = _should_store_alignment_memory_unit(
            alignment_hotspot=unit.alignment_hotspot,
            mismatch_reasons=unit.mismatch_reasons,
            guidance_applied=unit.guidance_applied,
            softening_detected=unit.softening_detected,
            guidance_effective=unit.guidance_effective,
        )

        if not should_store:
            if metrics is not None:
                metrics.skipped_total += 1
            return

        # In-memory store (bounded, LRU-evicted by insertion order)
        with self._alignment_memory_lock:
            self._alignment_memory_units.append(unit)
            if len(self._alignment_memory_units) > self._alignment_memory_max:
                self._alignment_memory_units.pop(0)

        # Best-effort JSONL write
        if _append_alignment_memory_unit:
            try:
                _append_alignment_memory_unit(unit, self._alignment_memory_path)
            except Exception as exc:
                logger.debug("alignment_memory: JSONL write failed: %s", exc)
                if metrics is not None:
                    metrics.save_errors += 1

        if metrics is not None:
            metrics.saved_total += 1
            if unit.alignment_hotspot:
                metrics.saved_because_hotspot += 1
            if unit.softening_detected:
                metrics.saved_because_softening += 1
            if unit.guidance_effective:
                metrics.saved_because_guidance_effective += 1

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

        # Stage 6 — WHY Strategy + Anchor + OperatorProfile
        if _STRATEGY_OK and _analyze:
            try:
                strategy = _analyze(text)
                if self._profile:
                    self._profile.observe(text, strategy)
                    strategy.apply_interviewer_bias(self._profile)
                    item["_interviewer_profile"] = self._profile.to_dict()
                    item["_operator_profile"] = self._profile.to_dict()
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

        if path_decision and graph_decision and graph_decision.mode != "reuse":
            try:
                path_decision = self._apply_relation_memory_route_policy(
                    item=item,
                    path_decision=path_decision,
                    graph_mode=str(graph_decision.mode),
                    available_backends=available_backends,
                )
            except Exception as exc:
                logger.debug("ResonanceAgent: relation memory route policy failed: %s", exc)

        if path_decision and hasattr(path_decision, "to_dict"):
            item["_path_selection"] = path_decision.to_dict()
            selected_backend = path_decision.selected_backend
        elif isinstance(path_decision, dict):
            item["_path_selection"] = path_decision
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
                    final_output = (item.get("_operator_response_output") or item.get("_copilot_output") or {}).get("pre_prompt", "")
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
                final_output = (item.get("_operator_response_output") or item.get("_copilot_output") or {}).get("pre_prompt", "")
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
        # Best-effort alignment memory write (advisory-only, never raises)
        self._maybe_store_alignment_memory_unit(item, final_output)

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
        copilot = item.get("_operator_response_output") or item.get("_copilot_output") or {}
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
            "Answer the operator request briefly, precisely, and without fluff.",
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
        copilot = item.get("_operator_response_output") or item.get("_copilot_output") or {}
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

        # Alignment memory hints — soft advisory from past alignment cycles
        # (advisory-only: never affects route_key / graph_mode / backend)
        memory_hint = self._build_alignment_memory_hint_for_item(item)
        if memory_hint:
            item["_alignment_memory_hint"] = memory_hint
            parts.append(memory_hint)

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

        guidance_applied = bool(guidance)
        effect_observed = guidance_applied and (
            response_softened
            or goal_alignment_score >= 0.65
            or (response_score >= 0.62 and pre_tension_score >= 0.45)
        )

        item["_alignment_outcome"] = build_alignment_outcome_snapshot(
            guidance_applied=guidance_applied,
            pre_tension_score=pre_tension_score,
            post_resonance_score=float(item.get("_resonance_score", 0.0) or 0.0),
            post_goal_alignment_score=float(goal_alignment_score or 0.0),
            softening_detected=response_softened,
            softening_score=float(softening.get("score", 0.0) or 0.0),
            softening_signals=softening_signals,
            guidance_effective=effect_observed,
        )

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
        copilot   = item.get("_operator_response_output") or item.get("_copilot_output") or {}
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

        # Strategy recommendations — computed once so feedback and adoption can share it
        _strategy_recs = self.get_alignment_strategy_recommendations(item)
        self._record_strategy_recommendations(_strategy_recs)
        self._record_strategy_adoption_traces(_strategy_recs, final_output)
        # Post-cycle feedback: advisory-only, appends to bounded session list
        self._record_strategy_outcome_feedback(_strategy_recs, alignment_outcome)
        _strategy_calibration_summary = self.get_strategy_calibration_summary()
        _strategy_playbook = self.build_alignment_strategy_playbook(
            item, _strategy_recs, calibration_summary=_strategy_calibration_summary
        )
        # Post-response adoption trace: checks recommended actions in final text
        self._record_recommendation_adoption_trace(
            _strategy_recs, final_output, alignment_outcome
        )
        # Multi-party alignment state snapshot (advisory, read-only)
        _adoption_traces_snapshot = self.get_recommendation_adoption_traces()
        _multi_party_state = self.get_multi_party_alignment_state(
            item, adoption_traces=_adoption_traces_snapshot
        )
        # Bridge graph: structural relationship layer over multi-party state
        _bridge_graph = self.get_bridge_graph_state(item, multi_party_state=_multi_party_state)
        # Bridge stabilization: advisory ordering layer over bridge graph edges
        _bridge_stabilization_order = self.get_bridge_stabilization_order(
            item,
            bridge_graph_state=_bridge_graph,
            multi_party_state=_multi_party_state,
        )
        _collective_coordination_snapshot = self.get_collective_coordination_snapshot(
            item,
            multi_party_state=_multi_party_state,
            bridge_graph_state=_bridge_graph,
            bridge_stabilization_order=_bridge_stabilization_order,
        )
        _bridge_playbook_advisory = self.get_bridge_playbook_advisory(
            item,
            playbook=_strategy_playbook,
            bridge_graph_state=_bridge_graph,
            bridge_stabilization_order=_bridge_stabilization_order,
            collective_snapshot=_collective_coordination_snapshot,
        )
        _coordination_advisory_summary = self.get_coordination_advisory_summary(
            item,
            collective_coordination_snapshot=_collective_coordination_snapshot,
            bridge_stabilization_order=_bridge_stabilization_order,
            bridge_playbook_advisory=_bridge_playbook_advisory,
        )
        council_ledger = self._build_council_contribution_ledger(
            item=item,
            cycle_id=cycle_id,
            final_output=final_output,
            strategy_recommendations=_strategy_recs,
        )
        council_ledger_artifact = self._write_council_contribution_ledger_artifact(
            council_ledger
        )
        council_cel_sync = self._sync_council_ledger_to_cel(council_ledger)
        relational_episode_artifact = self._write_relational_episode_artifact(
            council_ledger,
            item=item,
            council_ledger_artifact=council_ledger_artifact,
            council_cel_sync=council_cel_sync,
        )
        relation_memory_artifact = self._write_relation_memory_artifact(
            council_ledger,
            item=item,
            council_ledger_artifact=council_ledger_artifact,
            council_cel_sync=council_cel_sync,
        )
        council_quality_artifact = self._write_council_quality_artifact(
            council_ledger,
            council_ledger_artifact=council_ledger_artifact,
            council_cel_sync=council_cel_sync,
            item=item,
            relational_episode_artifact=relational_episode_artifact,
            relation_memory_artifact=relation_memory_artifact,
        )
        relational_learning_artifact = self._write_relational_learning_artifact(
            council_ledger,
            item=item,
            council_quality_artifact=council_quality_artifact,
        )
        relational_edge_learning = self._apply_relational_edge_learning(
            council_ledger,
            item=item,
            council_cel_sync=council_cel_sync,
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
            "operator_profile": item.get("_operator_profile") or item.get("_interviewer_profile"),
            "interviewer_profile": item.get("_operator_profile") or item.get("_interviewer_profile"),
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
            "alignment_memory_hint": item.get("_alignment_memory_hint"),
            "alignment_memory_metrics": self.get_alignment_memory_metrics(),
            "alignment_digest": self.get_alignment_digest(),
            "alignment_success_patterns": self.get_alignment_success_patterns(),
            "alignment_strategy_recommendations": _strategy_recs,
            "alignment_strategy_playbook": _strategy_playbook,
            "alignment_strategy_playbook_metrics": self.get_alignment_strategy_playbook_metrics(),
            "alignment_strategy_feedback": self.get_strategy_outcome_feedback_events(),
            "alignment_strategy_feedback_summary": self.get_strategy_feedback_summary(),
            "alignment_strategy_calibration_summary": self.get_strategy_calibration_summary(),
            "alignment_strategy_calibration_metrics": self.get_strategy_calibration_metrics(),
            "multi_party_alignment_state": _multi_party_state,
            "multi_party_alignment_metrics": self.get_multi_party_alignment_metrics(),
            "bridge_graph_state": _bridge_graph,
            "bridge_graph_metrics": self.get_bridge_graph_metrics(),
            "bridge_stabilization_order": _bridge_stabilization_order,
            "bridge_stabilization_metrics": self.get_bridge_stabilization_metrics(),
            "collective_coordination_snapshot": _collective_coordination_snapshot,
            "collective_coordination_metrics": self.get_collective_coordination_metrics(),
            "bridge_playbook_advisory": _bridge_playbook_advisory,
            "bridge_playbook_metrics": self.get_bridge_playbook_metrics(),
            "coordination_advisory_summary": _coordination_advisory_summary,
            "coordination_advisory_summary_metrics": self.get_coordination_advisory_summary_metrics(),
            "council_contribution_ledger": (
                council_ledger.to_dict() if council_ledger is not None else None
            ),
            "council_contribution_ledger_artifact": council_ledger_artifact,
            "relational_episode_artifact": relational_episode_artifact,
            "relation_memory_artifact": relation_memory_artifact,
            "relational_learning_artifact": relational_learning_artifact,
            "relational_edge_learning": relational_edge_learning,
            "council_cel_sync": council_cel_sync,
            "council_quality_artifact": council_quality_artifact,
            "route_key":       path_meta.get("route_key") or trail_meta.get("route_key") or fallback_route_key,
            "route_reason":    path_meta.get("reason") or "trail-fallback",
            "route_strategy":  path_meta.get("route_strategy"),
            "route_memory_adjusted": bool((path_meta.get("relation_memory_route_policy") or {}).get("policy_adjusted")),
            "route_memory_match_count": int(((path_meta.get("relation_memory_route_policy") or {}).get("match_count")) or 0),
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

    def _build_council_contribution_ledger(
        self,
        *,
        item: dict,
        cycle_id: str,
        final_output: str,
        strategy_recommendations: list[dict],
    ):
        if not (_COUNCIL_LEDGER_OK and _CouncilContributionLedger):
            return None

        path_meta = item.get("_path_selection") or {}
        trail_meta = item.get("_trail_route") or {}
        graph_meta = item.get("_graph_runtime") or {}
        llm_meta = item.get("_llm_backend") or {}
        orientation_meta = item.get("_network_plan") or {}
        alignment_report = item.get("_alignment_report") or {}
        alignment_outcome = item.get("_alignment_outcome") or {}
        cooperative_meta = item.get("_cooperative") or {}

        selected_route = (
            path_meta.get("route_key")
            or trail_meta.get("route_key")
            or orientation_meta.get("route_key")
            or "unknown"
        )
        task_id = str(item.get("_task_id") or item.get("task_id") or cycle_id)
        provider = str(llm_meta.get("provider") or "unknown")
        model = str(llm_meta.get("model") or "unknown")
        llm_id = f"{provider}:{model}" if provider != "unknown" or model != "unknown" else "primary-llm"
        latency_ms = int(llm_meta.get("latency_ms") or 0)

        adoption_by_strategy: dict[str, dict[str, Any]] = {}
        for trace in self.get_recommendation_adoption_traces():
            if not isinstance(trace, dict):
                continue
            strategy_id = str(trace.get("strategy_id") or "")
            if strategy_id:
                adoption_by_strategy[strategy_id] = trace

        participants: list = []
        for rec in strategy_recommendations:
            if not isinstance(rec, dict):
                continue
            strategy_id = str(rec.get("strategy_id") or "")
            if not strategy_id:
                continue
            adoption = adoption_by_strategy.get(strategy_id, {})
            confidence = max(
                float(rec.get("effective_rate") or 0.0),
                float(adoption.get("adoption_score") or 0.0),
                min(float(rec.get("support_count") or 0.0) / 10.0, 1.0),
            )
            participants.append(
                _CouncilParticipant(
                    model_id=f"strategy:{strategy_id}",
                    model_type="advisory_strategy",
                    proposal_id=strategy_id,
                    proposal_summary=str(rec.get("summary") or rec.get("title") or strategy_id),
                    route_hint=str(selected_route),
                    confidence=confidence,
                    latency_ms=latency_ms,
                    token_cost=0.0,
                    selected=str(adoption.get("adoption_label") or "") != "not_adopted",
                    weight_in_final_decision=float(adoption.get("adoption_score") or 0.0),
                )
            )

        coop_participants = cooperative_meta.get("participants") or []
        coop_route_key = str(cooperative_meta.get("route_key") or selected_route)
        coop_trust_score = float(cooperative_meta.get("trust_score") or 0.0)
        for peer_id in coop_participants:
            pid = str(peer_id)
            if not pid:
                continue
            participants.append(
                _CouncilParticipant(
                    model_id=pid,
                    model_type="cooperative_peer",
                    proposal_id=f"coop:{pid}",
                    proposal_summary="Cooperative council participant",
                    route_hint=coop_route_key,
                    confidence=coop_trust_score,
                    latency_ms=latency_ms,
                    token_cost=0.0,
                    selected=bool(cooperative_meta.get("success")),
                    weight_in_final_decision=coop_trust_score,
                )
            )

        participants.append(
            _CouncilParticipant(
                model_id=llm_id,
                model_type="primary_llm",
                proposal_id=f"route:{selected_route}",
                proposal_summary=(final_output or "").strip()[:160] or "Primary LLM response",
                route_hint=str(selected_route),
                confidence=float(item.get("_resonance_score", 0.5) or 0.5),
                latency_ms=latency_ms,
                token_cost=0.0,
                selected=True,
                weight_in_final_decision=1.0,
            )
        )

        derived_from_proposals = [
            participant.proposal_id
            for participant in participants
            if getattr(participant, "selected", False)
        ]

        goal_summary = (
            str((orientation_meta.get("goal_vector") or {}).get("strategy_bias") or "")
            or str((orientation_meta.get("need_profile") or {}).get("priority") or "")
            or str(item.get("text") or "")
        )[:160]

        active_nodes: list[str] = []
        for participant in alignment_report.get("participants") or []:
            if isinstance(participant, dict):
                pid = str(participant.get("participant_id") or participant.get("id") or "")
                if pid:
                    active_nodes.append(pid)
            elif isinstance(participant, str):
                active_nodes.append(participant)

        route_candidates: list[str] = []
        for value in (
            path_meta.get("route_key"),
            trail_meta.get("route_key"),
            orientation_meta.get("route_key"),
            cooperative_meta.get("route_key"),
        ):
            candidate = str(value or "")
            if candidate and candidate not in route_candidates:
                route_candidates.append(candidate)
        if selected_route and selected_route not in route_candidates:
            route_candidates.append(str(selected_route))

        observer_status = str((item.get("_observer_report") or {}).get("status") or "").lower()
        drift_detected = observer_status in {"drift", "unstable", "critical", "alert"}
        path_quality = float(
            alignment_outcome.get("post_goal_alignment_score")
            or item.get("_goal_alignment_score")
            or item.get("_resonance_score")
            or 0.0
        )
        network_improvement = float(
            item.get("_trail_reward")
            or cooperative_meta.get("trust_score")
            or (1.0 if cooperative_meta.get("success") else 0.0)
            or 0.0
        )
        operator_intervention_required = bool(
            (item.get("_care_cycle") or {}).get("action") in {"review", "retire"}
        )
        operator_feedback_score = float(
            alignment_outcome.get("softening_score")
            or alignment_outcome.get("post_goal_alignment_score")
            or item.get("_resonance_score")
            or 0.0
        )
        receiver_type = "model" if coop_participants else "human_operator"
        receiver_resonance_score = float(
            alignment_outcome.get("softening_score")
            or alignment_outcome.get("post_goal_alignment_score")
            or item.get("_goal_alignment_score")
            or item.get("_resonance_score")
            or 0.0
        )
        if receiver_resonance_score >= 0.70 and not operator_intervention_required:
            receiver_acceptance_label = "accepted"
        elif receiver_resonance_score >= 0.45:
            receiver_acceptance_label = "needs_revision"
        else:
            receiver_acceptance_label = "rejected"
        success = bool(
            alignment_outcome.get("guidance_effective")
            or cooperative_meta.get("success")
            or path_quality >= 0.55
        )

        return _CouncilContributionLedger.build(
            cycle_id=cycle_id,
            task_id=task_id,
            goal=_CouncilGoal(
                type="coordination_cycle",
                summary=goal_summary or "Council coordination cycle",
            ),
            network_context=_CouncilNetworkContext(
                route_candidates=route_candidates,
                active_nodes=active_nodes,
                graph_state_version=str(graph_meta.get("mode") or "unknown"),
            ),
            participants=participants,
            final_decision=_CouncilDecision(
                selected_route=str(selected_route),
                decision_summary=str(path_meta.get("reason") or "Council route selected"),
                derived_from_proposals=derived_from_proposals,
            ),
            outcome=_CouncilOutcome(
                success=success,
                path_quality=path_quality,
                network_improvement=network_improvement,
                operator_intervention_required=operator_intervention_required,
                operator_feedback_score=operator_feedback_score,
                drift_detected=drift_detected,
                receiver_type=receiver_type,
                receiver_resonance_score=receiver_resonance_score,
                receiver_acceptance_label=receiver_acceptance_label,
            ),
        )

    def _write_council_contribution_ledger_artifact(self, ledger) -> str | None:
        if ledger is None:
            return None
        try:
            self._council_ledger_dir.mkdir(parents=True, exist_ok=True)
            path = self._council_ledger_dir / f"{ledger.cycle_id}.json"
            path.write_text(
                json.dumps(ledger.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(path)
        except Exception as exc:
            logger.debug("ResonanceAgent: council ledger artifact write failed: %s", exc)
            return None

    def _sync_council_ledger_to_cel(self, ledger) -> dict[str, Any] | None:
        if (
            ledger is None
            or not _COUNCIL_CEL_SYNC_OK
            or _apply_council_ledger_to_cel is None
            or self._council_cel_contribution_ledger is None
            or self._council_cel_reputation_engine is None
        ):
            return None
        try:
            return _apply_council_ledger_to_cel(
                ledger,
                contribution_ledger=self._council_cel_contribution_ledger,
                reputation_engine=self._council_cel_reputation_engine,
            )
        except Exception as exc:
            logger.debug("ResonanceAgent: council CEL sync failed: %s", exc)
            return None

    def _quality_score_fallback_from_ledger(self, ledger) -> float | None:
        if ledger is None:
            return None
        outcome = getattr(ledger, "outcome", None)
        if outcome is None:
            return None
        if _quality_score_from_council_outcome is not None:
            try:
                return float(_quality_score_from_council_outcome(outcome))
            except Exception as exc:
                logger.debug("ResonanceAgent: council quality score fallback import failed: %s", exc)
        path_quality = max(0.0, min(1.0, float(getattr(outcome, "path_quality", 0.0) or 0.0)))
        operator_feedback = max(
            0.0,
            min(1.0, float(getattr(outcome, "operator_feedback_score", 0.0) or 0.0)),
        )
        receiver_resonance = max(
            0.0,
            min(1.0, float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)),
        )
        success = 1.0 if bool(getattr(outcome, "success", False)) else 0.0
        return round(
            (0.35 * path_quality)
            + (0.25 * operator_feedback)
            + (0.25 * receiver_resonance)
            + (0.15 * success),
            4,
        )

    def _build_council_quality_artifact_payload(
        self,
        ledger,
        *,
        council_ledger_artifact: str | None,
        council_cel_sync: dict[str, Any] | None,
        item: dict[str, Any] | None = None,
        relational_episode_artifact: str | None = None,
        relation_memory_artifact: str | None = None,
    ) -> dict[str, Any] | None:
        if ledger is None:
            return None
        outcome = getattr(ledger, "outcome", None)
        attribution = getattr(ledger, "attribution", None)
        final_decision = getattr(ledger, "final_decision", None)
        quality_score = None
        if council_cel_sync is not None:
            quality_score = council_cel_sync.get("quality_score")
        if quality_score is None:
            quality_score = self._quality_score_fallback_from_ledger(ledger)
        relational = self._build_relational_quality_summary((item or {}).get("_relational_field"))
        base_risk_summary = self._build_relation_risk_summary(relational)
        memory_context = self._build_relation_memory_context(
            ledger=ledger,
            relational_summary=relational,
            base_risk_summary=base_risk_summary,
        )
        risk_summary = self._build_relation_risk_summary(relational, memory_context=memory_context)
        relation_adjusted_quality_score = quality_score
        if quality_score is not None and relational is not None:
            relation_adjusted_quality_score = round(
                (0.75 * float(quality_score)) + (0.25 * float(relational["relation_safety_score"])),
                4,
            )
        path_meta = ((item or {}).get("_path_selection") or {}) if item is not None else {}
        route_memory_policy = path_meta.get("relation_memory_route_policy") or {}
        return {
            "cycle_id": str(getattr(ledger, "cycle_id", "") or ""),
            "task_id": str(getattr(ledger, "task_id", "") or ""),
            "timestamp": str(getattr(ledger, "timestamp", "") or ""),
            "council_ledger_path": council_ledger_artifact,
            "relational_episode_path": relational_episode_artifact,
            "relation_memory_path": relation_memory_artifact,
            "quality_score": quality_score,
            "relation_adjusted_quality_score": relation_adjusted_quality_score,
            "council_outcome": {
                "success": bool(getattr(outcome, "success", False)) if outcome is not None else False,
                "selected_route": (
                    str(getattr(final_decision, "selected_route", "unknown") or "unknown")
                    if final_decision is not None
                    else "unknown"
                ),
                "receiver_resonance_score": (
                    float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)
                    if outcome is not None
                    else 0.0
                ),
                "network_improvement": (
                    float(getattr(outcome, "network_improvement", 0.0) or 0.0)
                    if outcome is not None
                    else 0.0
                ),
                "receiver_acceptance_label": (
                    str(getattr(outcome, "receiver_acceptance_label", "unknown") or "unknown")
                    if outcome is not None
                    else "unknown"
                ),
                "route_strategy": str(path_meta.get("route_strategy") or risk_summary.get("route_strategy") or "continue_current_route"),
                "safety_mode": str(path_meta.get("safety_mode") or risk_summary.get("safety_mode") or "normal"),
                "route_memory_adjusted": bool(route_memory_policy.get("policy_adjusted")),
                "route_memory_match_count": int(route_memory_policy.get("match_count") or 0),
            },
            "attribution": {
                "best_contributor_model_id": (
                    str(getattr(attribution, "best_contributor_model_id", "n/a") or "n/a")
                    if attribution is not None
                    else "n/a"
                ),
                "best_contributor_score": (
                    float(getattr(attribution, "best_contributor_score", 0.0) or 0.0)
                    if attribution is not None
                    else 0.0
                ),
            },
            "cel": council_cel_sync or {
                "proposal_id": str(getattr(ledger, "cycle_id", "") or ""),
                "quality_score": quality_score,
                "contribution_records": [],
                "reputation_updates": [],
                "merit_updates": [],
            },
            "relational_field": relational,
            "operator_guidance": risk_summary,
            "liminalqa": {
                "published": False,
                "status_code": None,
            },
        }

    def _write_council_quality_artifact(
        self,
        ledger,
        *,
        council_ledger_artifact: str | None,
        council_cel_sync: dict[str, Any] | None,
        item: dict[str, Any] | None = None,
        relational_episode_artifact: str | None = None,
        relation_memory_artifact: str | None = None,
    ) -> str | None:
        payload = self._build_council_quality_artifact_payload(
            ledger,
            council_ledger_artifact=council_ledger_artifact,
            council_cel_sync=council_cel_sync,
            item=item,
            relational_episode_artifact=relational_episode_artifact,
            relation_memory_artifact=relation_memory_artifact,
        )
        if payload is None:
            return None
        try:
            self._council_quality_dir.mkdir(parents=True, exist_ok=True)
            path = self._council_quality_dir / f"{payload['cycle_id']}.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(path)
        except Exception as exc:
            logger.debug("ResonanceAgent: council quality artifact write failed: %s", exc)
            return None

    def _build_relational_episode_artifact_payload(
        self,
        ledger,
        *,
        item: dict[str, Any] | None = None,
        council_ledger_artifact: str | None = None,
        council_cel_sync: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if ledger is None:
            return None
        outcome = getattr(ledger, "outcome", None)
        attribution = getattr(ledger, "attribution", None)
        final_decision = getattr(ledger, "final_decision", None)
        relational = (item or {}).get("_relational_field")
        if not isinstance(relational, dict) or not relational:
            return None
        quality_score = None
        if council_cel_sync is not None:
            quality_score = council_cel_sync.get("quality_score")
        if quality_score is None:
            quality_score = self._quality_score_fallback_from_ledger(ledger)
        relational_summary = self._build_relational_quality_summary(relational)
        base_risk_summary = self._build_relation_risk_summary(relational_summary)
        memory_context = self._build_relation_memory_context(
            ledger=ledger,
            relational_summary=relational_summary,
            base_risk_summary=base_risk_summary,
        )
        risk_summary = self._build_relation_risk_summary(relational_summary, memory_context=memory_context)
        relation_adjusted_quality_score = quality_score
        if quality_score is not None and relational_summary is not None:
            relation_adjusted_quality_score = round(
                (0.75 * float(quality_score)) + (0.25 * float(relational_summary["relation_safety_score"])),
                4,
            )
        return {
            "cycle_id": str(getattr(ledger, "cycle_id", "") or ""),
            "task_id": str(getattr(ledger, "task_id", "") or ""),
            "timestamp": str(getattr(ledger, "timestamp", "") or ""),
            "council_ledger_path": council_ledger_artifact,
            "selected_route": (
                str(getattr(final_decision, "selected_route", "unknown") or "unknown")
                if final_decision is not None
                else "unknown"
            ),
            "quality_score": quality_score,
            "relation_adjusted_quality_score": relation_adjusted_quality_score,
            "best_contributor_model_id": (
                str(getattr(attribution, "best_contributor_model_id", "n/a") or "n/a")
                if attribution is not None
                else "n/a"
            ),
            "receiver_resonance_score": (
                float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)
                if outcome is not None
                else 0.0
            ),
            "success": bool(getattr(outcome, "success", False)) if outcome is not None else False,
            "relational_field": relational,
            "relational_summary": relational_summary,
            "operator_guidance": risk_summary,
        }

    def _write_relational_episode_artifact(
        self,
        ledger,
        *,
        item: dict[str, Any] | None = None,
        council_ledger_artifact: str | None = None,
        council_cel_sync: dict[str, Any] | None = None,
    ) -> str | None:
        payload = self._build_relational_episode_artifact_payload(
            ledger,
            item=item,
            council_ledger_artifact=council_ledger_artifact,
            council_cel_sync=council_cel_sync,
        )
        if payload is None:
            return None
        try:
            self._relational_episode_dir.mkdir(parents=True, exist_ok=True)
            path = self._relational_episode_dir / f"{payload['cycle_id']}.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(path)
        except Exception as exc:
            logger.debug("ResonanceAgent: relational episode artifact write failed: %s", exc)
            return None

    def _build_relation_memory_artifact_payload(
        self,
        ledger,
        *,
        item: dict[str, Any] | None = None,
        council_ledger_artifact: str | None = None,
        council_cel_sync: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if ledger is None:
            return None
        outcome = getattr(ledger, "outcome", None)
        final_decision = getattr(ledger, "final_decision", None)
        relational = (item or {}).get("_relational_field")
        relational_summary = self._build_relational_quality_summary(relational)
        if relational_summary is None:
            return None
        base_risk_summary = self._build_relation_risk_summary(relational_summary)
        memory_context = self._build_relation_memory_context(
            ledger=ledger,
            relational_summary=relational_summary,
            base_risk_summary=base_risk_summary,
        )
        risk_summary = self._build_relation_risk_summary(relational_summary, memory_context=memory_context)
        review = (item or {}).get("_council_operator_review") or {}
        review_decision = str(review.get("decision") or "pending")
        receiver_resonance = (
            float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)
            if outcome is not None
            else 0.0
        )
        risk_state = str(risk_summary.get("risk_state") or "watch")
        dominant_signal = str(relational_summary.get("dominant_signal") or "unknown")
        resonance_bucket = (
            "low" if receiver_resonance < 0.35 else "mid" if receiver_resonance < 0.7 else "high"
        )
        return {
            "cycle_id": str(getattr(ledger, "cycle_id", "") or ""),
            "task_id": str(getattr(ledger, "task_id", "") or ""),
            "timestamp": str(getattr(ledger, "timestamp", "") or ""),
            "council_ledger_path": council_ledger_artifact,
            "pattern_key": f"{risk_state}:{dominant_signal}:{resonance_bucket}",
            "risk_state": risk_state,
            "approval_posture": str(risk_summary.get("approval_posture") or "unknown"),
            "relation_safety_score": float(relational_summary.get("relation_safety_score") or 0.0),
            "tension_score": float(relational_summary.get("tension_score") or 0.0),
            "alignment_score": float(relational_summary.get("alignment_score") or 0.0),
            "dominant_signal": dominant_signal,
            "recommended_mode": str(relational_summary.get("recommended_mode") or "unknown"),
            "selected_route": (
                str(getattr(final_decision, "selected_route", "unknown") or "unknown")
                if final_decision is not None
                else "unknown"
            ),
            "receiver_resonance_score": receiver_resonance,
            "review_decision": review_decision,
            "incident_published": bool(((council_cel_sync or {}).get("incident") or {}).get("published", False)),
            "memory_context": memory_context,
            "tags": [risk_state, dominant_signal, resonance_bucket, review_decision],
        }

    def _write_relation_memory_artifact(
        self,
        ledger,
        *,
        item: dict[str, Any] | None = None,
        council_ledger_artifact: str | None = None,
        council_cel_sync: dict[str, Any] | None = None,
    ) -> str | None:
        payload = self._build_relation_memory_artifact_payload(
            ledger,
            item=item,
            council_ledger_artifact=council_ledger_artifact,
            council_cel_sync=council_cel_sync,
        )
        if payload is None:
            return None
        try:
            self._relation_memory_dir.mkdir(parents=True, exist_ok=True)
            path = self._relation_memory_dir / f"{payload['cycle_id']}.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(path)
        except Exception as exc:
            logger.debug("ResonanceAgent: relation memory artifact write failed: %s", exc)
            return None

    def _load_council_quality_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self._council_quality_dir.exists():
            return rows
        for path in sorted(self._council_quality_dir.glob("*.json")):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return rows

    def _build_relational_learning_artifact_payload(
        self,
        ledger,
        *,
        item: dict[str, Any] | None = None,
        council_quality_artifact: str | None = None,
    ) -> dict[str, Any] | None:
        if ledger is None:
            return None
        cycle_id = str(getattr(ledger, "cycle_id", "") or "")
        current_guidance: dict[str, Any] = {}
        if council_quality_artifact:
            try:
                current_payload = json.loads(Path(council_quality_artifact).read_text(encoding="utf-8"))
                current_guidance = (current_payload or {}).get("operator_guidance") or {}
            except Exception:
                current_guidance = {}
        rows = [
            row for row in self._load_council_quality_rows()
            if str(row.get("cycle_id") or "") != cycle_id
        ]
        rule_counts: Counter[str] = Counter()
        approve_counts: Counter[str] = Counter()
        reject_counts: Counter[str] = Counter()
        incident_counts: Counter[str] = Counter()
        for row in rows:
            guidance = row.get("operator_guidance") or {}
            rules = [str(rule) for rule in list(guidance.get("rule_hits") or [])]
            if not rules:
                continue
            decision = str((row.get("operator_review") or {}).get("decision") or "pending")
            incident_published = bool(((row.get("liminalqa") or {}).get("incident") or {}).get("published"))
            for rule in rules:
                rule_counts[rule] += 1
                if decision == "approved":
                    approve_counts[rule] += 1
                elif decision in {"rejected", "closed"}:
                    reject_counts[rule] += 1
                if incident_published:
                    incident_counts[rule] += 1
        top_effective_rules: list[dict[str, Any]] = []
        for rule, total in rule_counts.most_common(5):
            approved = approve_counts[rule]
            rejected = reject_counts[rule]
            incidents = incident_counts[rule]
            effectiveness = round((approved - rejected - incidents) / max(total, 1), 4)
            top_effective_rules.append(
                {
                    "rule": rule,
                    "seen": total,
                    "approved": approved,
                    "rejected": rejected,
                    "incidents": incidents,
                    "effectiveness": effectiveness,
                }
            )
        return {
            "cycle_id": cycle_id,
            "task_id": str(getattr(ledger, "task_id", "") or ""),
            "timestamp": str(getattr(ledger, "timestamp", "") or ""),
            "council_quality_path": council_quality_artifact,
            "current_rule_hits": [str(rule) for rule in list(current_guidance.get("rule_hits") or [])],
            "current_safety_mode": str(current_guidance.get("safety_mode") or "unknown"),
            "top_effective_rules": top_effective_rules,
            "heuristic_count": len(top_effective_rules),
        }

    def _write_relational_learning_artifact(
        self,
        ledger,
        *,
        item: dict[str, Any] | None = None,
        council_quality_artifact: str | None = None,
    ) -> str | None:
        payload = self._build_relational_learning_artifact_payload(
            ledger,
            item=item,
            council_quality_artifact=council_quality_artifact,
        )
        if payload is None:
            return None
        try:
            self._relational_learning_dir.mkdir(parents=True, exist_ok=True)
            path = self._relational_learning_dir / f"{payload['cycle_id']}.json"
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(path)
        except Exception as exc:
            logger.debug("ResonanceAgent: relational learning artifact write failed: %s", exc)
            return None

    def _apply_relational_edge_learning(
        self,
        ledger,
        *,
        item: dict[str, Any] | None = None,
        council_cel_sync: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not (self._graph_runtime and hasattr(self._graph_runtime, "adapt_relational_edges_from_outcome")):
            return None
        outcome = getattr(ledger, "outcome", None) if ledger is not None else None
        resonance_score = (
            float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)
            if outcome is not None
            else float((item or {}).get("_resonance_score", 0.0) or 0.0)
        )
        review = (council_cel_sync or {}).get("operator_review") or {}
        review_decision = str(review.get("decision") or "pending").strip().lower()
        incident_published = bool(((council_cel_sync or {}).get("incident") or {}).get("published"))
        feedback_polarity = 0.0
        if review_decision == "approved":
            feedback_polarity = 0.8
        elif review_decision in {"rejected", "closed"}:
            feedback_polarity = -0.8
        try:
            payload = self._graph_runtime.adapt_relational_edges_from_outcome(
                feedback_polarity=feedback_polarity,
                resonance_score=resonance_score,
                review_decision=review_decision,
                incident_published=incident_published,
                top_k=3,
            )
            if not isinstance(payload, dict):
                return None
            if hasattr(self._graph_runtime, "propose_relational_maintenance"):
                maintenance = self._graph_runtime.propose_relational_maintenance(max_units=20)
                if isinstance(maintenance, dict):
                    payload["maintenance"] = maintenance
            cycle_id = str(getattr(ledger, "cycle_id", "") or "")
            loop_artifact_path = self._write_relational_learning_loop_artifact(
                cycle_id=cycle_id,
                payload=payload,
            )
            if loop_artifact_path:
                payload["loop_artifact_path"] = loop_artifact_path
            return payload
        except Exception as exc:
            logger.debug("ResonanceAgent: relational edge learning failed: %s", exc)
            return None

    def _write_relational_learning_loop_artifact(
        self,
        *,
        cycle_id: str,
        payload: dict[str, Any],
    ) -> str | None:
        if not cycle_id:
            return None
        try:
            self._relational_learning_loop_dir.mkdir(parents=True, exist_ok=True)
            path = self._relational_learning_loop_dir / f"{cycle_id}.json"
            artifact = {
                "cycle_id": cycle_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "updated_edges": int((payload or {}).get("updated_edges") or 0),
                "scanned_units": int((payload or {}).get("scanned_units") or 0),
                "maintenance": dict((payload or {}).get("maintenance") or {}),
            }
            path.write_text(
                json.dumps(artifact, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return str(path)
        except Exception as exc:
            logger.debug("ResonanceAgent: relational learning loop artifact write failed: %s", exc)
            return None

    def _build_relational_quality_summary(self, relational: Any) -> dict[str, Any] | None:
        if not isinstance(relational, dict) or not relational:
            return None
        try:
            tension_score = max(0.0, min(1.0, float(relational.get("tension_score", 0.0) or 0.0)))
            alignment_score = max(0.0, min(1.0, float(relational.get("alignment_score", 0.0) or 0.0)))
        except (TypeError, ValueError):
            return None
        dominant_signal = str(relational.get("dominant_signal") or "neutral")
        relation_safety_score = round(max(0.0, min(1.0, ((1.0 - tension_score) + alignment_score) / 2.0)), 4)
        anti_tension = 1.0 - tension_score
        agreement = 1.0 - abs(alignment_score - anti_tension)
        confidence = (alignment_score + anti_tension) / 2.0
        relational_coherence = round(max(0.0, min(1.0, (0.6 * agreement) + (0.4 * confidence))), 4)
        if tension_score >= 0.7 and alignment_score < 0.4:
            recommended_mode = "decompress_and_repair"
        elif dominant_signal.startswith("foreground:attack") or dominant_signal == "tension":
            recommended_mode = "validate_before_solve"
        elif alignment_score >= 0.55 and tension_score <= 0.35:
            recommended_mode = "collaborative_progress"
        else:
            recommended_mode = "observe_and_clarify"
        return {
            "tension_score": round(tension_score, 4),
            "alignment_score": round(alignment_score, 4),
            "dominant_signal": dominant_signal,
            "relation_safety_score": relation_safety_score,
            "relational_coherence": relational_coherence,
            "recommended_mode": recommended_mode,
        }

    def _load_relation_memory_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if not self._relation_memory_dir.exists():
            return rows
        for path in sorted(self._relation_memory_dir.glob("*.json")):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return rows

    def _relation_pattern_key(self, *, risk_state: str, dominant_signal: str, receiver_resonance_score: float) -> str:
        resonance_bucket = "low" if receiver_resonance_score < 0.35 else "mid" if receiver_resonance_score < 0.7 else "high"
        return f"{risk_state}:{dominant_signal}:{resonance_bucket}"

    def _build_relation_memory_context(
        self,
        *,
        ledger,
        relational_summary: dict[str, Any] | None,
        base_risk_summary: dict[str, Any],
    ) -> dict[str, Any] | None:
        if ledger is None or not relational_summary:
            return None
        outcome = getattr(ledger, "outcome", None)
        receiver_resonance_score = (
            float(getattr(outcome, "receiver_resonance_score", 0.0) or 0.0)
            if outcome is not None
            else 0.0
        )
        pattern_key = self._relation_pattern_key(
            risk_state=str(base_risk_summary.get("risk_state") or "watch"),
            dominant_signal=str(relational_summary.get("dominant_signal") or "unknown"),
            receiver_resonance_score=receiver_resonance_score,
        )
        cycle_id = str(getattr(ledger, "cycle_id", "") or "")
        matched = [
            row for row in self._load_relation_memory_rows()
            if row.get("cycle_id") != cycle_id and row.get("pattern_key") == pattern_key
        ]
        if not matched:
            return {
                "pattern_key": pattern_key,
                "match_count": 0,
                "incident_count": 0,
                "reject_count": 0,
                "approve_count": 0,
                "policy_adjusted": False,
            }
        incident_count = sum(1 for row in matched if bool(row.get("incident_published")))
        reject_count = sum(1 for row in matched if str(row.get("review_decision") or "") in {"rejected", "closed"})
        approve_count = sum(1 for row in matched if str(row.get("review_decision") or "") == "approved")
        return {
            "pattern_key": pattern_key,
            "match_count": len(matched),
            "incident_count": incident_count,
            "reject_count": reject_count,
            "approve_count": approve_count,
            "policy_adjusted": False,
        }

    def _build_preroute_relation_memory_context(
        self,
        *,
        item: dict[str, Any],
        relational_summary: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not relational_summary:
            return None
        receiver_resonance_score = float(item.get("_resonance_score", 0.0) or 0.0)
        base_risk_summary = self._build_relation_risk_summary(relational_summary)
        pattern_key = self._relation_pattern_key(
            risk_state=str(base_risk_summary.get("risk_state") or "watch"),
            dominant_signal=str(relational_summary.get("dominant_signal") or "unknown"),
            receiver_resonance_score=receiver_resonance_score,
        )
        cycle_id = str(item.get("_cycle_id") or "")
        matched = [
            row for row in self._load_relation_memory_rows()
            if row.get("cycle_id") != cycle_id and row.get("pattern_key") == pattern_key
        ]
        if not matched:
            return {
                "pattern_key": pattern_key,
                "match_count": 0,
                "incident_count": 0,
                "reject_count": 0,
                "approve_count": 0,
                "policy_adjusted": False,
            }
        incident_count = sum(1 for row in matched if bool(row.get("incident_published")))
        reject_count = sum(1 for row in matched if str(row.get("review_decision") or "") in {"rejected", "closed"})
        approve_count = sum(1 for row in matched if str(row.get("review_decision") or "") == "approved")
        return {
            "pattern_key": pattern_key,
            "match_count": len(matched),
            "incident_count": incident_count,
            "reject_count": reject_count,
            "approve_count": approve_count,
            "policy_adjusted": False,
        }

    def _apply_relation_memory_route_policy(
        self,
        *,
        item: dict[str, Any],
        path_decision: Any,
        graph_mode: str,
        available_backends: list[str],
    ) -> dict[str, Any]:
        path_meta = (
            path_decision.to_dict()
            if hasattr(path_decision, "to_dict")
            else dict(path_decision or {})
        )
        relational_summary = self._build_relational_quality_summary(item.get("_relational_field"))
        if not relational_summary:
            return path_meta
        memory_context = self._build_preroute_relation_memory_context(
            item=item,
            relational_summary=relational_summary,
        )
        risk_summary = self._build_relation_risk_summary(
            relational_summary,
            memory_context=memory_context,
        )
        adjusted_memory = (risk_summary.get("memory_context") or {})
        route_policy = {
            "pattern_key": adjusted_memory.get("pattern_key"),
            "match_count": int(adjusted_memory.get("match_count") or 0),
            "incident_count": int(adjusted_memory.get("incident_count") or 0),
            "reject_count": int(adjusted_memory.get("reject_count") or 0),
            "approve_count": int(adjusted_memory.get("approve_count") or 0),
            "policy_adjusted": bool(adjusted_memory.get("policy_adjusted")),
            "risk_state": str(risk_summary.get("risk_state") or "watch"),
            "route_strategy": str(risk_summary.get("route_strategy") or "continue_current_route"),
            "safety_mode": str(risk_summary.get("safety_mode") or "normal"),
        }
        path_meta["relation_memory_route_policy"] = route_policy
        path_meta["route_strategy"] = route_policy["route_strategy"]
        path_meta["safety_mode"] = route_policy["safety_mode"]

        should_reroute_local = (
            route_policy["policy_adjusted"]
            and route_policy["route_strategy"] in {"freeze_and_escalate", "repair_then_reroute", "rerun_and_clarify"}
            and "local" in set(available_backends or [])
            and str(path_meta.get("selected_backend") or "") != "local"
        )
        if should_reroute_local:
            previous_route_key = str(path_meta.get("route_key") or "")
            previous_backend = str(path_meta.get("selected_backend") or "")
            path_meta["route_key"] = f"{graph_mode}>local"
            path_meta["selected_backend"] = "local"
            path_meta["reason"] = f"{path_meta.get('reason') or 'route-selected'}|relation-memory-evidence-first"
            path_meta["relation_memory_route_override"] = {
                "previous_route_key": previous_route_key,
                "previous_backend": previous_backend,
                "applied_backend": "local",
            }
        return path_meta

    def _build_relation_risk_summary(
        self,
        relational: dict[str, Any] | None,
        *,
        memory_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if _RELATIONAL_POLICY_OK and _evaluate_relational_policy is not None:
            try:
                return dict(
                    _evaluate_relational_policy(
                        relational,
                        memory_context=memory_context,
                    )
                )
            except Exception as exc:
                logger.debug("ResonanceAgent: relational policy engine failed: %s", exc)
        if not relational:
            return {
                "risk_state": "watch",
                "suggested_operator_action": "Request another cycle before approving.",
                "approval_posture": "evidence_check",
                "route_strategy": "rerun_and_clarify",
                "safety_mode": "evidence_first",
                "requires_human_review": False,
                "rerun_required": True,
                "memory_context": memory_context,
                "policy_engine_version": "resonance-agent-fallback",
                "rule_hits": ["missing_relational_context"],
            }
        tension_score = float(relational.get("tension_score", 0.0) or 0.0)
        alignment_score = float(relational.get("alignment_score", 0.0) or 0.0)
        relation_safety_score = float(relational.get("relation_safety_score", 0.0) or 0.0)
        recommended_mode = str(relational.get("recommended_mode") or "observe_and_clarify")
        if recommended_mode == "decompress_and_repair" or relation_safety_score < 0.3:
            risk_state = "repair"
            action = "Pause approval, reduce tension, and rerun the council after repair."
            approval_posture = "hold_and_repair"
            route_strategy = "repair_then_reroute"
            safety_mode = "repair_first"
            requires_human_review = False
            rerun_required = True
        elif recommended_mode == "validate_before_solve" or tension_score >= 0.6:
            risk_state = "watch"
            action = "Validate intent and evidence before approving this council outcome."
            approval_posture = "evidence_check"
            route_strategy = "validate_current_route"
            safety_mode = "evidence_first"
            requires_human_review = False
            rerun_required = False
        elif recommended_mode == "collaborative_progress" and alignment_score >= 0.55:
            risk_state = "safe"
            action = "Safe to continue with normal operator review."
            approval_posture = "normal_review"
            route_strategy = "continue_current_route"
            safety_mode = "normal"
            requires_human_review = False
            rerun_required = False
        else:
            risk_state = "escalate" if relation_safety_score < 0.15 else "watch"
            action = (
                "Escalate to a human reviewer before approval."
                if risk_state == "escalate"
                else "Observe the next cycle and clarify ambiguous signals before approval."
            )
            approval_posture = "human_escalation" if risk_state == "escalate" else "evidence_check"
            route_strategy = "freeze_and_escalate" if risk_state == "escalate" else "rerun_and_clarify"
            safety_mode = "human_first" if risk_state == "escalate" else "evidence_first"
            requires_human_review = risk_state == "escalate"
            rerun_required = risk_state != "escalate"
        policy_adjusted = False
        if memory_context and int(memory_context.get("match_count") or 0) >= 2:
            repeated_failures = int(memory_context.get("incident_count") or 0) + int(memory_context.get("reject_count") or 0)
            if repeated_failures >= 2 and risk_state in {"watch", "repair"}:
                risk_state = "escalate"
                action = "Escalate to a human reviewer: similar prior relational patterns led to incidents or rejection."
                approval_posture = "human_escalation"
                route_strategy = "freeze_and_escalate"
                safety_mode = "freeze"
                requires_human_review = True
                rerun_required = False
                policy_adjusted = True
        if memory_context is not None:
            memory_context = {**memory_context, "policy_adjusted": policy_adjusted}
        return {
            "risk_state": risk_state,
            "suggested_operator_action": action,
            "approval_posture": approval_posture,
            "route_strategy": route_strategy,
            "safety_mode": safety_mode,
            "requires_human_review": requires_human_review,
            "rerun_required": rerun_required,
            "memory_context": memory_context,
            "policy_engine_version": "resonance-agent-fallback",
            "rule_hits": ["fallback_inline_policy"],
        }

    def _build_cycle_record(
        self, item: dict, output: str, generation_time: float
    ) -> dict:
        """Build a minimal cycle record for the learner."""
        copilot = item.get("_operator_response_output") or item.get("_copilot_output") or {}
        return {
            "resonance_score": item.get("_resonance_score", 0.5),
            "copilot": {
                "active_rules": copilot.get("active_rules") or [],
            },
            "user_feedback": None,
        }
