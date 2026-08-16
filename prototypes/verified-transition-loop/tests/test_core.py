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
    UseTimeVerdict,
    UseTokenRegistry,
    evaluate_transition,
    revalidate_authorization_for_use,
    verify_authorization_receipt,
    verify_authorized_outcome,
    verify_executed_outcome,
    verify_outcome,
    verify_use_time_receipt,
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
    evidence = EvidenceBundle(
        True,
        True,
        True,
        True,
        NOW + 500,
        ("ci:42", "approval:7"),
        source_ref="git:abc",
        policy_ref="policy:deploy-v1",
        approval_ref="approval:7",
    )
    return intent, proposal, evidence


def authorization():
    intent, proposal, evidence = fixtures()
    return proposal, evidence, evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=evidence,
        verifier_id="verifier",
        executor_id="executor",
        now_ms=NOW,
    )


def use_receipt():
    proposal, evidence, auth = authorization()
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=evidence,
        executor_id="executor",
        now_ms=NOW + 1,
        execution_nonce="occurrence-1",
    )
    return proposal, evidence, auth, use


def healthy_outcome():
    return ObservedOutcome(
        "transition-1",
        "production-healthy",
        (("healthcheck_ok", True), ("artifact_matches", True)),
        rollback_available=True,
    )


def test_authorizes_complete_bound_evidence():
    _, _, receipt = authorization()
    assert receipt.verdict is TransitionVerdict.AUTHORIZE
    assert receipt.reason_codes == ()
    assert verify_authorization_receipt(receipt)


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


def test_missing_use_time_binding_holds():
    intent, proposal, evidence = fixtures()
    receipt = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=replace(evidence, policy_ref=None),
        verifier_id="verifier",
        executor_id="executor",
        now_ms=NOW,
    )
    assert receipt.verdict is TransitionVerdict.HOLD
    assert "POLICY_REF_MISSING" in receipt.reason_codes


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
    assert a.proposal_digest == b.proposal_digest


def test_tampered_authorization_receipt_is_rejected():
    proposal, _, receipt = authorization()
    tampered = replace(receipt, evidence_digest="0" * 64)
    assert not verify_authorization_receipt(tampered)

    result = verify_authorized_outcome(
        proposal=proposal,
        authorization=tampered,
        outcome=healthy_outcome(),
        verifier_id="outcome-verifier",
    )
    assert result.verdict is OutcomeVerdict.ESCALATE
    assert result.reason_codes == ("AUTHORIZATION_RECEIPT_INVALID",)


def test_use_time_revalidation_yields_execute_permit():
    _, _, _, use = use_receipt()
    assert use.verdict is UseTimeVerdict.EXECUTE
    assert use.reason_codes == ()
    assert verify_use_time_receipt(use)
    assert use.context_digest
    assert use.execution_nonce == "occurrence-1"


def test_source_change_blocks_at_use_time():
    proposal, evidence, auth = authorization()
    current = replace(evidence, source_ref="git:def")
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=current,
        executor_id="executor",
        now_ms=NOW + 1,
        execution_nonce="occurrence-1",
    )
    assert use.verdict is UseTimeVerdict.BLOCK
    assert "SOURCE_REF_CHANGED" in use.reason_codes
    assert "EVIDENCE_CONTEXT_CHANGED" in use.reason_codes


def test_policy_change_blocks_at_use_time():
    proposal, evidence, auth = authorization()
    current = replace(evidence, policy_ref="policy:deploy-v2")
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=current,
        executor_id="executor",
        now_ms=NOW + 1,
        execution_nonce="occurrence-1",
    )
    assert use.verdict is UseTimeVerdict.BLOCK
    assert "POLICY_REF_CHANGED" in use.reason_codes


def test_approval_change_blocks_at_use_time():
    proposal, evidence, auth = authorization()
    current = replace(evidence, approval_ref="approval:8")
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=current,
        executor_id="executor",
        now_ms=NOW + 1,
        execution_nonce="occurrence-1",
    )
    assert use.verdict is UseTimeVerdict.BLOCK
    assert "APPROVAL_REF_CHANGED" in use.reason_codes


def test_approval_expiry_blocks_at_use_time():
    proposal, evidence, auth = authorization()
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=evidence,
        executor_id="executor",
        now_ms=NOW + 501,
        execution_nonce="occurrence-1",
    )
    assert use.verdict is UseTimeVerdict.BLOCK
    assert "APPROVAL_EXPIRED_AT_USE" in use.reason_codes


def test_evidence_change_blocks_at_use_time():
    proposal, evidence, auth = authorization()
    current = replace(evidence, evidence_refs=evidence.evidence_refs + ("scan:fresh",))
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=current,
        executor_id="executor",
        now_ms=NOW + 1,
        execution_nonce="occurrence-1",
    )
    assert use.verdict is UseTimeVerdict.BLOCK
    assert "EVIDENCE_CONTEXT_CHANGED" in use.reason_codes


def test_executor_change_blocks_at_use_time():
    proposal, evidence, auth = authorization()
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=evidence,
        executor_id="other-executor",
        now_ms=NOW + 1,
        execution_nonce="occurrence-1",
    )
    assert use.verdict is UseTimeVerdict.BLOCK
    assert "EXECUTOR_BINDING_MISMATCH" in use.reason_codes


def test_execution_nonce_is_required():
    proposal, evidence, auth = authorization()
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=evidence,
        executor_id="executor",
        now_ms=NOW + 1,
        execution_nonce="",
    )
    assert use.verdict is UseTimeVerdict.BLOCK
    assert "EXECUTION_NONCE_INVALID" in use.reason_codes


def test_use_token_registry_is_exactly_once():
    _, _, _, use = use_receipt()
    registry = UseTokenRegistry()
    assert registry.consume(use)
    assert registry.consumed(use.use_id)
    assert not registry.consume(use)


def test_tampered_use_time_receipt_is_rejected():
    proposal, _, auth, use = use_receipt()
    tampered = replace(use, context_digest="0" * 64)
    assert not verify_use_time_receipt(tampered)
    result = verify_executed_outcome(
        proposal=proposal,
        authorization=auth,
        use_receipt=tampered,
        outcome=healthy_outcome(),
        verifier_id="outcome-verifier",
    )
    assert result.verdict is OutcomeVerdict.ESCALATE
    assert result.reason_codes == ("USE_TIME_RECEIPT_INVALID",)


def test_successful_outcome_commits():
    _, proposal, _ = fixtures()
    receipt = verify_outcome(
        proposal=proposal,
        outcome=healthy_outcome(),
        verifier_id="verifier",
        executor_id="executor",
    )
    assert receipt.verdict is OutcomeVerdict.COMMIT


def test_authorized_outcome_binds_authorization_receipt():
    proposal, _, auth = authorization()
    receipt = verify_authorized_outcome(
        proposal=proposal,
        authorization=auth,
        outcome=healthy_outcome(),
        verifier_id="outcome-verifier",
    )
    assert receipt.verdict is OutcomeVerdict.COMMIT
    assert receipt.authorization_decision_id == auth.decision_id


def test_executed_outcome_binds_use_time_receipt():
    proposal, _, auth, use = use_receipt()
    receipt = verify_executed_outcome(
        proposal=proposal,
        authorization=auth,
        use_receipt=use,
        outcome=healthy_outcome(),
        verifier_id="outcome-verifier",
    )
    assert receipt.verdict is OutcomeVerdict.COMMIT
    assert receipt.authorization_decision_id == auth.decision_id
    assert receipt.use_id == use.use_id


def test_blocked_use_time_receipt_cannot_commit_outcome():
    proposal, evidence, auth = authorization()
    blocked = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=replace(evidence, policy_ref="policy:deploy-v2"),
        executor_id="executor",
        now_ms=NOW + 1,
        execution_nonce="occurrence-1",
    )
    receipt = verify_executed_outcome(
        proposal=proposal,
        authorization=auth,
        use_receipt=blocked,
        outcome=healthy_outcome(),
        verifier_id="outcome-verifier",
    )
    assert receipt.verdict is OutcomeVerdict.ESCALATE
    assert receipt.reason_codes == ("EXECUTION_NOT_PERMITTED",)


def test_non_authorized_receipt_cannot_commit_outcome():
    intent, proposal, evidence = fixtures()
    held = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=replace(evidence, tests_passed=None),
        verifier_id="verifier",
        executor_id="executor",
        now_ms=NOW,
    )
    receipt = verify_authorized_outcome(
        proposal=proposal,
        authorization=held,
        outcome=healthy_outcome(),
        verifier_id="outcome-verifier",
    )
    assert receipt.verdict is OutcomeVerdict.ESCALATE
    assert receipt.reason_codes == ("TRANSITION_NOT_AUTHORIZED",)


def test_failed_invariant_requests_rollback():
    _, proposal, _ = fixtures()
    outcome = replace(
        healthy_outcome(),
        observed_post_state="production-degraded",
        invariant_results=(("healthcheck_ok", False), ("artifact_matches", True)),
    )
    receipt = verify_outcome(
        proposal=proposal,
        outcome=outcome,
        verifier_id="verifier",
        executor_id="executor",
    )
    assert receipt.verdict is OutcomeVerdict.ROLLBACK
    assert "INVARIANT_FAILED:healthcheck_ok" in receipt.reason_codes


def test_missing_invariant_escalates():
    _, proposal, _ = fixtures()
    outcome = replace(
        healthy_outcome(),
        invariant_results=(("healthcheck_ok", True),),
    )
    receipt = verify_outcome(
        proposal=proposal,
        outcome=outcome,
        verifier_id="verifier",
        executor_id="executor",
    )
    assert receipt.verdict is OutcomeVerdict.ESCALATE
    assert "INVARIANT_MISSING:artifact_matches" in receipt.reason_codes


def test_ledger_detects_tampering():
    ledger = EvidenceLedger()
    ledger.append("intent", {"id": "i1"})
    ledger.append("decision", {"verdict": "AUTHORIZE"})
    assert EvidenceLedger.verify(ledger.records)

    first, second = ledger.records
    tampered = LedgerRecord(
        second.index,
        second.record_type,
        {"verdict": "BLOCK"},
        second.previous_hash,
        second.record_hash,
    )
    assert not EvidenceLedger.verify((first, tampered))
