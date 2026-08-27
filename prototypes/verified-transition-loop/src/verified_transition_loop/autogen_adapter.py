from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
from typing import Any, Callable

from .core import (
    AuthorizationReceipt,
    EvidenceBundle,
    TransitionIntent,
    TransitionProposal,
    TransitionVerdict,
    UseTimeVerdict,
    UseTokenRegistry,
    evaluate_transition,
    revalidate_authorization_for_use,
)


class MissionAssessment(StrEnum):
    ALIGNED = "ALIGNED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    REJECTED = "REJECTED"


class MissionControlDecision(StrEnum):
    CONTINUE = "CONTINUE"
    HALT = "HALT"
    REQUIRE_REVIEW = "REQUIRE_REVIEW"


@dataclass(frozen=True)
class MissionTransitionRequest:
    """AutoGen-shaped transition request without importing AutoGen."""

    mission_id: str
    mission_version: str
    transition_id: str
    actor_id: str
    action: str
    rationale: str
    pre_state: str
    expected_post_state: str
    invariants: tuple[str, ...]
    occurrence_id: str


@dataclass(frozen=True)
class AutoGenVTLContext:
    """Current facts resolved by the embedding runtime at assessment/use time."""

    current_mission_id: str
    current_mission_version: str
    evidence: EvidenceBundle
    executor_id: str
    verifier_id: str = "vtl-autogen-mission-keeper"


@dataclass(frozen=True)
class MissionIntegrityRecord:
    """Historical pre-action assessment; never an execution token."""

    record_id: str
    request_digest: str
    mission_id: str
    mission_version: str
    transition_id: str
    actor_id: str
    verifier_id: str
    executor_id: str
    assessment: MissionAssessment
    reason_codes: tuple[str, ...]
    authorization_decision_id: str | None
    proposal_digest: str | None
    execution_allowed: bool = False


@dataclass(frozen=True)
class MissionControlRecord:
    """Narrow use-time gate output. The adapter still performs no execution."""

    control_id: str
    integrity_record_id: str
    decision: MissionControlDecision
    reason_codes: tuple[str, ...]
    use_id: str | None
    transition_may_proceed: bool
    execution_binding: str = "external"


@dataclass(frozen=True)
class MissionObservedOutcome:
    """Observed result kept separate from the pre-action integrity record."""

    transition_id: str
    outcome_ref: str
    observed_state: str


@dataclass(frozen=True)
class MissionOutcomeLink:
    integrity_record_id: str
    transition_id: str
    outcome_ref: str


@dataclass
class _PendingMissionDecision:
    request_digest: str
    occurrence_id: str
    intent: TransitionIntent
    proposal: TransitionProposal
    authorization: AuthorizationReceipt
    mission_id: str
    mission_version: str
    consumed: bool = False


ContextResolver = Callable[[MissionTransitionRequest], AutoGenVTLContext]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _request_digest(request: MissionTransitionRequest) -> str:
    return _digest(asdict(request))


def _record_id(request_digest: str, authorization_id: str | None) -> str:
    return "mission_" + _digest(
        {"request": request_digest, "authorization": authorization_id or "none"}
    )[:24]


def _control_id(record_id: str, decision: str, use_id: str | None) -> str:
    return "control_" + _digest(
        {"record": record_id, "decision": decision, "use_id": use_id or "none"}
    )[:24]


def _assessment_record(
    *,
    request: MissionTransitionRequest,
    request_digest: str,
    context: AutoGenVTLContext,
    assessment: MissionAssessment,
    reason_codes: tuple[str, ...],
    authorization: AuthorizationReceipt | None = None,
) -> MissionIntegrityRecord:
    authorization_id = authorization.decision_id if authorization else None
    proposal_digest = authorization.proposal_digest if authorization else None
    return MissionIntegrityRecord(
        record_id=_record_id(request_digest, authorization_id),
        request_digest=request_digest,
        mission_id=request.mission_id,
        mission_version=request.mission_version,
        transition_id=request.transition_id,
        actor_id=request.actor_id,
        verifier_id=context.verifier_id,
        executor_id=context.executor_id,
        assessment=assessment,
        reason_codes=reason_codes,
        authorization_decision_id=authorization_id,
        proposal_digest=proposal_digest,
        execution_allowed=False,
    )


def _context_failure_record(
    request: MissionTransitionRequest,
    request_digest: str,
) -> MissionIntegrityRecord:
    """Fail closed without fabricating an EvidenceBundle or execution authority."""

    return MissionIntegrityRecord(
        record_id=_record_id(request_digest, None),
        request_digest=request_digest,
        mission_id=request.mission_id,
        mission_version=request.mission_version,
        transition_id=request.transition_id,
        actor_id=request.actor_id,
        verifier_id="vtl-autogen-mission-keeper",
        executor_id="unknown-executor",
        assessment=MissionAssessment.REJECTED,
        reason_codes=("CONTEXT_RESOLUTION_FAILED",),
        authorization_decision_id=None,
        proposal_digest=None,
        execution_allowed=False,
    )


def _control(
    *,
    record_id: str,
    decision: MissionControlDecision,
    reasons: tuple[str, ...],
    use_id: str | None = None,
) -> MissionControlRecord:
    return MissionControlRecord(
        control_id=_control_id(record_id, decision.value, use_id),
        integrity_record_id=record_id,
        decision=decision,
        reason_codes=reasons,
        use_id=use_id,
        transition_may_proceed=decision is MissionControlDecision.CONTINUE,
        execution_binding="external",
    )


class AutoGenMissionKeeperAdapter:
    """Reference Mission Keeper compatibility layer for VTL.

    ``assess`` emits a historical MissionIntegrityRecord. ``gate`` performs the
    fresh use-time check immediately before a transition may be released. The
    class intentionally exposes no executor, repair, rewrite, or mutation API.
    """

    name = "verified-transition-loop-autogen-mission-keeper"

    def __init__(self, context_resolver: ContextResolver) -> None:
        self._resolve = context_resolver
        self._pending: dict[str, _PendingMissionDecision] = {}
        self._pending_by_occurrence: dict[str, str] = {}
        self._released_occurrences: set[str] = set()
        self._use_registry = UseTokenRegistry()

    def assess(
        self,
        request: MissionTransitionRequest,
        *,
        now_ms: int,
    ) -> MissionIntegrityRecord:
        request_digest = _request_digest(request)

        try:
            context = self._resolve(request)
        except Exception:
            return _context_failure_record(request, request_digest)

        if not request.occurrence_id:
            return _assessment_record(
                request=request,
                request_digest=request_digest,
                context=context,
                assessment=MissionAssessment.REJECTED,
                reason_codes=("OCCURRENCE_ID_MISSING",),
            )
        if request.occurrence_id in self._released_occurrences:
            return _assessment_record(
                request=request,
                request_digest=request_digest,
                context=context,
                assessment=MissionAssessment.REJECTED,
                reason_codes=("OCCURRENCE_ALREADY_RELEASED",),
            )
        if context.verifier_id == context.executor_id:
            return _assessment_record(
                request=request,
                request_digest=request_digest,
                context=context,
                assessment=MissionAssessment.REJECTED,
                reason_codes=("VERIFIER_EXECUTOR_NOT_SEPARATED",),
            )
        if context.current_mission_id != request.mission_id:
            return _assessment_record(
                request=request,
                request_digest=request_digest,
                context=context,
                assessment=MissionAssessment.REJECTED,
                reason_codes=("MISSION_ID_CHANGED",),
            )
        if context.current_mission_version != request.mission_version:
            return _assessment_record(
                request=request,
                request_digest=request_digest,
                context=context,
                assessment=MissionAssessment.REJECTED,
                reason_codes=("MISSION_VERSION_CHANGED",),
            )

        existing_ref = self._pending_by_occurrence.get(request.occurrence_id)
        if existing_ref is not None:
            existing = self._pending.get(existing_ref)
            if existing is not None and not existing.consumed:
                return _assessment_record(
                    request=request,
                    request_digest=request_digest,
                    context=context,
                    assessment=MissionAssessment.REJECTED,
                    reason_codes=("OCCURRENCE_ALREADY_PENDING",),
                )

        suffix = request_digest[:20]
        intent = TransitionIntent(
            intent_id=f"autogen-intent-{suffix}",
            actor=request.actor_id,
            action=request.action,
            purpose=request.rationale,
        )
        proposal = TransitionProposal(
            transition_id=request.transition_id,
            intent_id=intent.intent_id,
            pre_state=request.pre_state,
            action=request.action,
            expected_post_state=request.expected_post_state,
            invariants=request.invariants,
        )
        authorization = evaluate_transition(
            intent=intent,
            proposal=proposal,
            evidence=context.evidence,
            verifier_id=context.verifier_id,
            executor_id=context.executor_id,
            now_ms=now_ms,
        )

        if authorization.verdict is TransitionVerdict.AUTHORIZE:
            assessment = MissionAssessment.ALIGNED
        elif authorization.verdict is TransitionVerdict.HOLD:
            assessment = MissionAssessment.REVIEW_REQUIRED
        else:
            assessment = MissionAssessment.REJECTED

        record = _assessment_record(
            request=request,
            request_digest=request_digest,
            context=context,
            assessment=assessment,
            reason_codes=authorization.reason_codes,
            authorization=authorization,
        )

        if authorization.verdict is not TransitionVerdict.BLOCK:
            existing = self._pending.get(record.record_id)
            if existing is None:
                self._pending[record.record_id] = _PendingMissionDecision(
                    request_digest=request_digest,
                    occurrence_id=request.occurrence_id,
                    intent=intent,
                    proposal=proposal,
                    authorization=authorization,
                    mission_id=request.mission_id,
                    mission_version=request.mission_version,
                )
                self._pending_by_occurrence[request.occurrence_id] = record.record_id

        return record

    def gate(
        self,
        integrity_record_id: str,
        request: MissionTransitionRequest,
        *,
        now_ms: int,
        execution_nonce: str,
    ) -> MissionControlRecord:
        pending = self._pending.get(integrity_record_id)
        if pending is None:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("INTEGRITY_RECORD_NOT_FOUND",),
            )
        if pending.consumed:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("INTEGRITY_RECORD_ALREADY_USED",),
            )
        if pending.occurrence_id in self._released_occurrences:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("OCCURRENCE_ALREADY_RELEASED",),
            )
        if _request_digest(request) != pending.request_digest:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("REQUEST_BINDING_MISMATCH",),
            )
        if execution_nonce != pending.occurrence_id:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("OCCURRENCE_BINDING_MISMATCH",),
            )

        try:
            context = self._resolve(request)
        except Exception:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("CONTEXT_RESOLUTION_FAILED",),
            )

        if context.verifier_id == context.executor_id:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("VERIFIER_EXECUTOR_NOT_SEPARATED",),
            )
        if context.current_mission_id != pending.mission_id:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("MISSION_ID_CHANGED",),
            )
        if context.current_mission_version != pending.mission_version:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.HALT,
                reasons=("MISSION_VERSION_CHANGED",),
            )

        authorization = pending.authorization

        # A historical HOLD carries no latent authority. New approval/evidence
        # requires a fresh authorization decision before use-time evaluation.
        if authorization.verdict is TransitionVerdict.HOLD:
            authorization = evaluate_transition(
                intent=pending.intent,
                proposal=pending.proposal,
                evidence=context.evidence,
                verifier_id=context.verifier_id,
                executor_id=context.executor_id,
                now_ms=now_ms,
            )
            if authorization.verdict is TransitionVerdict.HOLD:
                return _control(
                    record_id=integrity_record_id,
                    decision=MissionControlDecision.REQUIRE_REVIEW,
                    reasons=authorization.reason_codes,
                )
            if authorization.verdict is TransitionVerdict.BLOCK:
                return _control(
                    record_id=integrity_record_id,
                    decision=MissionControlDecision.HALT,
                    reasons=authorization.reason_codes,
                )
            pending.authorization = authorization

        use_receipt = revalidate_authorization_for_use(
            proposal=pending.proposal,
            authorization=authorization,
            current_evidence=context.evidence,
            executor_id=context.executor_id,
            now_ms=now_ms,
            execution_nonce=execution_nonce,
        )

        if use_receipt.verdict is UseTimeVerdict.EXECUTE:
            if not self._use_registry.consume(use_receipt):
                return _control(
                    record_id=integrity_record_id,
                    decision=MissionControlDecision.HALT,
                    reasons=("EXECUTION_PERMIT_REPLAYED",),
                    use_id=use_receipt.use_id,
                )
            pending.consumed = True
            self._released_occurrences.add(pending.occurrence_id)
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.CONTINUE,
                reasons=(),
                use_id=use_receipt.use_id,
            )

        if use_receipt.verdict is UseTimeVerdict.HOLD:
            return _control(
                record_id=integrity_record_id,
                decision=MissionControlDecision.REQUIRE_REVIEW,
                reasons=use_receipt.reason_codes,
                use_id=use_receipt.use_id,
            )

        return _control(
            record_id=integrity_record_id,
            decision=MissionControlDecision.HALT,
            reasons=use_receipt.reason_codes,
            use_id=use_receipt.use_id,
        )


def link_observed_outcome(
    integrity_record: MissionIntegrityRecord,
    outcome: MissionObservedOutcome,
) -> MissionOutcomeLink:
    """Create an audit link without mutating the pre-action integrity record."""

    if outcome.transition_id != integrity_record.transition_id:
        raise ValueError("OUTCOME_TRANSITION_MISMATCH")
    return MissionOutcomeLink(
        integrity_record_id=integrity_record.record_id,
        transition_id=outcome.transition_id,
        outcome_ref=outcome.outcome_ref,
    )
