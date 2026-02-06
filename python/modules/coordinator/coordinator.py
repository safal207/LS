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
        from .adaptive_bias import AdaptiveBias
        from .confidence_dynamics import ConfidenceDynamics
        from .field_coordination import FieldCoordination
        from .meta_adaptation import MetaAdaptationLayer
        from .meta_hygiene import MetaHygiene
        from orientation import OrientationCenter
        from trajectory import TrajectoryLayer
        from field import ConsensusEngine

        self.mode_detector = ModeDetector()
        self.context_sync = ContextSync()
        self.hygiene = CognitiveHygiene()
        self.adaptive = AdaptiveBias()
        self.confidence_dynamics = ConfidenceDynamics()
        self.field_coordination = FieldCoordination()
        self.consensus = ConsensusEngine()
        self.meta = MetaAdaptationLayer()
        self.meta_hygiene = MetaHygiene()
        self.orientation = OrientationCenter()
        self.trajectory = TrajectoryLayer()
        self.field_adapter = None
        self.field_resonance = None
        self.field_bias = None

        # Metadata
        self.last_decision: Optional[CoordinationDecision] = None
        self.decision_history: list[CoordinationDecision] = []
        self.last_orientation: Optional[Dict[str, Any]] = None
        self.last_trajectory_error: Optional[float] = None

    def _build_orientation_inputs(
        self,
        telemetry: Optional[Dict[str, Any]],
        retrospective: Optional[Dict[str, Any]],
    ):
        telemetry = telemetry or {}
        retrospective = retrospective or {}

        history_stats = dict(telemetry)
        if "diversity" in history_stats and "diversity_score" not in history_stats:
            history_stats["diversity_score"] = history_stats["diversity"]

        beliefs = retrospective.get("beliefs")
        if beliefs is None and "stability_score" in retrospective:
            beliefs = [{"stability_score": retrospective.get("stability_score")}]

        temporal_metrics = dict(retrospective.get("temporal_metrics") or {})
        if "contradiction_rate" in retrospective and "contradiction_rate" not in temporal_metrics:
            temporal_metrics["contradiction_rate"] = retrospective.get("contradiction_rate")
        if "contradictions" in retrospective and "contradiction_rate" not in temporal_metrics:
            temporal_metrics["contradiction_rate"] = retrospective.get("contradictions")

        immunity_signals = dict(retrospective.get("immunity_signals") or {})
        if "drift_pressure" in retrospective and "drift_pressure" not in immunity_signals:
            immunity_signals["drift_pressure"] = retrospective.get("drift_pressure")
        if "drift" in retrospective and "drift_pressure" not in immunity_signals:
            immunity_signals["drift_pressure"] = retrospective.get("drift")

        conviction_inputs = dict(retrospective.get("conviction_inputs") or {})
        if "confidence_budget" in retrospective and "confidence_budget" not in conviction_inputs:
            conviction_inputs["confidence_budget"] = retrospective.get("confidence_budget")
        if "confidence" in retrospective and "confidence_budget" not in conviction_inputs:
            conviction_inputs["confidence_budget"] = retrospective.get("confidence")

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
        orientation_output = self.orientation.evaluate(
            **orientation_inputs,
            trajectory_error=self.last_trajectory_error,
        )
        self.last_orientation = orientation_output.to_dict()

        weight = self._compute_orientation_weight(self.last_orientation.get("rhythm_phase"))
        tendency = self._compute_orientation_tendency(self.last_orientation)
        self.last_orientation["weight"] = weight
        self.last_orientation["tendency"] = tendency
        orientation_bias = self.adaptive.compute_orientation_bias(self.last_orientation)
        trajectory_bias = self.adaptive.compute_trajectory_bias(self.last_trajectory_error)
        adaptive_bias = self.adaptive.combine(orientation_bias, trajectory_bias)
        self.last_orientation["orientation_bias"] = orientation_bias
        self.last_orientation["trajectory_bias"] = trajectory_bias
        self.last_orientation["adaptive_bias"] = adaptive_bias

        coordination_bias = 0.0
        if self.field_adapter is not None:
            metrics = self.field_adapter.pull_field_metrics()
            coordination_bias = self.field_coordination.compute(metrics)
        context["coordination_bias"] = coordination_bias

        decision = self.choose_mode(input_data, context, system_load=system_load)
        consensus_adjustment = 0.0
        if self.field_adapter is not None:
            metrics = self.field_adapter.pull_field_metrics()
            consensus_adjustment = self.consensus.compute(
                metrics,
                decision.mode,
                decision.confidence,
            )
        raw_confidence = max(
            0.0,
            min(1.0, decision.confidence + adaptive_bias + coordination_bias),
        )
        raw_confidence = max(0.0, min(1.0, raw_confidence + consensus_adjustment))
        smoothed_confidence = self.confidence_dynamics.update(raw_confidence)
        decision.confidence = smoothed_confidence

        self.meta.update_metrics(
            trajectory_error=self.last_trajectory_error,
            confidence=smoothed_confidence,
        )
        self.meta.adapt_confidence_dynamics(self.confidence_dynamics)
        self.meta.adapt_adaptive_bias(self.adaptive)

        field_bias = {}
        if self.field_adapter is not None and self.field_bias is not None:
            field_bias = self.field_adapter.compute_field_bias(self.field_bias)
            self.confidence_dynamics.alpha += field_bias.get("confidence_bias", 0.0)
            self.confidence_dynamics.max_delta += field_bias.get("trajectory_bias", 0.0)
            self.adaptive.apply_external_bias(field_bias.get("orientation_bias", 0.0))

        self.meta_hygiene.update(
            trajectory_error=self.last_trajectory_error,
            confidence=smoothed_confidence,
        )
        self.meta_hygiene.correct_confidence_dynamics(self.confidence_dynamics)
        self.meta_hygiene.correct_adaptive_bias(self.adaptive)
        payload = decision.to_dict()
        payload["confidence_raw"] = raw_confidence
        payload["confidence_smoothed"] = smoothed_confidence
        payload["orientation"] = self.last_orientation
        payload["field_bias"] = field_bias
        payload["coordination_bias"] = coordination_bias
        payload["consensus_adjustment"] = consensus_adjustment
        snapshot = {
            "orientation": self.last_orientation,
            "confidence": {
                "raw": raw_confidence,
                "smoothed": smoothed_confidence,
            },
            "trajectory": {
                "error": self.last_trajectory_error if self.last_trajectory_error is not None else 0.0,
            },
        }
        if self.field_adapter is not None:
            self.field_adapter.publish_from_ls(snapshot)
        self.trajectory.record_decision(
            decision.mode,
            {
                "orientation": self.last_orientation,
                "system_load": system_load,
            },
        )
        self.last_trajectory_error = self.trajectory.compute_trajectory_error()
        payload["trajectory_error"] = self.last_trajectory_error
        return payload

    def record_outcome(self, outcome: Dict[str, Any]) -> None:
        """
        Skeleton: record the outcome of the last decision.
        """
        self.trajectory.record_outcome(outcome)
        self.last_trajectory_error = self.trajectory.compute_trajectory_error()

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
