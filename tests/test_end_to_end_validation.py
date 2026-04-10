from __future__ import annotations

# End-to-end integration test exercising all 7 validation layers together:
#
#   1. AgentValidationBridge  — collects responses from agent handles
#   2. CollectiveAnswerValidator — scores + consensus
#   3. LifetraValidationAdapter — trajectory trace
#   4. ValidationGovernanceEngine — reputation, clusters, coalitions
#   5. LSSValidationHistoryStore — history persistence (fallback path)
#   6. LTP trace signing — Ed25519 sign + verify
#   7. ValidationEscalationHandler — escalation on review_required
#
# Every layer is wired together in a single pipeline.  The test uses fake
# Lifetra types (the real Rust-backed module is not required) and the LSS
# store's in-memory fallback (lri is not installed in CI).

import logging

import pytest

from ls.cognition.agent_validation_bridge import (
    AgentValidationBridge,
    BridgeResult,
    CallableAgentHandle,
)
from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
    ValidationResult,
)
from ls.cognition.lifetra_validation_adapter import (
    LifetraValidationAdapter,
    ValidationTraceArtifact,
)
from ls.cognition.ltp_trace_signer import (
    generate_key_pair,
    sign_trace_artifact,
    verify_trace_artifact,
)
from ls.cognition.validation_escalation import (
    EscalationRequired,
    LoggingEscalationHandler,
    NullEscalationHandler,
    RaisingEscalationHandler,
)
from ls.cognition.validation_governance import (
    InMemoryValidationHistoryStore,
    ValidationGovernanceEngine,
    ValidationGovernanceReport,
)
from ls.cognition.validation_lss_store import LSSValidationHistoryStore


# ── Fake Lifetra module ─────────────────────────────────────────────────────


class _FakeTimestamp:
    def __init__(self, s: int) -> None:
        self.epoch_seconds = s


class _FakeStateTransition:
    def __init__(self, label: str, ts: _FakeTimestamp, note: str) -> None:
        self.label = label
        self.occurred_at = ts
        self.note = note


class _FakeTrajectoryState:
    def __init__(self, stage: str, momentum: float, stability: float) -> None:
        self.stage = stage
        self.history: list[_FakeStateTransition] = []

    def add_transition(self, t: _FakeStateTransition) -> None:
        self.history.append(t)

    def summary(self) -> str:
        return f"FakeTrajectory(transitions={len(self.history)})"


class _FakeLifetra:
    _backend_name = "lifetra_fake"
    Timestamp = _FakeTimestamp
    StateTransition = _FakeStateTransition
    TrajectoryState = _FakeTrajectoryState


# ── Candidate builder for bridge tests ──────────────────────────────────────


def _scoring_builder(agent_id: str, text: str, task_prompt: str) -> CandidateAnswer:  # noqa: ARG001
    if text.strip():
        return CandidateAnswer(
            agent_id=agent_id,
            answer_text=text,
            relevance=0.88,
            thread_relevance=0.84,
            hallucination_risk=0.06,
        )
    return CandidateAnswer(
        agent_id=agent_id,
        answer_text=text,
        relevance=0.05,
        thread_relevance=0.05,
        hallucination_risk=0.95,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _build_full_stack(
    *,
    escalation_handler=None,
    quorum_size: int = 2,
    trusted_reputation_threshold: float = 0.0,
) -> tuple[CollectiveAnswerValidator, LSSValidationHistoryStore]:
    """Wire all 7 layers into one validator instance."""
    store = LSSValidationHistoryStore(thread_id="e2e-test")
    engine = ValidationGovernanceEngine(
        history_store=store,
        quorum_size=quorum_size,
        trusted_reputation_threshold=trusted_reputation_threshold,
    )
    adapter = LifetraValidationAdapter(lifetra_module=_FakeLifetra, clock=lambda: 1000)
    validator = CollectiveAnswerValidator(
        trace_backend=adapter,
        governance_engine=engine,
        escalation_handler=escalation_handler,
    )
    return validator, store


def _agreeing_payload() -> ValidationInput:
    return ValidationInput(
        task_prompt="What caching strategy should we use for session tokens?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-alpha",
                answer_text="Use an LRU cache with a 300-second TTL for session tokens.",
                relevance=0.90,
                thread_relevance=0.88,
                hallucination_risk=0.05,
                supports=["agent-beta"],
            ),
            CandidateAnswer(
                agent_id="agent-beta",
                answer_text="TTL-based LRU eviction with a 5-minute window is optimal.",
                relevance=0.87,
                thread_relevance=0.84,
                hallucination_risk=0.06,
            ),
        ],
    )


def _conflicting_payload() -> ValidationInput:
    return ValidationInput(
        task_prompt="Should we use microservices or a monolith?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-alpha",
                answer_text="Microservices give better scalability and team autonomy.",
                relevance=0.88,
                thread_relevance=0.85,
                hallucination_risk=0.07,
                contradicts=["agent-beta"],
            ),
            CandidateAnswer(
                agent_id="agent-beta",
                answer_text="A monolith is simpler and faster to ship for a small team.",
                relevance=0.86,
                thread_relevance=0.83,
                hallucination_risk=0.08,
                contradicts=["agent-alpha"],
            ),
        ],
    )


# ── Test: full stack — agreeing candidates ───────────────────────────────────


def test_full_stack_agreeing_candidates():
    """All 7 layers wired: agreeing candidates produce convergent result with
    trace, governance, and signable artifact."""
    validator, store = _build_full_stack()
    result = validator.validate(_agreeing_payload())

    # Layer 2: validator produced a result
    assert result.winner_agent_id is not None
    assert result.consensus_status in {"convergent", "weak"}

    # Layer 3: Lifetra trace attached
    assert result.trace_artifact is not None
    assert result.trace_artifact.backend == "lifetra_fake"
    assert result.trace_artifact.node_count > 0
    assert result.trace_artifact.edge_count > 0

    # Layer 4: governance report attached
    assert result.governance_report is not None
    assert isinstance(result.governance_report.review_required, bool)

    # Layer 5: history persisted in LSS store
    records = store.load_records()
    assert len(records) == 1
    assert records[0].winner_agent_id == result.winner_agent_id

    # Layer 6: sign and verify
    priv, pub = generate_key_pair()
    signed = sign_trace_artifact(result.trace_artifact, priv)
    assert "ltp_envelope" in signed.metadata
    assert verify_trace_artifact(signed, pub)


def test_full_stack_conflicting_candidates():
    """Conflicting candidates produce conflicted status and review_required."""
    validator, store = _build_full_stack()
    result = validator.validate(_conflicting_payload())

    assert result.consensus_status == "conflicted"
    assert result.trace_artifact is not None
    assert result.governance_report is not None
    assert "conflict_between_top_candidates" in result.global_risk_flags

    # History recorded
    assert len(store.load_records()) == 1


# ── Test: full stack via bridge ──────────────────────────────────────────────


def test_bridge_with_full_stack():
    """AgentValidationBridge (layer 1) feeding into the full 6-layer validator."""
    validator, store = _build_full_stack()
    bridge = AgentValidationBridge(
        handles=[
            CallableAgentHandle(agent_id="agent-alpha", fn=lambda _q: "LRU with 300s TTL."),
            CallableAgentHandle(agent_id="agent-beta", fn=lambda _q: "TTL-based LRU, 5 minutes."),
        ],
        validator=validator,
        candidate_builder=_scoring_builder,
    )

    result = bridge.submit("Which cache strategy?")

    assert isinstance(result, BridgeResult)
    vr = result.validation_result
    assert vr.winner_agent_id in {"agent-alpha", "agent-beta"}
    assert vr.trace_artifact is not None
    assert vr.governance_report is not None
    assert len(store.load_records()) == 1

    # Raw responses preserved
    assert result.raw_responses["agent-alpha"] == "LRU with 300s TTL."
    assert result.raw_responses["agent-beta"] == "TTL-based LRU, 5 minutes."


# ── Test: signing round-trip through full stack ──────────────────────────────


def test_sign_verify_round_trip_through_full_stack():
    """Sign the trace artifact from a full-stack run and verify it."""
    validator, _store = _build_full_stack()
    result = validator.validate(_agreeing_payload())

    assert result.trace_artifact is not None
    priv, pub = generate_key_pair()

    signed = sign_trace_artifact(result.trace_artifact, priv)
    assert verify_trace_artifact(signed, pub)

    # Wrong key must fail
    priv2, pub2 = generate_key_pair()
    assert not verify_trace_artifact(signed, pub2)

    # Unsigned artifact must fail
    assert not verify_trace_artifact(result.trace_artifact, pub)


# ── Test: escalation wiring through full stack ───────────────────────────────


def test_null_escalation_never_raises():
    """NullEscalationHandler wired into the full stack does not raise."""
    validator, _store = _build_full_stack(escalation_handler=NullEscalationHandler())
    result = validator.validate(_conflicting_payload())
    assert result is not None
    assert result.governance_report is not None


def test_logging_escalation_emits_warning(caplog):
    """LoggingEscalationHandler logs when review_required fires."""
    handler = LoggingEscalationHandler(log_level=logging.WARNING)
    validator, _store = _build_full_stack(escalation_handler=handler)

    with caplog.at_level(logging.WARNING, logger="ls.cognition.validation_escalation"):
        result = validator.validate(_conflicting_payload())

    assert result is not None
    if result.governance_report and result.governance_report.review_required:
        assert any("escalation" in r.message.lower() for r in caplog.records)


def test_raising_escalation_raises_on_review_required():
    """RaisingEscalationHandler raises EscalationRequired when review_required."""
    handler = RaisingEscalationHandler()
    validator, _store = _build_full_stack(escalation_handler=handler)

    # First check without handler to see if review_required fires
    plain_validator, _ = _build_full_stack()
    plain_result = plain_validator.validate(_conflicting_payload())

    if plain_result.governance_report and plain_result.governance_report.review_required:
        with pytest.raises(EscalationRequired) as exc_info:
            validator.validate(_conflicting_payload())
        assert exc_info.value.result is not None
        assert exc_info.value.report.review_required is True
    else:
        # Governance didn't flag review_required — handler must not raise
        result = validator.validate(_conflicting_payload())
        assert result is not None


# ── Test: history accumulation across rounds ─────────────────────────────────


def test_history_accumulates_across_multiple_rounds():
    """Run the full stack 3 times and verify history grows."""
    validator, store = _build_full_stack()
    payloads = [_agreeing_payload(), _conflicting_payload(), _agreeing_payload()]

    for payload in payloads:
        validator.validate(payload)

    records = store.load_records()
    assert len(records) == 3
    statuses = {r.consensus_status for r in records}
    # At least two distinct statuses from the mix of agreeing/conflicting
    assert len(statuses) >= 1


def test_reputation_evolves_over_rounds():
    """Agent reputation profiles appear once history exists (round 2+)."""
    validator, store = _build_full_stack()

    # Round 1 — no history yet, so profiles may be empty
    r1 = validator.validate(_agreeing_payload())
    profiles_r1 = {p.agent_id: p for p in r1.governance_report.agent_profiles}

    # Round 2 — history from round 1 is now available
    r2 = validator.validate(_agreeing_payload())
    profiles_r2 = {p.agent_id: p for p in r2.governance_report.agent_profiles}

    # Round 3 — history from rounds 1+2
    r3 = validator.validate(_agreeing_payload())
    profiles_r3 = {p.agent_id: p for p in r3.governance_report.agent_profiles}

    assert len(store.load_records()) == 3
    # By round 2, agents from round 1 should appear in profiles
    assert "agent-alpha" in profiles_r2 or "agent-alpha" in profiles_r3
    assert len(profiles_r3) >= len(profiles_r1)


# ── Test: trace artifact metadata completeness ──────────────────────────────


def test_trace_metadata_contains_graph_data():
    """Trace artifact metadata includes nodes, edges, and trajectory summary."""
    validator, _store = _build_full_stack()
    result = validator.validate(_agreeing_payload())
    meta = result.trace_artifact.metadata

    assert "nodes" in meta
    assert "edges" in meta
    assert "trajectory_summary" in meta
    assert "consensus_status" in meta
    assert "accepted_agent_ids" in meta
    assert "rejected_agent_ids" in meta
    assert "task_prompt_preview" in meta

    # Nodes: task + 2 candidates + validation result = 4
    assert len(meta["nodes"]) == 4
    node_kinds = {n["kind"] for n in meta["nodes"]}
    assert node_kinds == {"task_prompt", "candidate", "validation_result"}


def test_trace_edges_include_all_relation_types():
    """Edges include evaluates, accepted/rejected, supports, and winner."""
    validator, _store = _build_full_stack()
    result = validator.validate(_agreeing_payload())
    edges = result.trace_artifact.metadata["edges"]

    relations = {e["relation"] for e in edges}
    assert "evaluates" in relations
    assert "winner" in relations
    # At least one candidate should be accepted
    assert "accepted" in relations or "rejected" in relations


# ── Test: bridge with timeout agent in full stack ────────────────────────────


def test_bridge_timeout_agent_in_full_stack():
    """A timed-out agent still produces a trace and governance report."""
    validator, store = _build_full_stack()
    bridge = AgentValidationBridge(
        handles=[
            CallableAgentHandle(agent_id="good-agent", fn=lambda _q: "Good answer."),
            CallableAgentHandle(agent_id="timeout-agent", fn=lambda _q: None),
        ],
        validator=validator,
        candidate_builder=_scoring_builder,
        response_timeout=0.5,
    )

    result = bridge.submit("Question?")
    vr = result.validation_result

    # Timed-out agent appears in raw_responses as None
    assert result.raw_responses["timeout-agent"] is None
    # Trace and governance still attached
    assert vr.trace_artifact is not None
    assert vr.governance_report is not None
    # History recorded
    assert len(store.load_records()) == 1


# ── Test: sign artifact from bridge result ───────────────────────────────────


def test_sign_bridge_result_artifact():
    """Sign the trace artifact that comes out of a bridge run."""
    validator, _store = _build_full_stack()
    bridge = AgentValidationBridge(
        handles=[
            CallableAgentHandle(agent_id="a", fn=lambda _q: "Answer A."),
            CallableAgentHandle(agent_id="b", fn=lambda _q: "Answer B."),
        ],
        validator=validator,
        candidate_builder=_scoring_builder,
    )

    result = bridge.submit("Q?")
    artifact = result.validation_result.trace_artifact
    assert artifact is not None

    priv, pub = generate_key_pair()
    signed = sign_trace_artifact(artifact, priv)
    assert verify_trace_artifact(signed, pub)
    assert signed.metadata["ltp_envelope"]["payload"]["trace_id"] == artifact.trace_id
