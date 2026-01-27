import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

logger = logging.getLogger("CTE")


@dataclass
class LiminalAnchor:
    id: str
    decision: str
    alternatives: List[str]
    commitment: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "locked"  # locked -> resolved -> archived


@dataclass
class InsightNode:
    id: str
    parent_anchor_id: str
    content: str
    outcome_type: str  # "insight" | "conflict"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class CognitiveTimelineEngine:
    """
    Minimal CTE:
    - Liminal Anchors (Choice)
    - Insights/Conflicts (Consequences)
    - Causal Chain: Choice -> Outcome
    """

    def __init__(self) -> None:
        self._anchors: Dict[str, LiminalAnchor] = {}
        self._insights: Dict[str, InsightNode] = {}
        self.active_anchor_id: Optional[str] = None
        self._trajectory: List[str] = []  # Stores node IDs in chronological order

    # --------- Liminal Transition API ---------

    def commit_transition(self, decision: str, alternatives: Optional[List[str]] = None,
                          commitment: float = 0.9) -> str:
        """
        Creates a liminal anchor (decision point).
        """
        if alternatives is None:
            alternatives = []

        anchor_id = f"anchor_{int(datetime.now().timestamp())}"
        anchor = LiminalAnchor(
            id=anchor_id,
            decision=decision,
            alternatives=alternatives,
            commitment=commitment,
        )
        self._anchors[anchor_id] = anchor
        self.active_anchor_id = anchor_id
        self._trajectory.append(anchor_id)

        logger.info(
            f"🔒 LIMINAL LOCK: '{decision}' (commitment={commitment}, alternatives={alternatives})"
        )
        return anchor_id

    def check_oscillation(self, new_proposal: str) -> bool:
        """
        Checks if the new proposal contradicts the active anchor.
        Returns True if oscillation (waffling) is detected.
        """
        if not self.active_anchor_id:
            return False

        anchor = self._anchors.get(self.active_anchor_id)
        if not anchor or anchor.status != "locked":
            return False

        # Simple heuristic: if new proposal explicitly contradicts the decision.
        # In a real system, this would use semantic comparison.
        if new_proposal.strip().lower() != anchor.decision.strip().lower():
            logger.warning(
                f"🛡️ REJECTING OSCILLATION: committed to '{anchor.decision}', got '{new_proposal}'"
            )
            return True
        return False

    def register_outcome(self, content: str, outcome_type: str = "insight") -> Optional[str]:
        """
        Registers an outcome (insight/conflict) for the active anchor.
        Closes the causal loop: Choice -> Outcome.
        """
        if not self.active_anchor_id:
            logger.warning("⚠️ Outcome without active anchor.")
            return None

        anchor = self._anchors.get(self.active_anchor_id)
        if not anchor:
            logger.warning("⚠️ Active anchor not found in registry.")
            return None

        insight_id = f"insight_{int(datetime.now().timestamp())}"
        node = InsightNode(
            id=insight_id,
            parent_anchor_id=anchor.id,
            content=content,
            outcome_type=outcome_type,
        )
        self._insights[insight_id] = node
        self._trajectory.append(insight_id)

        anchor.status = "resolved"
        logger.info(
            f"💡 {outcome_type.upper()}: '{content}' derived from '{anchor.decision}'"
        )

        # Reset active anchor — cycle complete
        self.active_anchor_id = None
        return insight_id

    # --------- Read-only views for CaPUv3 ---------

    def export_summary(self) -> Dict[str, Any]:
        """
        Brief snapshot of CTE for prompt inclusion:
        - Active anchor (or last relevant one)
        - Last outcome
        """
        active_anchor = None
        if self.active_anchor_id:
            active_anchor = self._anchors.get(self.active_anchor_id)
        else:
            # Fallback: Find the last anchor in trajectory
            for node_id in reversed(self._trajectory):
                if node_id.startswith("anchor"):
                    active_anchor = self._anchors.get(node_id)
                    break

        last_insight: Optional[InsightNode] = None
        # Find last insight in trajectory
        for node_id in reversed(self._trajectory):
            if node_id.startswith("insight"):
                last_insight = self._insights.get(node_id)
                if last_insight:
                    break

        summary: Dict[str, Any] = {}
        if active_anchor:
            summary["active_anchor"] = {
                "decision": active_anchor.decision,
                "commitment": active_anchor.commitment,
                "status": active_anchor.status,
            }
        if last_insight:
            summary["last_outcome"] = {
                "content": last_insight.content,
                "type": last_insight.outcome_type,
                "from_decision": last_insight.parent_anchor_id,
            }
        return summary
