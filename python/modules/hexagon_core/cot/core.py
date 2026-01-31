import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

from ..belief.lifecycle import BeliefLifecycleManager, ConvictStatus
from ..causal.graph import CausalGraph
from ..mission.state import MissionState
from ..config import COTConfig
from .alignment import AlignmentSystem

logger = logging.getLogger("COTCore")

class COTCore:
    """
    Chain of Thought (COT) Core.
    Manages the OODA loop for cognitive processes: Observe, Orient, Decide, Adjust.
    """
    def __init__(self, lifecycle: BeliefLifecycleManager, causal_graph: CausalGraph, mission_state: MissionState):
        self.lifecycle = lifecycle
        self.causal_graph = causal_graph
        self.mission = mission_state
        self.config = COTConfig() # Load config
        self.alignment_system = AlignmentSystem(mission_state)

        self._last_cycle_time = 0.0
        self._belief_count_at_last_cycle = 0

        # Circuit Breaker
        self.consecutive_failures = 0
        self.circuit_open = False

    def run_cot_cycle(self, force: bool = False):
        """
        Executes the COT loop.
        """
        if self.circuit_open:
            logger.error("Circuit breaker OPEN — skipping COT cycle.")
            return

        try:
            now_ts = time.time()
            current_belief_count = self.lifecycle.get_belief_count()

            # Check triggers
            time_diff = (now_ts - self._last_cycle_time) / 60.0
            count_diff = current_belief_count - self._belief_count_at_last_cycle

            if not force:
                if time_diff < self.config.cot_frequency_minutes and count_diff < 10:
                    return

            logger.info("🔄 Starting COT Cycle...")

            # 1. OBSERVE
            active_beliefs = self.lifecycle.get_active_beliefs()
            # detect_contradictions is now handled by maybe_update_cognitive_state separately

            # 2. ORIENT
            aligned_beliefs = []
            for belief in active_beliefs:
                alignment = self.alignment_system.calculate_alignment(belief.belief)
                trajectory = self.alignment_system.calculate_trajectory(belief.id, self.causal_graph)

                # Store/Update metadata with orientation info
                belief.metadata["cot_alignment"] = alignment
                belief.metadata["cot_trajectory"] = trajectory

                if alignment > 0.6 and trajectory > 0.4:
                    aligned_beliefs.append(belief)

            # 3. DECIDE
            # Promotion
            promoted = []
            if self.config.enable_auto_promotion:
                promoted = self.lifecycle.promote_mature_beliefs()
            else:
                # Just check candidates and log
                utc_now = datetime.now(timezone.utc)
                for belief in aligned_beliefs:
                    can_promote, reason = self.lifecycle.promotion_system.can_be_promoted(belief, utc_now)
                    if can_promote:
                        logger.info(f"💡 Candidate for promotion: {belief.belief}")

            # 4. ADJUST
            if promoted:
                logger.info(f"🚀 Auto-promoted {len(promoted)} beliefs.")
                # Sync to mission
                for p in promoted:
                    self.mission.add_convict({
                        "belief": p.belief,
                        "confidence": p.confidence,
                        "strength": p.strength,
                        "origin": "promotion",
                        "id": p.id
                    })

            self._last_cycle_time = now_ts
            self._belief_count_at_last_cycle = current_belief_count

            # Reset circuit breaker on success
            self.consecutive_failures = 0

            logger.info("✅ COT Cycle Complete.")

        except Exception as e:
            self.consecutive_failures += 1
            if self.consecutive_failures >= 3:
                self.circuit_open = True
                logger.error("Circuit breaker OPENED due to repeated failures.")
            logger.error(f"❌ COT cycle failed: {e}", exc_info=True)
