from __future__ import annotations

from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
)
from ls.cognition.lifetra_validation_adapter import LifetraValidationAdapter


class _FakeTimestamp:
    def __init__(self, epoch_seconds: int) -> None:
        self.epoch_seconds = epoch_seconds


class _FakeStateTransition:
    def __init__(self, label: str, occurred_at: _FakeTimestamp, note: str) -> None:
        self.label = label
        self.occurred_at = occurred_at
        self.note = note


class _FakeTrajectoryState:
    def __init__(self, stage: str, momentum: float, stability: float) -> None:
        self.stage = stage
        self.momentum = momentum
        self.stability = stability
        self.history: list[_FakeStateTransition] = []

    def add_transition(self, transition: _FakeStateTransition) -> None:
        self.history.append(transition)

    def summary(self) -> str:
        latest = self.history[-1].label if self.history else "none"
        return (
            f"TrajectoryState(stage={self.stage}, momentum={self.momentum:.3f}, "
            f"stability={self.stability:.3f}, transitions={len(self.history)}, latest={latest})"
        )


class _FakeLifetraModule:
    _backend_name = "lifetra_py"
    Timestamp = _FakeTimestamp
    StateTransition = _FakeStateTransition
    TrajectoryState = _FakeTrajectoryState


def _adapter() -> LifetraValidationAdapter:
    return LifetraValidationAdapter(
        lifetra_module=_FakeLifetraModule,
        clock=lambda: 1_710_000_000,
    )


def _base_payload() -> ValidationInput:
    return ValidationInput(
        task_prompt="Choose the safest rollout plan.",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Roll out gradually behind a feature flag.",
                relevance=0.92,
                thread_relevance=0.84,
                hallucination_risk=0.08,
                supports=["agent-b"],
            ),
            CandidateAnswer(
                agent_id="agent-b",
                answer_text="Use a staged rollout with monitoring.",
                relevance=0.82,
                thread_relevance=0.79,
                hallucination_risk=0.09,
            ),
            CandidateAnswer(
                agent_id="agent-c",
                answer_text="Ship to everyone immediately.",
                relevance=0.22,
                thread_relevance=0.24,
                hallucination_risk=0.71,
                contradicts=["agent-a"],
            ),
        ],
    )


def _trace_from(payload: ValidationInput):
    result = CollectiveAnswerValidator().validate(payload)
    artifact = _adapter().build_validation_trace(payload, result)
    assert artifact is not None
    return result, artifact


def test_validator_behavior_is_unchanged_without_trace_backend():
    payload = _base_payload()

    result = CollectiveAnswerValidator().validate(payload)

    assert result.winner_agent_id == "agent-a"
    assert result.consensus_status == "convergent"
    assert result.trace_artifact is None


def test_lifetra_adapter_returns_non_null_artifact():
    payload = _base_payload()

    result, artifact = _trace_from(payload)

    assert artifact.backend == "lifetra_py"
    assert artifact.trace_id.startswith("lifetra:")
    assert artifact.node_count == len(payload.candidates) + 2
    assert artifact.edge_count >= len(payload.candidates) * 2
    assert artifact.summary.startswith("TrajectoryState(")
    assert artifact.winner_agent_id == result.winner_agent_id


def test_winner_metadata_is_preserved_in_trace_artifact():
    payload = _base_payload()

    result, artifact = _trace_from(payload)

    assert artifact.winner_agent_id == "agent-a"
    assert artifact.metadata["winner_node_id"] == "candidate:agent-a"
    assert artifact.metadata["consensus_status"] == result.consensus_status


def test_accepted_and_rejected_candidates_are_represented_in_metadata():
    payload = _base_payload()

    _, artifact = _trace_from(payload)

    assert artifact.metadata["accepted_agent_ids"] == ["agent-a", "agent-b"]
    assert artifact.metadata["rejected_agent_ids"] == ["agent-c"]


def test_support_and_contradiction_relations_are_emitted():
    payload = _base_payload()

    _, artifact = _trace_from(payload)

    relations = {
        (edge["source"], edge["target"], edge["relation"])
        for edge in artifact.metadata["edges"]
    }
    assert ("candidate:agent-a", "candidate:agent-b", "supports") in relations
    assert ("candidate:agent-c", "candidate:agent-a", "contradicts") in relations


def test_global_risk_flags_propagate_into_trace_artifact():
    payload = ValidationInput(
        task_prompt="Should we choose strategy A or strategy B?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-1",
                answer_text="Choose strategy A for throughput.",
                relevance=0.86,
                thread_relevance=0.80,
                hallucination_risk=0.10,
                contradicts=["agent-2"],
            ),
            CandidateAnswer(
                agent_id="agent-2",
                answer_text="Choose strategy B for lower latency.",
                relevance=0.84,
                thread_relevance=0.79,
                hallucination_risk=0.11,
                contradicts=["agent-1"],
            ),
        ],
    )

    result, artifact = _trace_from(payload)

    assert "conflict_between_top_candidates" in result.global_risk_flags
    assert artifact.global_risk_flags == result.global_risk_flags


def test_empty_and_compact_previews_do_not_break_trace_generation():
    payload = ValidationInput(
        task_prompt="   ",
        candidates=[
            CandidateAnswer(
                agent_id="silent-agent",
                answer_text="  ",
                relevance=0.45,
                thread_relevance=0.45,
                hallucination_risk=0.10,
            ),
            CandidateAnswer(
                agent_id="brief-agent",
                answer_text="ok",
                relevance=0.31,
                thread_relevance=0.31,
                hallucination_risk=0.10,
            ),
        ],
    )

    _, artifact = _trace_from(payload)

    nodes = {node["id"]: node for node in artifact.metadata["nodes"]}
    assert nodes["task:prompt"]["preview"] == ""
    assert nodes["candidate:silent-agent"]["preview"] == ""
    assert nodes["candidate:brief-agent"]["preview"] == "ok"
