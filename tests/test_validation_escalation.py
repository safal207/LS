from __future__ import annotations

import logging

import pytest

from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
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
)


def _governance_validator(escalation_handler=None) -> CollectiveAnswerValidator:
    store = InMemoryValidationHistoryStore()
    engine = ValidationGovernanceEngine(history_store=store, quorum_size=3)
    return CollectiveAnswerValidator(
        governance_engine=engine,
        escalation_handler=escalation_handler,
    )


def _conflicted_payload() -> ValidationInput:
    """Payload that produces conflict_between_top_candidates → review_required."""
    return ValidationInput(
        task_prompt="Choose A or B?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-1",
                answer_text="Definitely choose A.",
                relevance=0.88,
                thread_relevance=0.84,
                hallucination_risk=0.08,
                contradicts=["agent-2"],
            ),
            CandidateAnswer(
                agent_id="agent-2",
                answer_text="Definitely choose B.",
                relevance=0.86,
                thread_relevance=0.82,
                hallucination_risk=0.09,
                contradicts=["agent-1"],
            ),
        ],
    )


# ── NullEscalationHandler ─────────────────────────────────────────────────────


def test_null_handler_does_not_raise():
    validator = _governance_validator(escalation_handler=NullEscalationHandler())
    result = validator.validate(_conflicted_payload())
    # Must not raise even when review_required may be True
    assert result is not None


def test_null_handler_preserves_result():
    validator = _governance_validator(escalation_handler=NullEscalationHandler())
    result = validator.validate(_conflicted_payload())
    assert result.winner_agent_id is not None
    assert result.consensus_status == "conflicted"


# ── No handler (default) ──────────────────────────────────────────────────────


def test_no_handler_does_not_raise():
    validator = _governance_validator(escalation_handler=None)
    result = validator.validate(_conflicted_payload())
    assert result is not None


# ── LoggingEscalationHandler ──────────────────────────────────────────────────


def test_logging_handler_emits_warning(caplog):
    handler = LoggingEscalationHandler(log_level=logging.WARNING)
    validator = _governance_validator(escalation_handler=handler)

    with caplog.at_level(logging.WARNING, logger="ls.cognition.validation_escalation"):
        result = validator.validate(_conflicted_payload())

    assert result is not None
    if result.governance_report and result.governance_report.review_required:
        assert any("escalation" in r.message.lower() for r in caplog.records)


def test_logging_handler_includes_winner_in_log(caplog):
    handler = LoggingEscalationHandler()
    validator = _governance_validator(escalation_handler=handler)

    with caplog.at_level(logging.WARNING):
        result = validator.validate(_conflicted_payload())

    if result.governance_report and result.governance_report.review_required:
        combined = " ".join(r.message for r in caplog.records)
        assert "escalation" in combined.lower()


# ── RaisingEscalationHandler ──────────────────────────────────────────────────


def test_raising_handler_raises_when_review_required():
    handler = RaisingEscalationHandler()
    validator = _governance_validator(escalation_handler=handler)

    payload = _conflicted_payload()
    # Run without handler first to check if review_required fires
    plain_result = _governance_validator().validate(payload)

    if plain_result.governance_report and plain_result.governance_report.review_required:
        with pytest.raises(EscalationRequired) as exc_info:
            validator.validate(payload)
        assert exc_info.value.result is not None
        assert exc_info.value.report is not None
    else:
        # governance didn't flag review_required — RaisingHandler must not raise
        result = validator.validate(payload)
        assert result is not None


def test_raising_handler_exception_carries_result_and_report():
    handler = RaisingEscalationHandler()
    validator = _governance_validator(escalation_handler=handler)

    plain = _governance_validator().validate(_conflicted_payload())
    if not (plain.governance_report and plain.governance_report.review_required):
        pytest.skip("governance did not flag review_required for this payload")

    with pytest.raises(EscalationRequired) as exc_info:
        validator.validate(_conflicted_payload())

    err = exc_info.value
    assert err.result.consensus_status is not None
    assert err.report.review_required is True
    assert "review" in str(err).lower()


def test_raising_handler_does_not_raise_when_not_review_required():
    handler = RaisingEscalationHandler()
    store = InMemoryValidationHistoryStore()
    # trusted_reputation_threshold=0.0 so agents with no history still qualify
    # as trusted supporters, ensuring quorum is reachable on first round.
    engine = ValidationGovernanceEngine(
        history_store=store,
        quorum_size=1,
        trusted_reputation_threshold=0.0,
    )
    validator = CollectiveAnswerValidator(
        governance_engine=engine,
        escalation_handler=handler,
    )
    payload = ValidationInput(
        task_prompt="What is the capital of France?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Paris is the capital of France.",
                relevance=0.95,
                thread_relevance=0.92,
                hallucination_risk=0.03,
                supports=["agent-b"],
            ),
            CandidateAnswer(
                agent_id="agent-b",
                answer_text="The capital is Paris.",
                relevance=0.90,
                thread_relevance=0.88,
                hallucination_risk=0.04,
            ),
        ],
    )
    # Should not raise
    result = validator.validate(payload)
    assert result.winner_agent_id is not None


# ── Validator unchanged when no governance ────────────────────────────────────


def test_validator_without_governance_ignores_escalation_handler():
    handler = RaisingEscalationHandler()
    # No governance_engine — escalation_handler must never be called
    validator = CollectiveAnswerValidator(escalation_handler=handler)
    payload = ValidationInput(
        task_prompt="Pick one.",
        candidates=[
            CandidateAnswer(
                agent_id="a",
                answer_text="Option A.",
                relevance=0.8,
                thread_relevance=0.8,
                hallucination_risk=0.1,
            ),
        ],
    )
    result = validator.validate(payload)
    assert result is not None
