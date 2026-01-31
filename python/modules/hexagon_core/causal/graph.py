import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
import logging

from .cycle_detector import CycleDetector
# from .temporal_index import TemporalIndex # Optional for now

logger = logging.getLogger("CausalGraph")

@dataclass
class CausalEdge:
    cause_id: str
    effect_id: str
    timestamp: datetime
    weight: float
    context: Dict[str, Any]

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

    def add_causal_link(self, cause_id: str, effect_id: str, weight: float, context: Dict[str, Any] = None) -> bool:
        with self._lock:
            # 1. Cycle Check
            # Build simple graph for detector
            simple_graph = {k: [e.effect_id for e in v] for k, v in self._downstream.items()}

            if self._cycle_detector.has_path(simple_graph, effect_id, cause_id):
                logger.warning(f"⛔ Cycle detected: Cannot add {cause_id} -> {effect_id}")
                return False

            if context is None: context = {}

            edge = CausalEdge(
                cause_id=cause_id,
                effect_id=effect_id,
                timestamp=datetime.now(timezone.utc),
                weight=weight,
                context=context
            )

            self._edges.append(edge)

            if effect_id not in self._upstream: self._upstream[effect_id] = []
            self._upstream[effect_id].append(edge)

            if cause_id not in self._downstream: self._downstream[cause_id] = []
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
            # Find edges to remove
            to_remove = []
            for edge in self._edges:
                if edge.cause_id == convict_id or edge.effect_id == convict_id:
                    to_remove.append(edge)

            for edge in to_remove:
                self._edges.remove(edge)

                # Update indices
                if edge in self._upstream.get(edge.effect_id, []):
                    self._upstream[edge.effect_id].remove(edge)

                if edge in self._downstream.get(edge.cause_id, []):
                    self._downstream[edge.cause_id].remove(edge)

            if to_remove:
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
