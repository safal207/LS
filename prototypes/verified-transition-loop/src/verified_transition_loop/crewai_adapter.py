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


class CrewGuardrailDisposition(StrEnum):
    ALLOW = "ALLOW"
    DEFER = "DEFER"
    DENY = "DENY"


@dataclass(frozen=True)
class CrewGuardrailRequest:
    """CrewAI-shaped pre-tool-call request without importing CrewAI."""

    tool_name: str
    tool_input: dict[str, Any]
    agent_role: str | None = None
    task_description: str | None = None
    crew_id: str | None = None
    timestamp: str = ""
    tool_call_id: str | None = None


@dataclass(frozen=True)
class CrewVTLContext:
    """VTL facts resolved by the embedding application for one tool call."""

    pre_state: str
    expected_post_state: str
    invariants: tuple[str, ...]
    evidence: EvidenceBundle
    executor_id: str
    verifier_id: str = "vtl-crewai-pretool-verifier"


@dataclass(frozen=True)
class CrewGuardrailDecision:
    disposition: CrewGuardrailDisposition
    reason_codes: tuple[str, ...]
    decision_ref: str | None
    continuation_token: str | None
    execution_allowed: bool
    execution_binding: str
    authorization_decision_id: str | None = None
    use_id: str | None = None


@dataclass
class _PendingDecision:
    request_digest: str
    occurrence_id: str
    intent: TransitionIntent
    proposal: TransitionProposal
    authorization: AuthorizationReceipt
    frozen_evidence: EvidenceBundle
    consumed: bool = False


ContextResolver = Callable[[CrewGuardrailRequest], CrewVTLContext]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _request_digest(request: CrewGuardrailRequest) -> str:
    return _digest(asdict(request))


def _occurrence_id(request: CrewGuardrailRequest) -> str | None:
    if request.tool_call_id:
        return request.tool_call_id
    if request.timestamp:
        return request.timestamp
    return None


def _tool_action(request: CrewGuardrailRequest) -> str:
    args_digest = _digest(request.tool_input)[:24]
    return f"tool:{request.tool_name}:{args_digest}"


def _decision_ref(request_digest: str, authorization_id: str) -> str:
    return f"crew_vtl_{_digest({'request': request_digest, 'authorization': authorization_id})[:24]}"


def _continuation_token(decision_ref: str, occurrence_id: str) -> str:
    return f"cont_{_digest({'decision_ref': decision_ref, 'occurrence_id': occurrence_id})[:24]}"


def _deny(*reasons: str, decision_ref: str | None = None) -> CrewGuardrailDecision:
    return CrewGuardrailDecision(
        disposition=CrewGuardrailDisposition.DENY,
        reason_codes=tuple(reasons),
        decision_ref=decision_ref,
        continuation_token=None,
        execution_allowed=False,
        execution_binding="external",
    )


class CrewVTLGuardrailProvider:
    """Reference adapter for CrewAI's proposed pre-tool-call provider shape.

    It intentionally has no CrewAI runtime dependency. ``evaluate`` models the
    provider's first decision. ``resume`` models the deferred continuation at
    the point immediately before the tool call is released.
    """

    name = "verified-transition-loop"

    def __init__(self, context_resolver: ContextResolver) -> None:
        self._resolve = context_resolver
        self._pending: dict[str, _PendingDecision] = {}
        self._use_registry = UseTokenRegistry()

    def health_check(self) -> bool:
        return True

    def evaluate(
        self,
        request: CrewGuardrailRequest,
        *,
        now_ms: int,
    ) -> CrewGuardrailDecision:
        occurrence_id = _occurrence_id(request)
        if occurrence_id is None:
            return _deny("OCCURRENCE_ID_MISSING")

        try:
            context = self._resolve(request)
        except Exception:
            return _deny("CONTEXT_RESOLUTION_FAILED")

        request_digest = _request_digest(request)
        action = _tool_action(request)
        suffix = request_digest[:20]
        intent = TransitionIntent(
            intent_id=f"crew-intent-{suffix}",
            actor=request.agent_role or "crew-agent",
            action=action,
            purpose=request.task_description or f"execute CrewAI tool {request.tool_name}",
        )
        proposal = TransitionProposal(
            transition_id=f"crew-transition-{suffix}",
            intent_id=intent.intent_id,
            pre_state=context.pre_state,
            action=action,
            expected_post_state=context.expected_post_state,
            invariants=context.invariants,
        )
        authorization = evaluate_transition(
            intent=intent,
            proposal=proposal,
            evidence=context.evidence,
            verifier_id=context.verifier_id,
            executor_id=context.executor_id,
            now_ms=now_ms,
        )

        decision_ref = _decision_ref(request_digest, authorization.decision_id)
        token = _continuation_token(decision_ref, occurrence_id)

        if authorization.verdict is TransitionVerdict.BLOCK:
            return CrewGuardrailDecision(
                disposition=CrewGuardrailDisposition.DENY,
                reason_codes=authorization.reason_codes,
                decision_ref=decision_ref,
                continuation_token=None,
                execution_allowed=False,
                execution_binding="external",
                authorization_decision_id=authorization.decision_id,
            )

        self._pending[decision_ref] = _PendingDecision(
            request_digest=request_digest,
            occurrence_id=occurrence_id,
            intent=intent,
            proposal=proposal,
            authorization=authorization,
            frozen_evidence=context.evidence,
        )

        reasons = authorization.reason_codes
        if authorization.verdict is TransitionVerdict.AUTHORIZE:
            reasons = ("USE_TIME_REVALIDATION_REQUIRED",)

        return CrewGuardrailDecision(
            disposition=CrewGuardrailDisposition.DEFER,
            reason_codes=reasons,
            decision_ref=decision_ref,
            continuation_token=token,
            execution_allowed=False,
            execution_binding="external",
            authorization_decision_id=authorization.decision_id,
        )

    def resume(
        self,
        decision_ref: str,
        request: CrewGuardrailRequest,
        *,
        now_ms: int,
        execution_nonce: str,
    ) -> CrewGuardrailDecision:
        pending = self._pending.get(decision_ref)
        if pending is None:
            return _deny("CONTINUATION_NOT_FOUND", decision_ref=decision_ref)
        if pending.consumed:
            return _deny("CONTINUATION_ALREADY_USED", decision_ref=decision_ref)
        if _request_digest(request) != pending.request_digest:
            return _deny("REQUEST_BINDING_MISMATCH", decision_ref=decision_ref)

        try:
            context = self._resolve(request)
        except Exception:
            return _deny("CONTEXT_RESOLUTION_FAILED", decision_ref=decision_ref)

        authorization = pending.authorization

        # HOLD means no authority existed yet. A resumed asynchronous approval
        # therefore needs a fresh authorization decision before use-time checks.
        if authorization.verdict is TransitionVerdict.HOLD:
            authorization = evaluate_transition(
                intent=pending.intent,
                proposal=pending.proposal,
                evidence=context.evidence,
                verifier_id=context.verifier_id,
                executor_id=context.executor_id,
                now_ms=now_ms,
            )
            if authorization.verdict is TransitionVerdict.BLOCK:
                return CrewGuardrailDecision(
                    disposition=CrewGuardrailDisposition.DENY,
                    reason_codes=authorization.reason_codes,
                    decision_ref=decision_ref,
                    continuation_token=None,
                    execution_allowed=False,
                    execution_binding="external",
                    authorization_decision_id=authorization.decision_id,
                )
            if authorization.verdict is TransitionVerdict.HOLD:
                return CrewGuardrailDecision(
                    disposition=CrewGuardrailDisposition.DEFER,
                    reason_codes=authorization.reason_codes,
                    decision_ref=decision_ref,
                    continuation_token=_continuation_token(
                        decision_ref,
                        pending.occurrence_id,
                    ),
                    execution_allowed=False,
                    execution_binding="external",
                    authorization_decision_id=authorization.decision_id,
                )
            pending.authorization = authorization
            pending.frozen_evidence = context.evidence

        use_receipt = revalidate_authorization_for_use(
            proposal=pending.proposal,
            authorization=authorization,
            current_evidence=context.evidence,
            executor_id=context.executor_id,
            now_ms=now_ms,
            execution_nonce=execution_nonce,
        )

        if use_receipt.verdict is not UseTimeVerdict.EXECUTE:
            return CrewGuardrailDecision(
                disposition=CrewGuardrailDisposition.DENY,
                reason_codes=use_receipt.reason_codes,
                decision_ref=decision_ref,
                continuation_token=None,
                execution_allowed=False,
                execution_binding="external",
                authorization_decision_id=authorization.decision_id,
                use_id=use_receipt.use_id,
            )

        if not self._use_registry.consume(use_receipt):
            return CrewGuardrailDecision(
                disposition=CrewGuardrailDisposition.DENY,
                reason_codes=("EXECUTION_PERMIT_REPLAYED",),
                decision_ref=decision_ref,
                continuation_token=None,
                execution_allowed=False,
                execution_binding="external",
                authorization_decision_id=authorization.decision_id,
                use_id=use_receipt.use_id,
            )

        pending.consumed = True
        return CrewGuardrailDecision(
            disposition=CrewGuardrailDisposition.ALLOW,
            reason_codes=(),
            decision_ref=decision_ref,
            continuation_token=None,
            execution_allowed=True,
            execution_binding="external",
            authorization_decision_id=authorization.decision_id,
            use_id=use_receipt.use_id,
        )
