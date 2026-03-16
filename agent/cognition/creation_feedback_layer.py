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


FLOW_CHANNELS: tuple[str, str, str] = ("dopamine", "economy", "knowledge")


FLOW_NODES: tuple[dict[str, str], ...] = (
    {"id": "cue", "label": "Idea / Cue"},
    {"id": "agent_loop", "label": "AgentLoop"},
    {"id": "causal_memory", "label": "Causal Memory"},
    {"id": "micro_progress", "label": "Micro-step"},
    {"id": "reflection", "label": "Reflection Engine"},
    {"id": "artifact", "label": "Commit / Artifact"},
    {"id": "mel", "label": "MEL: Model Economy"},
    {"id": "icrl", "label": "ICRL Routing"},
    {"id": "cel", "label": "CEL: Decision Economy"},
    {"id": "cem", "label": "Event Mesh / CEM"},
    {"id": "ctl", "label": "Ledger / CTL"},
    {"id": "ltp", "label": "Long-Term Memory / LTP"},
    {"id": "next_cue", "label": "Next Idea / Cue"},
)


FLOW_EDGES: tuple[dict[str, str], ...] = (
    {"source": "cue", "target": "agent_loop", "channel": "dopamine"},
    {"source": "agent_loop", "target": "causal_memory", "channel": "knowledge"},
    {"source": "agent_loop", "target": "micro_progress", "channel": "dopamine"},
    {"source": "micro_progress", "target": "reflection", "channel": "dopamine"},
    {"source": "micro_progress", "target": "artifact", "channel": "knowledge"},
    {"source": "artifact", "target": "mel", "channel": "economy"},
    {"source": "mel", "target": "icrl", "channel": "economy"},
    {"source": "icrl", "target": "cel", "channel": "economy"},
    {"source": "cel", "target": "cem", "channel": "knowledge"},
    {"source": "cem", "target": "ctl", "channel": "knowledge"},
    {"source": "ctl", "target": "ltp", "channel": "knowledge"},
    {"source": "ltp", "target": "next_cue", "channel": "dopamine"},
)


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
            "flow_visualization": self.flow_visualization(),
            "mermaid": self.mermaid_diagram(),
        }

    def flow_visualization(self) -> dict[str, Any]:
        """Return one-frame LS flow map for UI graph rendering.

        The shape intentionally combines creation, motivation, and economy loops
        into a single structure so dashboards can show the full contour of the
        system without additional joins.
        """
        return {
            "channels": list(FLOW_CHANNELS),
            "nodes": [dict(node) for node in FLOW_NODES],
            "edges": [dict(edge) for edge in FLOW_EDGES],
            "summary": {
                "creation_score": round(self._score, 4),
                "events_total": len(self.metrics),
            },
        }

    def mermaid_diagram(self) -> str:
        """Return Mermaid diagram for docs and quick console previews."""
        node_lines = [f'    {node["id"]}["{node["label"]}"]' for node in FLOW_NODES]
        edge_lines = [
            f'    {edge["source"]} -->|{edge["channel"]}| {edge["target"]}'
            for edge in FLOW_EDGES
        ]
        return "\n".join(["flowchart TD", *node_lines, *edge_lines])
