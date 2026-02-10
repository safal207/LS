import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, TYPE_CHECKING
import logging

from .cycle_detector import CycleDetector

if TYPE_CHECKING:
    from ..belief.lifecycle import BeliefLifecycleManager

logger = logging.getLogger("CausalGraph")

@dataclass
class CausalEdge:
    cause_id: str
    effect_id: str
    timestamp: datetime
    weight: float
    context: Dict[str, Any]

    def __hash__(self):
        # Hash based on ID and timestamp, ignoring mutable context
        return hash((self.cause_id, self.effect_id, self.timestamp, self.weight))

    def __eq__(self, other):
        if not isinstance(other, CausalEdge):
            return False
        return (self.cause_id == other.cause_id and
                self.effect_id == other.effect_id and
                self.timestamp == other.timestamp and
                self.weight == other.weight)

class CausalGraph:
    """
    Manages cause-and-effect relationships between beliefs (Convicts) or events.
    Thread-safe using RLock.
    """
    def __init__(self):
        self._edges: List[CausalEdge] = []
        # Adjacency lists for fast lookup
        self._upstream: Dict[str, List[CausalEdge]] = {}   # effect -> [edges from causes]
        self._downstream: Dict[str, List[CausalEdge]] = {} # cause -> [edges to effects]

        self._lock = threading.RLock()
        self._cycle_detector = CycleDetector()

    def add_causal_link(self, cause_id: str, effect_id: str, weight: float, context: Dict[str, Any] = None, lifecycle: Optional['BeliefLifecycleManager'] = None) -> bool:
        with self._lock:
            # Validate belief existence
            if lifecycle:
                if not lifecycle.belief_exists(cause_id) or not lifecycle.belief_exists(effect_id):
                    logger.warning(f"❌ Cannot add causal link: {cause_id} or {effect_id} not found in lifecycle")
                    return False

            # 1. Cycle Check
            # Build simple graph for detector
            simple_graph = {k: [e.effect_id for e in v] for k, v in self._downstream.items()}

            if self._cycle_detector.has_path(simple_graph, effect_id, cause_id):
                logger.warning(f"⛔ Cycle detected: Cannot add {cause_id} -> {effect_id}")
                return False

            if context is None:
                context = {}

            edge = CausalEdge(
                cause_id=cause_id,
                effect_id=effect_id,
                timestamp=datetime.now(timezone.utc),
                weight=weight,
                context=context
            )

            self._edges.append(edge)

            if effect_id not in self._upstream:
                self._upstream[effect_id] = []
            self._upstream[effect_id].append(edge)

            if cause_id not in self._downstream:
                self._downstream[cause_id] = []
            self._downstream[cause_id].append(edge)

            logger.info(f"🔗 Causal link added: {cause_id} -> {effect_id} (w={weight:.2f})")
            return True

    def get_upstream(self, node_id: str) -> List[CausalEdge]:
        with self._lock:
            return list(self._upstream.get(node_id, []))

    def get_downstream(self, node_id: str) -> List[CausalEdge]:
        with self._lock:
            return list(self._downstream.get(node_id, []))

    def remove_belief(self, convict_id: str) -> None:
        """
        Removes all links involving this belief.
        """
        with self._lock:
            upstream_edges = self._upstream.get(convict_id, [])
            downstream_edges = self._downstream.get(convict_id, [])

            # Identify edges to remove
            to_remove = set(upstream_edges) | set(downstream_edges)

            if not to_remove:
                return

            # Remove from main list
            self._edges = [e for e in self._edges if e not in to_remove]

            # Remove from indices
            for edge in to_remove:
                # Remove from upstream of effect
                if edge.effect_id in self._upstream:
                    if edge in self._upstream[edge.effect_id]:
                        self._upstream[edge.effect_id].remove(edge)

                # Remove from downstream of cause
                if edge.cause_id in self._downstream:
                    if edge in self._downstream[edge.cause_id]:
                        self._downstream[edge.cause_id].remove(edge)

            logger.info(f"🗑️ Removed {len(to_remove)} causal links for belief {convict_id}")

    def get_edges(self) -> List[CausalEdge]:
         with self._lock:
             return list(self._edges)

    def export_graph(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "nodes_count": len(set(e.cause_id for e in self._edges) | set(e.effect_id for e in self._edges)),
                "edges_count": len(self._edges),
                "edges": [
                    {
                        "cause": e.cause_id,
                        "effect": e.effect_id,
                        "weight": e.weight,
                        "timestamp": e.timestamp.isoformat()
                    }
                    for e in self._edges
                ]
            }
