from __future__ import annotations

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


@dataclass(frozen=True)
class AuthorizationReceipt:
    decision_id: str
    transition_id: str
    verdict: TransitionVerdict
    reason_codes: tuple[str, ...]
    verifier_id: str
    executor_id: str
    evidence_digest: str


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

    if verdict is TransitionVerdict.AUTHORIZE and not evidence.evidence_refs:
        verdict = TransitionVerdict.HOLD
        reasons.append("EVIDENCE_REFS_MISSING")

    evidence_digest = _digest(_evidence_payload(evidence))
    decision_payload = {
        "transition_id": proposal.transition_id,
        "intent_id": proposal.intent_id,
        "verdict": verdict.value,
        "reason_codes": reasons,
        "verifier_id": verifier_id,
        "executor_id": executor_id,
        "evidence_digest": evidence_digest,
    }

    return AuthorizationReceipt(
        decision_id=_stable_id("auth", decision_payload),
        transition_id=proposal.transition_id,
        verdict=verdict,
        reason_codes=tuple(reasons),
        verifier_id=verifier_id,
        executor_id=executor_id,
        evidence_digest=evidence_digest,
    )


def verify_outcome(
    *,
    proposal: TransitionProposal,
    outcome: ObservedOutcome,
    verifier_id: str,
    executor_id: str,
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
        failed = sorted(name for name, ok in outcome.invariant_results if name in expected and not ok)

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
    }

    return OutcomeReceipt(
        outcome_id=_stable_id("outcome", receipt_payload),
        transition_id=proposal.transition_id,
        verdict=verdict,
        reason_codes=tuple(reasons),
        verifier_id=verifier_id,
        executor_id=executor_id,
        observed_outcome_digest=outcome_digest,
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
        return tuple(self._records)

    def append(self, record_type: str, payload: dict[str, Any]) -> LedgerRecord:
        previous_hash = self._records[-1].record_hash if self._records else GENESIS_HASH
        index = len(self._records)
        preimage = {
            "index": index,
            "record_type": record_type,
            "payload": payload,
            "previous_hash": previous_hash,
        }
        record = LedgerRecord(
            index=index,
            record_type=record_type,
            payload=payload,
            previous_hash=previous_hash,
            record_hash=_digest(preimage),
        )
        self._records.append(record)
        return record

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
