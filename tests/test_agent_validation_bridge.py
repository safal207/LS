from __future__ import annotations

import pytest

from ls.cognition.agent_validation_bridge import (
    AgentValidationBridge,
    BridgeResult,
    CallableAgentHandle,
    _default_candidate_builder,
)
from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _strong_handle(agent_id: str, text: str) -> CallableAgentHandle:
    """Always returns a good answer."""
    return CallableAgentHandle(agent_id=agent_id, fn=lambda _q: text)


def _weak_handle(agent_id: str) -> CallableAgentHandle:
    """Simulates a bad / empty response (returns empty string)."""
    return CallableAgentHandle(agent_id=agent_id, fn=lambda _q: "")


def _scoring_builder(agent_id: str, text: str, task_prompt: str) -> CandidateAnswer:  # noqa: ARG001
    """Scoring function that gives strong scores to non-empty answers."""
    if text.strip():
        return CandidateAnswer(
            agent_id=agent_id,
            answer_text=text,
            relevance=0.90,
            thread_relevance=0.88,
            hallucination_risk=0.05,
        )
    return CandidateAnswer(
        agent_id=agent_id,
        answer_text=text,
        relevance=0.05,
        thread_relevance=0.05,
        hallucination_risk=0.95,
    )


# ── CallableAgentHandle ───────────────────────────────────────────────────────


def test_callable_handle_submit_and_drain():
    handle = _strong_handle("agent-a", "my answer")
    handle.submit("question?")
    response = handle.drain_response(timeout=1.0)
    assert response == "my answer"


def test_callable_handle_drain_clears_pending():
    handle = _strong_handle("agent-a", "answer")
    handle.submit("q")
    handle.drain_response(timeout=1.0)
    # Second drain returns None — no double-counting
    assert handle.drain_response(timeout=1.0) is None


def test_callable_handle_fn_error_gives_none_response():
    def bad_fn(_q: str) -> str:
        raise RuntimeError("crash")

    handle = CallableAgentHandle(agent_id="bad", fn=bad_fn)
    handle.submit("q")
    assert handle.drain_response(timeout=1.0) is None


# ── Default candidate builder ─────────────────────────────────────────────────


def test_default_builder_returns_candidate_with_agent_id():
    ca = _default_candidate_builder("agent-x", "some answer", "task")
    assert ca.agent_id == "agent-x"
    assert ca.answer_text == "some answer"
    assert 0.0 <= ca.relevance <= 1.0
    assert 0.0 <= ca.hallucination_risk <= 1.0


# ── Bridge construction ───────────────────────────────────────────────────────


def test_bridge_requires_at_least_one_handle():
    with pytest.raises(ValueError, match="at least one"):
        AgentValidationBridge(handles=[])


# ── Bridge.submit — happy path ────────────────────────────────────────────────


def test_bridge_returns_bridge_result():
    bridge = AgentValidationBridge(
        handles=[
            _strong_handle("agent-a", "LRU cache with 300s TTL."),
            _strong_handle("agent-b", "TTL-based LRU eviction, 5 minute window."),
        ],
        candidate_builder=_scoring_builder,
    )
    result = bridge.submit("Which cache strategy?")
    assert isinstance(result, BridgeResult)
    assert isinstance(result.validation_result.winner_agent_id, str)


def test_bridge_winner_is_one_of_the_handles():
    handles = [
        _strong_handle("agent-a", "Gradual rollout with flags."),
        _strong_handle("agent-b", "Blue-green deployment."),
    ]
    bridge = AgentValidationBridge(handles=handles, candidate_builder=_scoring_builder)
    result = bridge.submit("Deploy strategy?")
    agent_ids = {h.agent_id for h in handles}
    assert result.validation_result.winner_agent_id in agent_ids


def test_bridge_raw_responses_contains_all_agents():
    handles = [
        _strong_handle("a", "Answer A."),
        _strong_handle("b", "Answer B."),
        _strong_handle("c", "Answer C."),
    ]
    bridge = AgentValidationBridge(handles=handles, candidate_builder=_scoring_builder)
    result = bridge.submit("Question?")
    assert set(result.raw_responses.keys()) == {"a", "b", "c"}


def test_bridge_raw_responses_match_fn_output():
    bridge = AgentValidationBridge(
        handles=[_strong_handle("a", "exact text")],
        candidate_builder=_scoring_builder,
    )
    result = bridge.submit("Q?")
    assert result.raw_responses["a"] == "exact text"


# ── Bridge.submit — timeout / missing response ────────────────────────────────


def test_bridge_timeout_agent_produces_rejected_candidate():
    # A handle that never sets a response (returns None from drain)
    handle_ok = _strong_handle("agent-ok", "Good answer.")
    handle_timeout = CallableAgentHandle(agent_id="agent-timeout", fn=lambda _q: None)

    bridge = AgentValidationBridge(
        handles=[handle_ok, handle_timeout],
        candidate_builder=_scoring_builder,
        response_timeout=0.5,
    )
    result = bridge.submit("Question?")

    # Timed-out agent must appear with None in raw_responses
    assert result.raw_responses["agent-timeout"] is None
    # Its candidate must be rejected
    ranked = {vc.agent_id: vc for vc in result.validation_result.ranked_candidates}
    assert ranked["agent-timeout"].accepted is False


def test_bridge_all_timeout_gives_rejected_status():
    handles = [
        CallableAgentHandle(agent_id=f"agent-{i}", fn=lambda _q: None)
        for i in range(3)
    ]
    bridge = AgentValidationBridge(handles=handles, response_timeout=0.5)
    result = bridge.submit("Question?")
    assert result.validation_result.consensus_status == "rejected"
    assert result.validation_result.winner_agent_id is None


# ── Sequential mode ───────────────────────────────────────────────────────────


def test_bridge_sequential_mode_returns_correct_result():
    bridge = AgentValidationBridge(
        handles=[
            _strong_handle("agent-a", "Answer A."),
            _strong_handle("agent-b", "Answer B."),
        ],
        candidate_builder=_scoring_builder,
        parallel=False,
    )
    result = bridge.submit("Q?")
    assert result.validation_result.winner_agent_id in {"agent-a", "agent-b"}


# ── Integration with validator backends ──────────────────────────────────────


def test_bridge_with_full_validator_stack():
    from ls.cognition.lifetra_validation_adapter import LifetraValidationAdapter
    from ls.cognition.validation_governance import (
        InMemoryValidationHistoryStore,
        ValidationGovernanceEngine,
    )

    class _FakeTS:
        def __init__(self, s): self.epoch_seconds = s

    class _FakeST:
        def __init__(self, l, t, n): self.label, self.occurred_at, self.note = l, t, n

    class _FakeTraj:
        def __init__(self, st, m, s):
            self.stage, self.history = st, []
        def add_transition(self, t): self.history.append(t)
        def summary(self): return f"T(transitions={len(self.history)})"

    class _FakeLifetra:
        _backend_name = "lifetra_py"
        Timestamp = _FakeTS
        StateTransition = _FakeST
        TrajectoryState = _FakeTraj

    store = InMemoryValidationHistoryStore()
    engine = ValidationGovernanceEngine(history_store=store)
    adapter = LifetraValidationAdapter(lifetra_module=_FakeLifetra, clock=lambda: 0)
    validator = CollectiveAnswerValidator(
        trace_backend=adapter,
        governance_engine=engine,
    )

    bridge = AgentValidationBridge(
        handles=[
            _strong_handle("agent-a", "LRU cache with 300s TTL."),
            _strong_handle("agent-b", "TTL-based eviction, 5 minute window."),
        ],
        validator=validator,
        candidate_builder=_scoring_builder,
    )

    result = bridge.submit("Which cache?")

    assert result.validation_result.winner_agent_id is not None
    assert result.validation_result.trace_artifact is not None
    assert result.validation_result.governance_report is not None


# ── Single handle ─────────────────────────────────────────────────────────────


def test_bridge_single_handle_gives_weak_or_rejected():
    bridge = AgentValidationBridge(
        handles=[_strong_handle("solo", "Only answer.")],
        candidate_builder=_scoring_builder,
    )
    result = bridge.submit("Q?")
    status = result.validation_result.consensus_status
    assert status in {"weak", "convergent", "rejected"}
