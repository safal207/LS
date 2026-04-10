from __future__ import annotations

import pytest

from ls.cognition.collective_answer_validator import (
    CandidateAnswer,
    CollectiveAnswerValidator,
    ValidationInput,
)
from ls.cognition.lifetra_validation_adapter import LifetraValidationAdapter
from ls.cognition.ltp_trace_signer import (
    _build_signing_payload,
    _jcs_dumps,
    generate_key_pair,
    sign_trace_artifact,
    verify_trace_artifact,
)


# ── Fake Lifetra module (same pattern as adapter tests) ──────────────────────


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
        self.history: list[_FakeStateTransition] = []

    def add_transition(self, t: _FakeStateTransition) -> None:
        self.history.append(t)

    def summary(self) -> str:
        return f"TrajectoryState(transitions={len(self.history)})"


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
        task_prompt="Which deployment strategy minimises downtime?",
        candidates=[
            CandidateAnswer(
                agent_id="agent-a",
                answer_text="Blue-green deployment with DNS failover.",
                relevance=0.91,
                thread_relevance=0.86,
                hallucination_risk=0.06,
                supports=["agent-b"],
            ),
            CandidateAnswer(
                agent_id="agent-b",
                answer_text="Use blue-green with a load-balancer toggle.",
                relevance=0.84,
                thread_relevance=0.80,
                hallucination_risk=0.08,
            ),
            CandidateAnswer(
                agent_id="agent-c",
                answer_text="Push straight to production without a canary.",
                relevance=0.20,
                thread_relevance=0.18,
                hallucination_risk=0.78,
                contradicts=["agent-a"],
            ),
        ],
    )


def _artifact():
    payload = _base_payload()
    result = CollectiveAnswerValidator().validate(payload)
    artifact = _adapter().build_validation_trace(payload, result)
    assert artifact is not None
    return artifact


# ── JCS canonicalization ──────────────────────────────────────────────────────


def test_jcs_sorts_keys():
    obj = {"z": 1, "a": 2, "m": 3}
    canonical = _jcs_dumps(obj).decode()
    assert canonical == '{"a": 2, "m": 3, "z": 1}'


def test_jcs_nested_sorts_recursively():
    obj = {"b": {"y": 1, "a": 2}, "a": 0}
    canonical = _jcs_dumps(obj).decode()
    assert canonical.startswith('{"a":')
    assert '"a": 2' in canonical
    assert '"y": 1' in canonical


def test_jcs_list_preserves_order():
    obj = {"items": [3, 1, 2]}
    canonical = _jcs_dumps(obj).decode()
    assert '"items": [3, 1, 2]' in canonical


def test_jcs_handles_none_and_bool():
    obj = {"flag": None, "ok": True, "no": False}
    canonical = _jcs_dumps(obj).decode()
    assert '"flag": null' in canonical
    assert '"ok": true' in canonical
    assert '"no": false' in canonical


# ── Key generation ────────────────────────────────────────────────────────────


def test_generate_key_pair_returns_usable_keys():
    priv, pub = generate_key_pair()
    assert priv is not None
    assert pub is not None


# ── sign_trace_artifact ───────────────────────────────────────────────────────


def test_sign_returns_new_artifact_with_ltp_envelope():
    artifact = _artifact()
    priv, _ = generate_key_pair()

    signed = sign_trace_artifact(artifact, priv)

    assert signed is not artifact
    assert "ltp_envelope" in signed.metadata
    envelope = signed.metadata["ltp_envelope"]
    assert isinstance(envelope, dict)
    assert "sig" in envelope
    assert isinstance(envelope["sig"], str)
    assert len(envelope["sig"]) > 0


def test_sign_preserves_all_other_artifact_fields():
    artifact = _artifact()
    priv, _ = generate_key_pair()

    signed = sign_trace_artifact(artifact, priv)

    assert signed.trace_id == artifact.trace_id
    assert signed.winner_agent_id == artifact.winner_agent_id
    assert signed.global_risk_flags == artifact.global_risk_flags
    assert signed.node_count == artifact.node_count
    assert signed.edge_count == artifact.edge_count
    assert signed.backend == artifact.backend


def test_sign_envelope_covers_tamper_evident_fields():
    artifact = _artifact()
    priv, _ = generate_key_pair()

    signed = sign_trace_artifact(artifact, priv)
    payload = signed.metadata["ltp_envelope"]["payload"]

    assert payload["trace_id"] == artifact.trace_id
    assert payload["winner_agent_id"] == artifact.winner_agent_id
    assert payload["global_risk_flags"] == sorted(artifact.global_risk_flags)
    assert payload["node_count"] == artifact.node_count
    assert payload["edge_count"] == artifact.edge_count
    assert payload["backend"] == artifact.backend


def test_sign_is_deterministic_for_same_key():
    artifact = _artifact()
    priv, _ = generate_key_pair()

    signed_a = sign_trace_artifact(artifact, priv)
    signed_b = sign_trace_artifact(artifact, priv)

    # Ed25519 is deterministic — same key + same message = same signature
    assert signed_a.metadata["ltp_envelope"]["sig"] == signed_b.metadata["ltp_envelope"]["sig"]


def test_sign_produces_different_sigs_for_different_keys():
    artifact = _artifact()
    priv_a, _ = generate_key_pair()
    priv_b, _ = generate_key_pair()

    signed_a = sign_trace_artifact(artifact, priv_a)
    signed_b = sign_trace_artifact(artifact, priv_b)

    assert signed_a.metadata["ltp_envelope"]["sig"] != signed_b.metadata["ltp_envelope"]["sig"]


# ── verify_trace_artifact ─────────────────────────────────────────────────────


def test_verify_returns_true_for_valid_signature():
    artifact = _artifact()
    priv, pub = generate_key_pair()

    signed = sign_trace_artifact(artifact, priv)

    assert verify_trace_artifact(signed, pub) is True


def test_verify_returns_false_for_wrong_public_key():
    artifact = _artifact()
    priv, _ = generate_key_pair()
    _, other_pub = generate_key_pair()

    signed = sign_trace_artifact(artifact, priv)

    assert verify_trace_artifact(signed, other_pub) is False


def test_verify_returns_false_for_unsigned_artifact():
    artifact = _artifact()
    _, pub = generate_key_pair()

    assert verify_trace_artifact(artifact, pub) is False


def test_verify_returns_false_after_sig_tampered():
    artifact = _artifact()
    priv, pub = generate_key_pair()

    signed = sign_trace_artifact(artifact, priv)
    envelope = signed.metadata["ltp_envelope"]

    # Reverse the signature string — guaranteed to be a different byte sequence
    tampered_sig = envelope["sig"][::-1]
    tampered_envelope = {**envelope, "sig": tampered_sig}
    tampered_metadata = {**signed.metadata, "ltp_envelope": tampered_envelope}

    from dataclasses import replace
    tampered = replace(signed, metadata=tampered_metadata)

    assert verify_trace_artifact(tampered, pub) is False


def test_verify_returns_false_after_payload_tampered():
    artifact = _artifact()
    priv, pub = generate_key_pair()

    signed = sign_trace_artifact(artifact, priv)
    envelope = signed.metadata["ltp_envelope"]

    # Change winner in the envelope payload without re-signing
    tampered_payload = {**envelope["payload"], "winner_agent_id": "malicious-agent"}
    tampered_envelope = {**envelope, "payload": tampered_payload}
    tampered_metadata = {**signed.metadata, "ltp_envelope": tampered_envelope}

    from dataclasses import replace
    tampered = replace(signed, metadata=tampered_metadata)

    assert verify_trace_artifact(tampered, pub) is False


# ── Edge cases ────────────────────────────────────────────────────────────────


def test_sign_with_rejected_outcome_no_winner():
    payload = ValidationInput(
        task_prompt="Describe a safe approach.",
        candidates=[
            CandidateAnswer(
                agent_id="risky",
                answer_text="",
                relevance=0.10,
                thread_relevance=0.10,
                hallucination_risk=0.90,
            ),
        ],
    )
    result = CollectiveAnswerValidator().validate(payload)
    artifact = _adapter().build_validation_trace(payload, result)
    assert artifact is not None
    assert artifact.winner_agent_id is None

    priv, pub = generate_key_pair()
    signed = sign_trace_artifact(artifact, priv)

    assert verify_trace_artifact(signed, pub) is True
    assert signed.metadata["ltp_envelope"]["payload"]["winner_agent_id"] is None


def test_build_signing_payload_global_risk_flags_are_sorted():
    artifact = _artifact()
    lce = _build_signing_payload(artifact)
    flags = lce["payload"]["global_risk_flags"]
    assert flags == sorted(flags)


def test_sign_gracefully_returns_original_on_bad_key():
    artifact = _artifact()
    # Pass a non-key object — should not raise, should return original
    result = sign_trace_artifact(artifact, private_key="not-a-key")
    # Returns either the original or a copy; must not raise
    assert result.trace_id == artifact.trace_id


def test_verify_gracefully_returns_false_on_bad_envelope():
    artifact = _artifact()
    priv, pub = generate_key_pair()
    signed = sign_trace_artifact(artifact, priv)

    # Replace envelope with garbage
    from dataclasses import replace
    broken = replace(signed, metadata={**signed.metadata, "ltp_envelope": {"sig": "!!!"}})

    assert verify_trace_artifact(broken, pub) is False
