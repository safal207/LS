from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
from typing import Any, Iterable

GENESIS_HASH = "0" * 64


class TransitionVerdict(StrEnum):
    AUTHORIZE = "AUTHORIZE"
    HOLD = "HOLD"
    BLOCK = "BLOCK"


class UseTimeVerdict(StrEnum):
    EXECUTE = "EXECUTE"
    HOLD = "HOLD"
    BLOCK = "BLOCK"


class OutcomeVerdict(StrEnum):
    COMMIT = "COMMIT"
    RETRY = "RETRY"
    ROLLBACK = "ROLLBACK"
    ESCALATE = "ESCALATE"


@dataclass(frozen=True)
class TransitionIntent:
    intent_id: str
    actor: str
    action: str
    purpose: str


@dataclass(frozen=True)
class TransitionProposal:
    transition_id: str
    intent_id: str
    pre_state: str
    action: str
    expected_post_state: str
    invariants: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceBundle:
    mission_aligned: bool | None
    exact_source_bound: bool | None
    tests_passed: bool | None
    approval_current: bool | None
    approval_valid_until_ms: int | None
    evidence_refs: tuple[str, ...] = ()
    source_ref: str | None = None
    policy_ref: str | None = None
    approval_ref: str | None = None


@dataclass(frozen=True)
class AuthorizationReceipt:
    decision_id: str
    transition_id: str
    intent_id: str
    verdict: TransitionVerdict
    reason_codes: tuple[str, ...]
    verifier_id: str
    executor_id: str
    proposal_digest: str
    evidence_digest: str
    source_ref: str | None
    policy_ref: str | None
    approval_ref: str | None
    approval_valid_until_ms: int | None


@dataclass(frozen=True)
class UseTimeReceipt:
    use_id: str
    authorization_decision_id: str
    transition_id: str
    verdict: UseTimeVerdict
    reason_codes: tuple[str, ...]
    executor_id: str
    proposal_digest: str
    context_digest: str
    execution_nonce: str
    checked_at_ms: int


@dataclass(frozen=True)
class ObservedOutcome:
    transition_id: str
    observed_post_state: str
    invariant_results: tuple[tuple[str, bool], ...]
    rollback_available: bool
    retryable: bool = False


@dataclass(frozen=True)
class OutcomeReceipt:
    outcome_id: str
    transition_id: str
    verdict: OutcomeVerdict
    reason_codes: tuple[str, ...]
    verifier_id: str
    executor_id: str
    observed_outcome_digest: str
    authorization_decision_id: str | None = None
    use_id: str | None = None


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{_digest(value)[:24]}"


def _evidence_payload(evidence: EvidenceBundle) -> dict[str, Any]:
    return asdict(evidence)


def _proposal_digest(proposal: TransitionProposal) -> str:
    return _digest(asdict(proposal))


def _authorization_payload(receipt: AuthorizationReceipt) -> dict[str, Any]:
    return {
        "transition_id": receipt.transition_id,
        "intent_id": receipt.intent_id,
        "verdict": receipt.verdict.value,
        "reason_codes": list(receipt.reason_codes),
        "verifier_id": receipt.verifier_id,
        "executor_id": receipt.executor_id,
        "proposal_digest": receipt.proposal_digest,
        "evidence_digest": receipt.evidence_digest,
        "source_ref": receipt.source_ref,
        "policy_ref": receipt.policy_ref,
        "approval_ref": receipt.approval_ref,
        "approval_valid_until_ms": receipt.approval_valid_until_ms,
    }


def _use_time_payload(receipt: UseTimeReceipt) -> dict[str, Any]:
    return {
        "authorization_decision_id": receipt.authorization_decision_id,
        "transition_id": receipt.transition_id,
        "verdict": receipt.verdict.value,
        "reason_codes": list(receipt.reason_codes),
        "executor_id": receipt.executor_id,
        "proposal_digest": receipt.proposal_digest,
        "context_digest": receipt.context_digest,
        "execution_nonce": receipt.execution_nonce,
        "checked_at_ms": receipt.checked_at_ms,
    }


def verify_authorization_receipt(receipt: AuthorizationReceipt) -> bool:
    expected_id = _stable_id("auth", _authorization_payload(receipt))
    return receipt.decision_id == expected_id


def verify_use_time_receipt(receipt: UseTimeReceipt) -> bool:
    expected_id = _stable_id("use", _use_time_payload(receipt))
    return receipt.use_id == expected_id


def evaluate_transition(
    *,
    intent: TransitionIntent,
    proposal: TransitionProposal,
    evidence: EvidenceBundle,
    verifier_id: str,
    executor_id: str,
    now_ms: int,
) -> AuthorizationReceipt:
    reasons: list[str] = []
    verdict = TransitionVerdict.AUTHORIZE

    if verifier_id == executor_id:
        verdict = TransitionVerdict.BLOCK
        reasons.append("VERIFIER_EXECUTOR_COLLISION")

    if proposal.intent_id != intent.intent_id:
        verdict = TransitionVerdict.BLOCK
        reasons.append("INTENT_BINDING_MISMATCH")

    if proposal.action != intent.action:
        verdict = TransitionVerdict.BLOCK
        reasons.append("ACTION_BINDING_MISMATCH")

    checks = {
        "mission_aligned": evidence.mission_aligned,
        "exact_source_bound": evidence.exact_source_bound,
        "tests_passed": evidence.tests_passed,
        "approval_current": evidence.approval_current,
    }

    failed = [name for name, value in checks.items() if value is False]
    missing = [name for name, value in checks.items() if value is None]

    if failed:
        verdict = TransitionVerdict.BLOCK
        reasons.extend(f"EVIDENCE_FAILED:{name}" for name in failed)
    elif missing and verdict is TransitionVerdict.AUTHORIZE:
        verdict = TransitionVerdict.HOLD
        reasons.extend(f"EVIDENCE_MISSING:{name}" for name in missing)

    if evidence.approval_valid_until_ms is None:
        if verdict is TransitionVerdict.AUTHORIZE:
            verdict = TransitionVerdict.HOLD
        reasons.append("APPROVAL_EXPIRY_MISSING")
    elif now_ms > evidence.approval_valid_until_ms:
        verdict = TransitionVerdict.BLOCK
        reasons.append("APPROVAL_EXPIRED")

    required_bindings = {
        "SOURCE_REF_MISSING": evidence.source_ref,
        "POLICY_REF_MISSING": evidence.policy_ref,
        "APPROVAL_REF_MISSING": evidence.approval_ref,
    }
    for reason, value in required_bindings.items():
        if not value:
            if verdict is TransitionVerdict.AUTHORIZE:
                verdict = TransitionVerdict.HOLD
            reasons.append(reason)

    if verdict is TransitionVerdict.AUTHORIZE and not evidence.evidence_refs:
        verdict = TransitionVerdict.HOLD
        reasons.append("EVIDENCE_REFS_MISSING")

    proposal_digest = _proposal_digest(proposal)
    evidence_digest = _digest(_evidence_payload(evidence))
    decision_payload = {
        "transition_id": proposal.transition_id,
        "intent_id": proposal.intent_id,
        "verdict": verdict.value,
        "reason_codes": reasons,
        "verifier_id": verifier_id,
        "executor_id": executor_id,
        "proposal_digest": proposal_digest,
        "evidence_digest": evidence_digest,
        "source_ref": evidence.source_ref,
        "policy_ref": evidence.policy_ref,
        "approval_ref": evidence.approval_ref,
        "approval_valid_until_ms": evidence.approval_valid_until_ms,
    }

    return AuthorizationReceipt(
        decision_id=_stable_id("auth", decision_payload),
        transition_id=proposal.transition_id,
        intent_id=proposal.intent_id,
        verdict=verdict,
        reason_codes=tuple(reasons),
        verifier_id=verifier_id,
        executor_id=executor_id,
        proposal_digest=proposal_digest,
        evidence_digest=evidence_digest,
        source_ref=evidence.source_ref,
        policy_ref=evidence.policy_ref,
        approval_ref=evidence.approval_ref,
        approval_valid_until_ms=evidence.approval_valid_until_ms,
    )


def revalidate_authorization_for_use(
    *,
    proposal: TransitionProposal,
    authorization: AuthorizationReceipt,
    current_evidence: EvidenceBundle,
    executor_id: str,
    now_ms: int,
    execution_nonce: str,
) -> UseTimeReceipt:
    reasons: list[str] = []
    verdict = UseTimeVerdict.EXECUTE

    if not verify_authorization_receipt(authorization):
        verdict = UseTimeVerdict.BLOCK
        reasons.append("AUTHORIZATION_RECEIPT_INVALID")
    elif authorization.verdict is not TransitionVerdict.AUTHORIZE:
        verdict = UseTimeVerdict.BLOCK
        reasons.append("TRANSITION_NOT_AUTHORIZED")

    proposal_digest = _proposal_digest(proposal)
    if (
        authorization.transition_id != proposal.transition_id
        or authorization.intent_id != proposal.intent_id
        or authorization.proposal_digest != proposal_digest
    ):
        verdict = UseTimeVerdict.BLOCK
        reasons.append("AUTHORIZATION_TRANSITION_MISMATCH")

    if executor_id != authorization.executor_id:
        verdict = UseTimeVerdict.BLOCK
        reasons.append("EXECUTOR_BINDING_MISMATCH")

    if not execution_nonce or any(ch.isspace() for ch in execution_nonce):
        verdict = UseTimeVerdict.BLOCK
        reasons.append("EXECUTION_NONCE_INVALID")

    current_evidence_digest = _digest(_evidence_payload(current_evidence))

    comparisons = (
        ("SOURCE_REF_CHANGED", authorization.source_ref, current_evidence.source_ref),
        ("POLICY_REF_CHANGED", authorization.policy_ref, current_evidence.policy_ref),
        ("APPROVAL_REF_CHANGED", authorization.approval_ref, current_evidence.approval_ref),
    )
    for reason, authorized_value, current_value in comparisons:
        if authorized_value != current_value:
            verdict = UseTimeVerdict.BLOCK
            reasons.append(reason)

    if current_evidence_digest != authorization.evidence_digest:
        verdict = UseTimeVerdict.BLOCK
        reasons.append("EVIDENCE_CONTEXT_CHANGED")

    if current_evidence.approval_current is not True:
        verdict = UseTimeVerdict.BLOCK
        reasons.append("APPROVAL_NOT_CURRENT_AT_USE")

    if (
        authorization.approval_valid_until_ms is None
        or current_evidence.approval_valid_until_ms is None
        or now_ms > authorization.approval_valid_until_ms
        or now_ms > current_evidence.approval_valid_until_ms
    ):
        verdict = UseTimeVerdict.BLOCK
        reasons.append("APPROVAL_EXPIRED_AT_USE")

    context_payload = {
        "proposal_digest": proposal_digest,
        "evidence_digest": current_evidence_digest,
        "source_ref": current_evidence.source_ref,
        "policy_ref": current_evidence.policy_ref,
        "approval_ref": current_evidence.approval_ref,
        "approval_valid_until_ms": current_evidence.approval_valid_until_ms,
        "executor_id": executor_id,
        "checked_at_ms": now_ms,
    }
    context_digest = _digest(context_payload)
    use_payload = {
        "authorization_decision_id": authorization.decision_id,
        "transition_id": proposal.transition_id,
        "verdict": verdict.value,
        "reason_codes": reasons,
        "executor_id": executor_id,
        "proposal_digest": proposal_digest,
        "context_digest": context_digest,
        "execution_nonce": execution_nonce,
        "checked_at_ms": now_ms,
    }

    return UseTimeReceipt(
        use_id=_stable_id("use", use_payload),
        authorization_decision_id=authorization.decision_id,
        transition_id=proposal.transition_id,
        verdict=verdict,
        reason_codes=tuple(reasons),
        executor_id=executor_id,
        proposal_digest=proposal_digest,
        context_digest=context_digest,
        execution_nonce=execution_nonce,
        checked_at_ms=now_ms,
    )


class UseTokenRegistry:
    """Small in-memory reference registry for single-use execution permits."""

    def __init__(self) -> None:
        self._consumed: set[str] = set()

    def consume(self, receipt: UseTimeReceipt) -> bool:
        if not verify_use_time_receipt(receipt):
            return False
        if receipt.verdict is not UseTimeVerdict.EXECUTE:
            return False
        if receipt.use_id in self._consumed:
            return False
        self._consumed.add(receipt.use_id)
        return True

    def consumed(self, use_id: str) -> bool:
        return use_id in self._consumed


def verify_outcome(
    *,
    proposal: TransitionProposal,
    outcome: ObservedOutcome,
    verifier_id: str,
    executor_id: str,
    authorization_decision_id: str | None = None,
    use_id: str | None = None,
) -> OutcomeReceipt:
    reasons: list[str] = []

    if verifier_id == executor_id:
        verdict = OutcomeVerdict.ESCALATE
        reasons.append("VERIFIER_EXECUTOR_COLLISION")
    elif outcome.transition_id != proposal.transition_id:
        verdict = OutcomeVerdict.ESCALATE
        reasons.append("TRANSITION_BINDING_MISMATCH")
    else:
        expected = set(proposal.invariants)
        observed = {name for name, _ in outcome.invariant_results}
        missing = sorted(expected - observed)
        failed = sorted(
            name for name, ok in outcome.invariant_results
            if name in expected and not ok
        )

        if missing:
            verdict = OutcomeVerdict.ESCALATE
            reasons.extend(f"INVARIANT_MISSING:{name}" for name in missing)
        elif failed:
            reasons.extend(f"INVARIANT_FAILED:{name}" for name in failed)
            if outcome.rollback_available:
                verdict = OutcomeVerdict.ROLLBACK
            elif outcome.retryable:
                verdict = OutcomeVerdict.RETRY
            else:
                verdict = OutcomeVerdict.ESCALATE
        elif outcome.observed_post_state != proposal.expected_post_state:
            reasons.append("POST_STATE_MISMATCH")
            if outcome.rollback_available:
                verdict = OutcomeVerdict.ROLLBACK
            elif outcome.retryable:
                verdict = OutcomeVerdict.RETRY
            else:
                verdict = OutcomeVerdict.ESCALATE
        else:
            verdict = OutcomeVerdict.COMMIT

    outcome_digest = _digest(asdict(outcome))
    receipt_payload = {
        "transition_id": proposal.transition_id,
        "verdict": verdict.value,
        "reason_codes": reasons,
        "verifier_id": verifier_id,
        "executor_id": executor_id,
        "observed_outcome_digest": outcome_digest,
        "authorization_decision_id": authorization_decision_id,
        "use_id": use_id,
    }

    return OutcomeReceipt(
        outcome_id=_stable_id("outcome", receipt_payload),
        transition_id=proposal.transition_id,
        verdict=verdict,
        reason_codes=tuple(reasons),
        verifier_id=verifier_id,
        executor_id=executor_id,
        observed_outcome_digest=outcome_digest,
        authorization_decision_id=authorization_decision_id,
        use_id=use_id,
    )


def verify_authorized_outcome(
    *,
    proposal: TransitionProposal,
    authorization: AuthorizationReceipt,
    outcome: ObservedOutcome,
    verifier_id: str,
) -> OutcomeReceipt:
    if not verify_authorization_receipt(authorization):
        return _authorization_failure_outcome(
            proposal=proposal,
            outcome=outcome,
            verifier_id=verifier_id,
            executor_id=authorization.executor_id,
            authorization_decision_id=authorization.decision_id,
            reason="AUTHORIZATION_RECEIPT_INVALID",
        )
    if authorization.verdict is not TransitionVerdict.AUTHORIZE:
        return _authorization_failure_outcome(
            proposal=proposal,
            outcome=outcome,
            verifier_id=verifier_id,
            executor_id=authorization.executor_id,
            authorization_decision_id=authorization.decision_id,
            reason="TRANSITION_NOT_AUTHORIZED",
        )
    if (
        authorization.transition_id != proposal.transition_id
        or authorization.intent_id != proposal.intent_id
        or authorization.proposal_digest != _proposal_digest(proposal)
    ):
        return _authorization_failure_outcome(
            proposal=proposal,
            outcome=outcome,
            verifier_id=verifier_id,
            executor_id=authorization.executor_id,
            authorization_decision_id=authorization.decision_id,
            reason="AUTHORIZATION_TRANSITION_MISMATCH",
        )
    return verify_outcome(
        proposal=proposal,
        outcome=outcome,
        verifier_id=verifier_id,
        executor_id=authorization.executor_id,
        authorization_decision_id=authorization.decision_id,
    )


def verify_executed_outcome(
    *,
    proposal: TransitionProposal,
    authorization: AuthorizationReceipt,
    use_receipt: UseTimeReceipt,
    outcome: ObservedOutcome,
    verifier_id: str,
) -> OutcomeReceipt:
    if not verify_authorization_receipt(authorization):
        return _execution_failure_outcome(
            proposal=proposal,
            outcome=outcome,
            verifier_id=verifier_id,
            executor_id=authorization.executor_id,
            authorization_decision_id=authorization.decision_id,
            use_id=use_receipt.use_id,
            reason="AUTHORIZATION_RECEIPT_INVALID",
        )
    if not verify_use_time_receipt(use_receipt):
        return _execution_failure_outcome(
            proposal=proposal,
            outcome=outcome,
            verifier_id=verifier_id,
            executor_id=authorization.executor_id,
            authorization_decision_id=authorization.decision_id,
            use_id=use_receipt.use_id,
            reason="USE_TIME_RECEIPT_INVALID",
        )
    if use_receipt.verdict is not UseTimeVerdict.EXECUTE:
        return _execution_failure_outcome(
            proposal=proposal,
            outcome=outcome,
            verifier_id=verifier_id,
            executor_id=authorization.executor_id,
            authorization_decision_id=authorization.decision_id,
            use_id=use_receipt.use_id,
            reason="EXECUTION_NOT_PERMITTED",
        )
    if (
        use_receipt.authorization_decision_id != authorization.decision_id
        or use_receipt.transition_id != proposal.transition_id
        or use_receipt.proposal_digest != _proposal_digest(proposal)
        or use_receipt.executor_id != authorization.executor_id
    ):
        return _execution_failure_outcome(
            proposal=proposal,
            outcome=outcome,
            verifier_id=verifier_id,
            executor_id=authorization.executor_id,
            authorization_decision_id=authorization.decision_id,
            use_id=use_receipt.use_id,
            reason="USE_TIME_BINDING_MISMATCH",
        )

    return verify_outcome(
        proposal=proposal,
        outcome=outcome,
        verifier_id=verifier_id,
        executor_id=authorization.executor_id,
        authorization_decision_id=authorization.decision_id,
        use_id=use_receipt.use_id,
    )


def _authorization_failure_outcome(
    *,
    proposal: TransitionProposal,
    outcome: ObservedOutcome,
    verifier_id: str,
    executor_id: str,
    authorization_decision_id: str,
    reason: str,
) -> OutcomeReceipt:
    return _execution_failure_outcome(
        proposal=proposal,
        outcome=outcome,
        verifier_id=verifier_id,
        executor_id=executor_id,
        authorization_decision_id=authorization_decision_id,
        use_id=None,
        reason=reason,
    )


def _execution_failure_outcome(
    *,
    proposal: TransitionProposal,
    outcome: ObservedOutcome,
    verifier_id: str,
    executor_id: str,
    authorization_decision_id: str,
    use_id: str | None,
    reason: str,
) -> OutcomeReceipt:
    outcome_digest = _digest(asdict(outcome))
    receipt_payload = {
        "transition_id": proposal.transition_id,
        "verdict": OutcomeVerdict.ESCALATE.value,
        "reason_codes": [reason],
        "verifier_id": verifier_id,
        "executor_id": executor_id,
        "observed_outcome_digest": outcome_digest,
        "authorization_decision_id": authorization_decision_id,
        "use_id": use_id,
    }
    return OutcomeReceipt(
        outcome_id=_stable_id("outcome", receipt_payload),
        transition_id=proposal.transition_id,
        verdict=OutcomeVerdict.ESCALATE,
        reason_codes=(reason,),
        verifier_id=verifier_id,
        executor_id=executor_id,
        observed_outcome_digest=outcome_digest,
        authorization_decision_id=authorization_decision_id,
        use_id=use_id,
    )


@dataclass(frozen=True)
class LedgerRecord:
    index: int
    record_type: str
    payload: dict[str, Any]
    previous_hash: str
    record_hash: str


class EvidenceLedger:
    def __init__(self) -> None:
        self._records: list[LedgerRecord] = []

    @property
    def records(self) -> tuple[LedgerRecord, ...]:
        return tuple(deepcopy(self._records))

    def append(self, record_type: str, payload: dict[str, Any]) -> LedgerRecord:
        previous_hash = self._records[-1].record_hash if self._records else GENESIS_HASH
        index = len(self._records)
        stored_payload = deepcopy(payload)
        preimage = {
            "index": index,
            "record_type": record_type,
            "payload": stored_payload,
            "previous_hash": previous_hash,
        }
        record = LedgerRecord(
            index=index,
            record_type=record_type,
            payload=stored_payload,
            previous_hash=previous_hash,
            record_hash=_digest(preimage),
        )
        self._records.append(record)
        return deepcopy(record)

    @staticmethod
    def verify(records: Iterable[LedgerRecord]) -> bool:
        previous_hash = GENESIS_HASH
        for expected_index, record in enumerate(records):
            if record.index != expected_index or record.previous_hash != previous_hash:
                return False
            preimage = {
                "index": record.index,
                "record_type": record.record_type,
                "payload": record.payload,
                "previous_hash": record.previous_hash,
            }
            if record.record_hash != _digest(preimage):
                return False
            previous_hash = record.record_hash
        return True