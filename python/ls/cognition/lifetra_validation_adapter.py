from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from time import time
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from ls.cognition.collective_answer_validator import (
        ValidationInput,
        ValidationResult,
    )


@dataclass(frozen=True)
class ValidationTraceArtifact:
    backend: str
    trace_id: str
    node_count: int
    edge_count: int
    winner_agent_id: str | None
    global_risk_flags: list[str]
    summary: str
    metadata: dict[str, Any]


class ValidationTraceBackend(Protocol):
    def build_validation_trace(
        self,
        payload: ValidationInput,
        result: ValidationResult,
    ) -> ValidationTraceArtifact | None: ...


def _candidate_node_id(agent_id: str) -> str:
    normalized = [
        char.lower()
        if char.isalnum() or char in {"-", "_", ":", "."}
        else "-"
        for char in agent_id.strip()
    ]
    collapsed = "".join(normalized).strip("-") or "unknown"
    return f"candidate:{collapsed}"


def _safe_preview(text: str, limit: int = 80) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    if limit <= 3:
        return compact[:limit]
    return f"{compact[: limit - 3]}..."


def _normalized_text_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return sha256(normalized.encode("utf-8")).hexdigest()[:16]


class LifetraValidationAdapter:
    def __init__(
        self,
        lifetra_module: Any | None = None,
        *,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._lifetra_module = lifetra_module
        self._clock = clock or (lambda: int(time()))

    def build_validation_trace(
        self,
        payload: ValidationInput,
        result: ValidationResult,
    ) -> ValidationTraceArtifact | None:
        module = self._lifetra_module or self._load_lifetra_module()
        if module is None:
            return None

        trajectory = self._build_trajectory(module, payload, result)
        if trajectory is None:
            return None

        nodes = self._build_nodes(payload, result)
        edges = self._build_edges(payload, result)
        summary = trajectory.summary()
        winner_node_id = (
            _candidate_node_id(result.winner_agent_id)
            if result.winner_agent_id is not None
            else None
        )

        metadata = {
            "consensus_status": result.consensus_status,
            "consensus_summary": result.consensus_summary,
            "winner_node_id": winner_node_id,
            "task_prompt_preview": _safe_preview(payload.task_prompt),
            "task_prompt_hash": _normalized_text_hash(payload.task_prompt),
            "accepted_agent_ids": [
                candidate.agent_id
                for candidate in result.ranked_candidates
                if candidate.accepted
            ],
            "rejected_agent_ids": [
                candidate.agent_id
                for candidate in result.ranked_candidates
                if not candidate.accepted
            ],
            "nodes": nodes,
            "edges": edges,
            "trajectory_summary": summary,
        }

        trace_seed = "|".join(
            [
                payload.task_prompt,
                result.consensus_status,
                result.winner_agent_id or "none",
                ",".join(sorted(candidate.agent_id for candidate in result.ranked_candidates)),
            ]
        )
        backend_name = getattr(module, "_backend_name", None) or getattr(
            module,
            "__name__",
            "lifetra_py",
        )
        return ValidationTraceArtifact(
            backend=backend_name,
            trace_id=f"lifetra:{_normalized_text_hash(trace_seed)}",
            node_count=len(nodes),
            edge_count=len(edges),
            winner_agent_id=result.winner_agent_id,
            global_risk_flags=list(result.global_risk_flags),
            summary=summary,
            metadata=metadata,
        )

    @staticmethod
    def _load_lifetra_module() -> Any | None:
        try:
            import lifetra_py
        except ImportError:
            return None
        return lifetra_py

    def _build_trajectory(
        self,
        module: Any,
        payload: ValidationInput,
        result: ValidationResult,
    ) -> Any | None:
        if not all(
            hasattr(module, attr)
            for attr in ("Timestamp", "StateTransition", "TrajectoryState")
        ):
            return None

        trajectory = module.TrajectoryState(
            self._trajectory_stage(result),
            self._trajectory_momentum(result),
            self._trajectory_stability(result),
        )

        event_index = 0
        self._add_transition(
            module,
            trajectory,
            event_index,
            "validation_started",
            (
                f"prompt={_safe_preview(payload.task_prompt)} "
                f"candidates={len(payload.candidates)}"
            ),
        )
        event_index += 1

        payload_by_agent = {candidate.agent_id: candidate for candidate in payload.candidates}
        for validated in result.ranked_candidates:
            candidate = payload_by_agent.get(validated.agent_id)
            if candidate is None:
                continue
            self._add_transition(
                module,
                trajectory,
                event_index,
                f"candidate:{validated.agent_id}",
                (
                    f"accepted={validated.accepted} "
                    f"score={validated.score:.3f} "
                    f"preview={_safe_preview(candidate.answer_text)}"
                ),
            )
            event_index += 1

        for edge in self._build_edges(payload, result):
            self._add_transition(
                module,
                trajectory,
                event_index,
                f"{edge['relation']}:{edge['source']}->{edge['target']}",
                edge["note"],
            )
            event_index += 1

        self._add_transition(
            module,
            trajectory,
            event_index,
            "validation_completed",
            (
                f"winner={result.winner_agent_id or 'none'} "
                f"status={result.consensus_status} "
                f"flags={','.join(result.global_risk_flags) or 'none'}"
            ),
        )
        return trajectory

    def _add_transition(
        self,
        module: Any,
        trajectory: Any,
        event_index: int,
        label: str,
        note: str,
    ) -> None:
        timestamp = module.Timestamp(self._clock() + event_index)
        transition = module.StateTransition(label, timestamp, note)
        trajectory.add_transition(transition)

    @staticmethod
    def _trajectory_stage(result: ValidationResult) -> str:
        mapping = {
            "rejected": "dormant",
            "weak": "stabilizing",
            "convergent": "evolving",
            "conflicted": "transforming",
        }
        return mapping.get(result.consensus_status, "evolving")

    @staticmethod
    def _trajectory_momentum(result: ValidationResult) -> float:
        if not result.ranked_candidates:
            return 0.0
        return max(0.0, min(1.0, result.ranked_candidates[0].score))

    @staticmethod
    def _trajectory_stability(result: ValidationResult) -> float:
        penalty = min(len(result.global_risk_flags) * 0.15, 0.8)
        return max(0.0, min(1.0, 0.85 - penalty))

    @staticmethod
    def _build_nodes(
        payload: ValidationInput,
        result: ValidationResult,
    ) -> list[dict[str, Any]]:
        validated_by_agent = {
            candidate.agent_id: candidate
            for candidate in result.ranked_candidates
        }
        nodes: list[dict[str, Any]] = [
            {
                "id": "task:prompt",
                "kind": "task_prompt",
                "preview": _safe_preview(payload.task_prompt),
                "text_hash": _normalized_text_hash(payload.task_prompt),
            }
        ]

        for candidate in payload.candidates:
            validated = validated_by_agent.get(candidate.agent_id)
            if validated is None:
                continue
            nodes.append(
                {
                    "id": _candidate_node_id(candidate.agent_id),
                    "kind": "candidate",
                    "agent_id": candidate.agent_id,
                    "accepted": validated.accepted,
                    "score": validated.score,
                    "preview": _safe_preview(candidate.answer_text),
                    "text_hash": _normalized_text_hash(candidate.answer_text),
                    "risk_flags": list(validated.risk_flags),
                    "reasons": list(validated.reasons),
                }
            )

        nodes.append(
            {
                "id": "validation:result",
                "kind": "validation_result",
                "winner_agent_id": result.winner_agent_id,
                "consensus_status": result.consensus_status,
                "global_risk_flags": list(result.global_risk_flags),
            }
        )
        return nodes

    @staticmethod
    def _build_edges(
        payload: ValidationInput,
        result: ValidationResult,
    ) -> list[dict[str, Any]]:
        validated_by_agent = {
            candidate.agent_id: candidate
            for candidate in result.ranked_candidates
        }
        edges: list[dict[str, Any]] = []

        for candidate in payload.candidates:
            node_id = _candidate_node_id(candidate.agent_id)
            validated = validated_by_agent.get(candidate.agent_id)
            if validated is None:
                continue
            edges.append(
                {
                    "source": "task:prompt",
                    "target": node_id,
                    "relation": "evaluates",
                    "note": (
                        f"candidate={candidate.agent_id} "
                        f"accepted={validated.accepted} "
                        f"score={validated.score:.3f}"
                    ),
                }
            )
            edges.append(
                {
                    "source": node_id,
                    "target": "validation:result",
                    "relation": "accepted" if validated.accepted else "rejected",
                    "note": (
                        f"candidate={candidate.agent_id} "
                        f"flags={','.join(validated.risk_flags) or 'none'}"
                    ),
                }
            )

            for target_agent_id in candidate.supports:
                edges.append(
                    {
                        "source": node_id,
                        "target": _candidate_node_id(target_agent_id),
                        "relation": "supports",
                        "note": f"{candidate.agent_id} supports {target_agent_id}",
                    }
                )
            for target_agent_id in candidate.contradicts:
                edges.append(
                    {
                        "source": node_id,
                        "target": _candidate_node_id(target_agent_id),
                        "relation": "contradicts",
                        "note": f"{candidate.agent_id} contradicts {target_agent_id}",
                    }
                )

        if result.winner_agent_id is not None:
            edges.append(
                {
                    "source": _candidate_node_id(result.winner_agent_id),
                    "target": "validation:result",
                    "relation": "winner",
                    "note": f"winner={result.winner_agent_id}",
                }
            )

        return edges
