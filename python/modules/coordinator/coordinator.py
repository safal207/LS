"""
C ? Coordinator Module

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
    C ? Coordinator (?????????? ????)

    v0.1: Skeleton ? defines interface and contract.
    v0.2: Will implement mode selection logic.
    v0.3: Will add adaptive heuristics.
    """

    def __init__(self):
        """Initialize coordinator with sub-modules."""
        from .mode_detector import ModeDetector
        from .context_sync import ContextSync
        from .cognitive_hygiene import CognitiveHygiene

        self.mode_detector = ModeDetector()
        self.context_sync = ContextSync()
        self.hygiene = CognitiveHygiene()

        # Metadata
        self.last_decision: Optional[CoordinationDecision] = None
        self.decision_history: list[CoordinationDecision] = []

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
            - if input is simple AND not under load ? "A"
            - else if input is complex OR requires explanation ? "B"
            - else ? "both" (for verification)
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
            1. choose_mode() ? pick A, B, or both
            2. execute A or B (done by caller)
            3. sync_context() ? merge results
            4. cleanup() ? cognitive hygiene
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
