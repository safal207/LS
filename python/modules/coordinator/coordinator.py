"""
C - Coordinator Module

Part of Behavior Codex (docs/BEHAVIOR_CODEX.md)

Responsibility:
- Choose between Mode A (fast) and Mode B (deep)
- Synchronize context between modes
- Maintain cognitive hygiene
- Pass all data to Temporal Spine (D)

Rule: C has final word on mode selection.
Rule: C never modifies A/B results, only selects and syncs.
Rule: C always passes data to D (observability).
"""

from typing import Literal, Optional, Dict, Any
from dataclasses import dataclass
import time


@dataclass
class CoordinationDecision:
    """Result of C's decision-making."""
    mode: Literal["A", "B", "both"]
    reason: str
    confidence: float
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "reason": self.reason,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


class Coordinator:
    """
    C - Coordinator
    
    v0.1: Skeleton - defines interface and contract.
    v0.2: Will implement mode selection logic.
    v0.3: Will add adaptive heuristics.
    """

    def __init__(self):
        """Initialize coordinator with sub-modules."""
        from .mode_detector import ModeDetector
        from .context_sync import ContextSync
        from .cognitive_hygiene import CognitiveHygiene
        from orientation import OrientationCenter

        self.mode_detector = ModeDetector()
        self.context_sync = ContextSync()
        self.hygiene = CognitiveHygiene()
        self.orientation = OrientationCenter()

        # Metadata
        self.last_decision: Optional[CoordinationDecision] = None
        self.decision_history: list[CoordinationDecision] = []
        self.last_orientation: Optional[Dict[str, Any]] = None

    def _build_orientation_inputs(
        self,
        telemetry: Optional[Dict[str, Any]],
        retrospective: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        telemetry = telemetry or {}
        retrospective = retrospective or {}

        history_stats = {
            "diversity_score": telemetry.get("diversity_score", telemetry.get("diversity", 0.0)),
            "entropy": telemetry.get("entropy", 0.0),
            "unique_paths": telemetry.get("unique_paths", 0.0),
            "total_paths": telemetry.get("total_paths", 0.0),
        }

        beliefs = retrospective.get("beliefs")
        if beliefs is None and "stability" in retrospective:
            beliefs = [{"age": 1.0, "support": float(retrospective.get("stability", 0.0))}]

        temporal_metrics = {
            "contradiction_rate": retrospective.get("contradiction_rate", retrospective.get("contradictions", 0.0)),
            "short_term_trend": retrospective.get("short_term_trend", 0.0),
            "long_term_trend": retrospective.get("long_term_trend", 0.0),
        }

        immunity_signals = {
            "drift_pressure": retrospective.get("drift_pressure", retrospective.get("drift", 0.0)),
            "anomaly_rate": retrospective.get("anomaly_rate", 0.0),
            "bias_flags": retrospective.get("bias_flags", 0.0),
            "drift_signals": retrospective.get("drift_signals", []),
        }

        conviction_inputs = {
            "confidence_budget": retrospective.get("confidence_budget", retrospective.get("confidence", 0.0)),
            "support_level": retrospective.get("support_level", 0.0),
            "diversity_of_evidence": retrospective.get("diversity_of_evidence", 0.0),
            "conflict_level": retrospective.get("conflict_level", 0.0),
            "belief_age": retrospective.get("belief_age", 0.0),
        }

        return {
            "history_stats": history_stats,
            "beliefs": beliefs,
            "temporal_metrics": temporal_metrics,
            "immunity_signals": immunity_signals,
            "conviction_inputs": conviction_inputs,
        }

    def choose_mode(
        self,
        input_data: str,
        context: Dict[str, Any],
        system_load: float = 0.0,
    ) -> CoordinationDecision:
        """
        C FUNCTION 1: Determine which mode(s) to activate.

        Args:
            input_data: User query or system event
            context: Current cognitive context
            system_load: System load (0.0 to 1.0)

        Returns:
            CoordinationDecision with mode choice and reasoning

        Priority (Codex section 7):
            1. Context integrity
            2. Correctness
            3. Explainability
            4. Speed
            5. Pattern evolution

        Decision logic (v0.1 skeleton):
            - if input is simple AND not under load -> "A"
            - else if input is complex OR requires explanation -> "B"
            - else -> "both" (for verification)
        """
        analysis = self.mode_detector.analyze(
            input_data=input_data,
            context=context,
            system_load=system_load,
        )

        confidence = max(0.1, 1.0 - float(getattr(analysis, "ambiguity_score", 0.0)))
        decision = CoordinationDecision(
            mode=analysis.mode,
            reason=analysis.reason,
            confidence=confidence,
            timestamp=time.time(),
        )

        self.last_decision = decision
        self.decision_history.append(decision)

        return decision

    def decide(
        self,
        input_data: str,
        context: Dict[str, Any],
        system_load: float = 0.0,
        *,
        telemetry: Optional[Dict[str, Any]] = None,
        retrospective: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Skeleton integration with Orientation Center.

        Returns a dict with the selected mode and orientation signal.
        Does not change decision logic.
        """
        orientation_inputs = self._build_orientation_inputs(telemetry, retrospective)
        orientation_output = self.orientation.evaluate(**orientation_inputs)
        self.last_orientation = orientation_output.to_dict()

        weight = self._compute_orientation_weight(self.last_orientation.get("rhythm_phase"))
        tendency = self._compute_orientation_tendency(self.last_orientation)
        self.last_orientation["weight"] = weight
        self.last_orientation["tendency"] = tendency

        decision = self.choose_mode(input_data, context, system_load=system_load)
        payload = decision.to_dict()
        payload["orientation"] = self.last_orientation
        return payload

    def _compute_orientation_weight(self, rhythm_phase: Optional[str]) -> float:
        if rhythm_phase == "inhale":
            return -0.1
        if rhythm_phase == "exhale":
            return 0.1
        return 0.0

    def _compute_orientation_tendency(self, signals: Dict[str, Any]) -> float:
        diversity = float(signals.get("diversity_score", 0.0))
        stability = float(signals.get("stability_score", 0.0))
        contradiction = float(signals.get("contradiction_rate", 0.0))
        drift = float(signals.get("drift_pressure", 0.0))
        confidence = float(signals.get("confidence_budget", 0.0))

        return (
            0.1 * diversity
            + 0.3 * stability
            - 0.3 * contradiction
            - 0.2 * drift
            + 0.2 * confidence
        )

    def sync_context(
        self,
        mode_a_result: Optional[Any],
        mode_b_result: Optional[Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        C FUNCTION 2: Synchronize results between modes.

        Args:
            mode_a_result: Output from Mode A (if executed)
            mode_b_result: Output from Mode B (if executed)
            context: Current context to update

        Returns:
            Updated context with merged results

        Guarantee (Codex section 8):
            - Context integrity is maintained
            - No data is lost
            - State is consistent
        """
        synced = self.context_sync.merge(
            mode_a_result=mode_a_result,
            mode_b_result=mode_b_result,
            context=context,
        )

        return synced

    def cleanup(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        C FUNCTION 3: Cognitive hygiene.

        Args:
            context: Current context

        Returns:
            Cleaned context

        Cleans:
            - Remove noise
            - Prevent cycles
            - Normalize context
            - Control pace and rhythm
        """
        cleaned = self.hygiene.clean(context=context)

        return cleaned

    def finalize(
        self,
        mode_result: Any,
        context: Dict[str, Any],
    ) -> tuple[Any, Dict[str, Any]]:
        """
        C MAIN ORCHESTRATOR: Full coordination pipeline.

        Sequence (Codex section 6):
            1. choose_mode() -> pick A, B, or both
            2. execute A or B (done by caller)
            3. sync_context() -> merge results
            4. cleanup() -> cognitive hygiene
            5. return finalized result and context

        This is the method that AgentLoop calls.
        """
        # Sync the result into context
        context = self.sync_context(
            mode_a_result=mode_result if isinstance(mode_result, dict) else None,
            mode_b_result=mode_result if isinstance(mode_result, dict) else None,
            context=context,
        )

        # Clean up
        context = self.cleanup(context)

        return mode_result, context
