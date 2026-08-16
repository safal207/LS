from dataclasses import replace

from verified_transition_loop import (
    EvidenceBundle,
    EvidenceLedger,
    LedgerRecord,
    ObservedOutcome,
    OutcomeVerdict,
    TransitionIntent,
    TransitionProposal,
    TransitionVerdict,
    evaluate_transition,
    verify_outcome,
)

NOW = 1_000


def fixtures():
    intent = TransitionIntent("intent-1", "agent", "deploy", "release exact commit")
    proposal = TransitionProposal(
        "transition-1",
        "intent-1",
        "staging",
        "deploy",
        "production-healthy",
        ("healthcheck_ok", "artifact_matches"),
    )
    evidence = EvidenceBundle(True, True, True, True, NOW + 500, ("ci:42", "approval:7"))
    return intent, proposal, evidence


def test_authorizes_complete_bound_evidence():
    intent, proposal, evidence = fixtures()
    receipt = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=evidence,
        verifier_id="verifier",
        executor_id="executor",
        now_ms=NOW,
    )
    assert receipt.verdict is TransitionVerdict.AUTHORIZE
    assert receipt.reason_codes == ()


def test_missing_evidence_holds():
    intent, proposal, evidence = fixtures()
    receipt = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=replace(evidence, tests_passed=None),
        verifier_id="verifier",
        executor_id="executor",
        now_ms=NOW,
    )
    assert receipt.verdict is TransitionVerdict.HOLD
    assert "EVIDENCE_MISSING:tests_passed" in receipt.reason_codes


def test_failed_evidence_blocks():
    intent, proposal, evidence = fixtures()
    receipt = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=replace(evidence, tests_passed=False),
        verifier_id="verifier",
        executor_id="executor",
        now_ms=NOW,
    )
    assert receipt.verdict is TransitionVerdict.BLOCK


def test_expired_approval_blocks():
    intent, proposal, evidence = fixtures()
    receipt = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=replace(evidence, approval_valid_until_ms=NOW - 1),
        verifier_id="verifier",
        executor_id="executor",
        now_ms=NOW,
    )
    assert receipt.verdict is TransitionVerdict.BLOCK
    assert "APPROVAL_EXPIRED" in receipt.reason_codes


def test_verifier_cannot_be_executor():
    intent, proposal, evidence = fixtures()
    receipt = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=evidence,
        verifier_id="same",
        executor_id="same",
        now_ms=NOW,
    )
    assert receipt.verdict is TransitionVerdict.BLOCK
    assert "VERIFIER_EXECUTOR_COLLISION" in receipt.reason_codes


def test_authorization_receipt_is_deterministic():
    intent, proposal, evidence = fixtures()
    a = evaluate_transition(intent=intent, proposal=proposal, evidence=evidence, verifier_id="v", executor_id="e", now_ms=NOW)
    b = evaluate_transition(intent=intent, proposal=proposal, evidence=evidence, verifier_id="v", executor_id="e", now_ms=NOW)
    assert a.decision_id == b.decision_id
    assert a.evidence_digest == b.evidence_digest


def test_successful_outcome_commits():
    _, proposal, _ = fixtures()
    outcome = ObservedOutcome(
        "transition-1",
        "production-healthy",
        (("healthcheck_ok", True), ("artifact_matches", True)),
        rollback_available=True,
    )
    receipt = verify_outcome(proposal=proposal, outcome=outcome, verifier_id="verifier", executor_id="executor")
    assert receipt.verdict is OutcomeVerdict.COMMIT


def test_failed_invariant_requests_rollback():
    _, proposal, _ = fixtures()
    outcome = ObservedOutcome(
        "transition-1",
        "production-degraded",
        (("healthcheck_ok", False), ("artifact_matches", True)),
        rollback_available=True,
    )
    receipt = verify_outcome(proposal=proposal, outcome=outcome, verifier_id="verifier", executor_id="executor")
    assert receipt.verdict is OutcomeVerdict.ROLLBACK
    assert "INVARIANT_FAILED:healthcheck_ok" in receipt.reason_codes


def test_missing_invariant_escalates():
    _, proposal, _ = fixtures()
    outcome = ObservedOutcome(
        "transition-1",
        "production-healthy",
        (("healthcheck_ok", True),),
        rollback_available=True,
    )
    receipt = verify_outcome(proposal=proposal, outcome=outcome, verifier_id="verifier", executor_id="executor")
    assert receipt.verdict is OutcomeVerdict.ESCALATE
    assert "INVARIANT_MISSING:artifact_matches" in receipt.reason_codes


def test_ledger_detects_tampering():
    ledger = EvidenceLedger()
    ledger.append("intent", {"id": "i1"})
    ledger.append("decision", {"verdict": "AUTHORIZE"})
    assert EvidenceLedger.verify(ledger.records)

    first, second = ledger.records
    tampered = LedgerRecord(second.index, second.record_type, {"verdict": "BLOCK"}, second.previous_hash, second.record_hash)
    assert not EvidenceLedger.verify((first, tampered))
