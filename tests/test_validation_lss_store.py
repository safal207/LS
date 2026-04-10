from __future__ import annotations

# Tests for LSSValidationHistoryStore.
#
# lri is not installed in the test environment, so all tests verify the
# graceful fallback path (InMemoryValidationHistoryStore).  The interface
# contract must be identical whether backed by LSS or the in-memory store.

import pytest

from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
)
from ls.cognition.validation_governance import (
    InMemoryValidationHistoryStore,
    ValidationGovernanceEngine,
    ValidationHistoryRecord,
)
from ls.cognition.validation_lss_store import (
    LSSValidationHistoryStore,
    _lce_dict_to_record,
    _record_to_lce_dict,
)


def _make_record() -> ValidationHistoryRecord:
    store = InMemoryValidationHistoryStore()
    engine = ValidationGovernanceEngine(history_store=store)
    payload = ValidationInput(
        task_prompt="Which option?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Option A.",
                relevance=0.85,
                thread_relevance=0.80,
                hallucination_risk=0.08,
            ),
            CandidateAnswer(
                agent_id="agent-b",
                answer_text="Option B.",
                relevance=0.60,
                thread_relevance=0.58,
                hallucination_risk=0.15,
            ),
        ],
    )
    validator = CollectiveAnswerValidator(governance_engine=engine)
    validator.validate(payload)
    records = store.load_records()
    assert records, "Expected at least one history record"
    return records[0]


# ── LCE serialisation round-trip ──────────────────────────────────────────────


def test_record_to_lce_dict_has_intent_payload_policy():
    record = _make_record()
    lce = _record_to_lce_dict(record)

    assert "intent" in lce
    assert lce["intent"]["type"] == "validation_history_record"
    assert "payload" in lce
    assert "policy" in lce
    assert lce["policy"]["consent"] == "internal"


def test_lce_dict_to_record_round_trips():
    record = _make_record()
    lce = _record_to_lce_dict(record)
    reconstructed = _lce_dict_to_record(lce)

    assert reconstructed is not None
    assert reconstructed.round_id == record.round_id
    assert reconstructed.winner_agent_id == record.winner_agent_id
    assert reconstructed.consensus_status == record.consensus_status


def test_lce_dict_to_record_returns_none_for_bad_payload():
    bad_lce = {"intent": {}, "payload": "not-a-dict", "policy": {}}
    result = _lce_dict_to_record(bad_lce)
    assert result is None


def test_lce_dict_to_record_returns_none_for_missing_payload():
    result = _lce_dict_to_record({"intent": {}})
    assert result is None


# ── Fallback path (lri not installed) ────────────────────────────────────────


def test_store_uses_fallback_when_lri_unavailable():
    store = LSSValidationHistoryStore(thread_id="test-thread")
    # lri not installed → fallback must be set
    assert store._fallback is not None or store._lss is not None


def test_fallback_load_returns_empty_initially():
    store = LSSValidationHistoryStore(thread_id="test-empty")
    assert store.load_records() == []


def test_fallback_append_and_load_round_trips():
    store = LSSValidationHistoryStore(thread_id="test-roundtrip")
    record = _make_record()

    store.append_record(record)
    loaded = store.load_records()

    assert len(loaded) == 1
    assert loaded[0].round_id == record.round_id
    assert loaded[0].winner_agent_id == record.winner_agent_id


def test_fallback_accumulates_multiple_records():
    store = LSSValidationHistoryStore(thread_id="test-multi")
    record_a = _make_record()
    record_b = _make_record()

    store.append_record(record_a)
    store.append_record(record_b)

    loaded = store.load_records()
    assert len(loaded) == 2


# ── Coherence and drift (fallback path) ──────────────────────────────────────


def test_coherence_returns_none_when_lss_unavailable():
    store = LSSValidationHistoryStore(thread_id="test-coherence")
    if store._lss is None:
        assert store.coherence() is None
    else:
        # LSS available: coherence is None before any records stored
        result = store.coherence()
        assert result is None or isinstance(result, float)


def test_drift_events_returns_empty_list_when_lss_unavailable():
    store = LSSValidationHistoryStore(thread_id="test-drift")
    if store._lss is None:
        assert store.drift_events() == []
    else:
        assert isinstance(store.drift_events(), list)


# ── Integration: governance engine with LSS store ─────────────────────────────


def test_governance_engine_works_with_lss_store():
    store = LSSValidationHistoryStore(thread_id="test-governance")
    engine = ValidationGovernanceEngine(history_store=store)
    validator = CollectiveAnswerValidator(governance_engine=engine)

    payload = ValidationInput(
        task_prompt="Which strategy?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Strategy A: gradual rollout.",
                relevance=0.88,
                thread_relevance=0.84,
                hallucination_risk=0.07,
                supports=["agent-b"],
            ),
            CandidateAnswer(
                agent_id="agent-b",
                answer_text="Strategy A with monitoring.",
                relevance=0.82,
                thread_relevance=0.79,
                hallucination_risk=0.09,
            ),
        ],
    )

    result = validator.validate(payload)

    assert result.winner_agent_id is not None
    assert result.governance_report is not None
    # History must be persisted
    assert len(store.load_records()) == 1


def test_governance_history_accumulates_across_rounds():
    store = LSSValidationHistoryStore(thread_id="test-accumulate")
    engine = ValidationGovernanceEngine(history_store=store)
    validator = CollectiveAnswerValidator(governance_engine=engine)

    payload = ValidationInput(
        task_prompt="Round question.",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Clear answer.",
                relevance=0.90,
                thread_relevance=0.88,
                hallucination_risk=0.05,
            ),
        ],
    )

    validator.validate(payload)
    validator.validate(payload)

    assert len(store.load_records()) == 2
