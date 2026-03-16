from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .cognitive_transaction import CognitiveTransaction


CREATION_EVENT_WEIGHTS: dict[str, float] = {
    "idea_created": 1.0,
    "code_commit": 2.5,
    "model_published": 3.0,
    "agent_improved": 1.5,
    "prediction_submitted": 1.0,
    "decision_resolved": 2.0,
}


@dataclass(frozen=True)
class CreationMetric:
    action: str
    weight: float
    tx_id: str
    timestamp: str
    actor: str


class CreationFeedbackLayer:
    """Tracks creation micro-events and exposes visible growth snapshots.

    This layer plugs into the cognitive transaction ledger and converts a stream
    of creator actions into:
      * cumulative creation score
      * weighted progress counters
      * time-series trajectory suitable for visualization
      * simple idea lineage map (idea -> spawned descendants)
    """

    def __init__(self, event_weights: dict[str, float] | None = None) -> None:
        self.event_weights = event_weights or CREATION_EVENT_WEIGHTS
        self.metrics: list[CreationMetric] = []
        self._score = 0.0
        self._counts: dict[str, int] = defaultdict(int)
        self._weighted_counts: dict[str, float] = defaultdict(float)
        self._trajectory: list[dict[str, Any]] = []
        self._lineage_children: dict[str, list[str]] = defaultdict(list)

    @property
    def creation_score(self) -> float:
        return self._score

    def ingest_transaction(self, tx: CognitiveTransaction) -> bool:
        """Capture one transaction if it is part of the creation loop.

        Returns True if the transaction was counted as a creation event.
        """
        weight = self.event_weights.get(tx.action)
        if weight is None:
            return False

        self.metrics.append(
            CreationMetric(
                action=tx.action,
                weight=weight,
                tx_id=tx.tx_id,
                timestamp=tx.timestamp,
                actor=tx.actor,
            )
        )

        self._score += weight
        self._counts[tx.action] += 1
        self._weighted_counts[tx.action] += weight

        self._trajectory.append(
            {
                "timestamp": tx.timestamp,
                "tx_id": tx.tx_id,
                "action": tx.action,
                "score": round(self._score, 4),
            }
        )

        parent_idea_tx_id = tx.payload.get("parent_idea_tx_id")
        if isinstance(parent_idea_tx_id, str) and parent_idea_tx_id:
            self._lineage_children[parent_idea_tx_id].append(tx.tx_id)

        return True

    def snapshot(self) -> dict[str, Any]:
        return {
            "creation_score": round(self._score, 4),
            "events_total": len(self.metrics),
            "counts": dict(self._counts),
            "weighted_counts": {k: round(v, 4) for k, v in self._weighted_counts.items()},
            "trajectory": list(self._trajectory),
            "idea_lineage": dict(self._lineage_children),
        }
