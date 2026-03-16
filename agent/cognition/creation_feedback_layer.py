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


@dataclass(frozen=True)
class CreationLoopFeedback:
    """Per-step micro feedback: reflection reward + CEL payload + LTP update."""

    tx_id: str
    actor: str
    action: str
    micro_reward: float
    prediction_error: float
    contribution_score: float
    quality_score: float
    ltp_score: float
    reflection_event: dict[str, Any]
    cel_decision_payload: dict[str, Any]
    ltp_update: dict[str, Any]


class CreationFeedbackLayer:
    """Tracks creation micro-events and exposes visible growth snapshots."""

    def __init__(self, event_weights: dict[str, float] | None = None) -> None:
        self.event_weights = event_weights or CREATION_EVENT_WEIGHTS
        self.metrics: list[CreationMetric] = []
        self._score = 0.0
        self._counts: dict[str, int] = defaultdict(int)
        self._weighted_counts: dict[str, float] = defaultdict(float)
        self._trajectory: list[dict[str, Any]] = []
        self._lineage_children: dict[str, list[str]] = defaultdict(list)
        self._expected_reward_by_actor: dict[str, float] = defaultdict(float)
        self._ltp_score_by_actor: dict[str, float] = defaultdict(float)

    @property
    def creation_score(self) -> float:
        return self._score

    def ingest_transaction(self, tx: CognitiveTransaction) -> bool:
        """Capture one transaction if it is part of the creation loop."""
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

    def process_micro_step(
        self,
        tx: CognitiveTransaction,
        *,
        quality_score: float = 0.7,
        expected_reward: float | None = None,
    ) -> CreationLoopFeedback | None:
        """Run one RL-like micro loop: reward -> CEL decision payload -> LTP update.

        Returns None for non-creation transactions.
        """
        if not self.ingest_transaction(tx):
            return None

        if not 0 <= quality_score <= 1:
            raise ValueError("quality_score must be in [0,1]")

        weight = self.event_weights[tx.action]
        baseline = self._expected_reward_by_actor[tx.actor]
        if expected_reward is not None:
            baseline = expected_reward

        prediction_error = weight - baseline
        micro_reward = max(0.0, weight + (0.5 * prediction_error))

        # TD-like expectation update per actor.
        self._expected_reward_by_actor[tx.actor] = baseline + (0.2 * prediction_error)

        contribution_score = _clamp01(micro_reward / 3.0)
        current_ltp = self._ltp_score_by_actor[tx.actor]
        ltp_score = _clamp01(current_ltp + (0.20 * quality_score) + (0.15 * contribution_score))
        self._ltp_score_by_actor[tx.actor] = ltp_score

        reflection_event = {
            "type": "reflection_micro_reward",
            "tx_id": tx.tx_id,
            "actor": tx.actor,
            "action": tx.action,
            "micro_reward": round(micro_reward, 4),
            "prediction_error": round(prediction_error, 4),
            "quality_score": round(quality_score, 4),
        }
        cel_decision_payload = {
            "type": "cel_decision_micro",
            "trace_id": tx.payload.get("trace_id", f"trace_{tx.tx_id}"),
            "proposal_id": f"micro_{tx.tx_id}",
            "agent_id": tx.actor,
            "decision_action": tx.action,
            "contribution_score": round(contribution_score, 4),
            "micro_reward": round(micro_reward, 4),
        }
        ltp_update = {
            "type": "ltp_growth_update",
            "actor": tx.actor,
            "source_tx_id": tx.tx_id,
            "ltp_score": round(ltp_score, 4),
            "delta": round(ltp_score - current_ltp, 4),
        }

        return CreationLoopFeedback(
            tx_id=tx.tx_id,
            actor=tx.actor,
            action=tx.action,
            micro_reward=round(micro_reward, 4),
            prediction_error=round(prediction_error, 4),
            contribution_score=round(contribution_score, 4),
            quality_score=round(quality_score, 4),
            ltp_score=round(ltp_score, 4),
            reflection_event=reflection_event,
            cel_decision_payload=cel_decision_payload,
            ltp_update=ltp_update,
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "creation_score": round(self._score, 4),
            "events_total": len(self.metrics),
            "counts": dict(self._counts),
            "weighted_counts": {k: round(v, 4) for k, v in self._weighted_counts.items()},
            "trajectory": list(self._trajectory),
            "idea_lineage": dict(self._lineage_children),
            "actor_profiles": {
                actor: {
                    "expected_reward": round(expected, 4),
                    "ltp_score": round(self._ltp_score_by_actor.get(actor, 0.0), 4),
                }
                for actor, expected in self._expected_reward_by_actor.items()
            },
            "flow_visualization": self.flow_visualization(),
            "mermaid": self.mermaid_diagram(),
        }

    def flow_visualization(self) -> dict[str, Any]:
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
        node_lines = [f'    {node["id"]}["{node["label"]}"]' for node in FLOW_NODES]
        edge_lines = [
            f'    {edge["source"]} -->|{edge["channel"]}| {edge["target"]}'
            for edge in FLOW_EDGES
        ]
        return "\n".join(["flowchart TD", *node_lines, *edge_lines])


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
