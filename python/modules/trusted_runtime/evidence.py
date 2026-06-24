from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Optional

from .contracts import (
    CognitiveTrail,
    DecisionCode,
    EvidenceDecision,
    ReusableArtifact,
    TrailEvent,
    TrailEventType,
)


class EvidenceGateError(RuntimeError):
    """Base error for evidence-gate integrations and decision guards."""


class EvidenceGateDisabledError(EvidenceGateError):
    """Raised when an optional evidence-gate integration is disabled."""


class EvidenceGateUnavailableError(EvidenceGateError):
    """Raised when an evidence-gate backend cannot be reached or invoked."""


class MalformedEvidenceDecisionResponseError(EvidenceGateError):
    """Raised when a gate returns an unusable decision payload."""


class EvidenceArtifactMismatchError(EvidenceGateError):
    """Raised when a decision does not match the evidence request."""


class EvidenceDecisionNotAllow(EvidenceGateError):
    """Raised when a non-ALLOW result reaches an authorization boundary."""


@dataclass(frozen=True)
class EvidenceGateRequest:
    request_id: str
    task_id: str
    trail_id: str
    actor: str
    intent_ref: str
    scope: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    policy_version: str
    causal_audit_ref: str
    causal_authorization_allowed: bool
    created_at: str
    artifact_digest: str
    artifact_verified: bool
    missing_evidence_refs: tuple[str, ...] = ()
    risk_flags: tuple[str, ...] = ()
    escalation_reasons: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = (
            self.request_id,
            self.task_id,
            self.trail_id,
            self.actor,
            self.intent_ref,
            self.policy_version,
            self.causal_audit_ref,
            self.created_at,
        )
        if not all(required):
            raise ValueError("evidence gate identifiers and timestamps must not be empty")
        if not self.scope:
            raise ValueError("evidence gate request requires a non-empty scope")
        if len(self.scope) != len(set(self.scope)):
            raise ValueError("evidence gate scope must be unique")
        for name, values in (
            ("evidence_refs", self.evidence_refs),
            ("missing_evidence_refs", self.missing_evidence_refs),
            ("risk_flags", self.risk_flags),
            ("escalation_reasons", self.escalation_reasons),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"{name} must be unique")
        if self.artifact_verified and not self.artifact_digest:
            raise ValueError("verified evidence artifact requires a digest")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "EvidenceGateRequest":
        return cls(
            request_id=str(payload["request_id"]),
            task_id=str(payload["task_id"]),
            trail_id=str(payload["trail_id"]),
            actor=str(payload["actor"]),
            intent_ref=str(payload["intent_ref"]),
            scope=tuple(str(value) for value in payload["scope"]),
            evidence_refs=tuple(str(value) for value in payload.get("evidence_refs", ())),
            policy_version=str(payload["policy_version"]),
            causal_audit_ref=str(payload["causal_audit_ref"]),
            causal_authorization_allowed=bool(payload["causal_authorization_allowed"]),
            created_at=str(payload["created_at"]),
            artifact_digest=str(payload.get("artifact_digest", "")),
            artifact_verified=bool(payload.get("artifact_verified", False)),
            missing_evidence_refs=tuple(
                str(value) for value in payload.get("missing_evidence_refs", ())
            ),
            risk_flags=tuple(str(value) for value in payload.get("risk_flags", ())),
            escalation_reasons=tuple(
                str(value) for value in payload.get("escalation_reasons", ())
            ),
            metadata=dict(payload.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "actor": self.actor,
            "intent_ref": self.intent_ref,
            "scope": list(self.scope),
            "evidence_refs": list(self.evidence_refs),
            "policy_version": self.policy_version,
            "causal_audit_ref": self.causal_audit_ref,
            "causal_authorization_allowed": self.causal_authorization_allowed,
            "created_at": self.created_at,
            "artifact_digest": self.artifact_digest,
            "artifact_verified": self.artifact_verified,
            "missing_evidence_refs": list(self.missing_evidence_refs),
            "risk_flags": list(self.risk_flags),
            "escalation_reasons": list(self.escalation_reasons),
            "metadata": dict(self.metadata),
        }


class DeterministicEvidenceGateAdapter:
    """Dependency-free ALLOW/HOLD/BLOCK/ESCALATE reference gate."""

    def __init__(self, actor: str = "adapter:deterministic-evidence-gate") -> None:
        if not actor:
            raise ValueError("evidence gate actor must not be empty")
        self.actor = actor

    @property
    def adapter_name(self) -> str:
        return "deterministic-evidence-gate"

    def decide(self, request: Mapping[str, Any]) -> EvidenceDecision:
        gate_request = EvidenceGateRequest.from_mapping(request)
        decision, reason = self._evaluate(gate_request)
        return EvidenceDecision(
            task_id=gate_request.task_id,
            trail_id=gate_request.trail_id,
            decision=decision,
            reason=reason,
            policy_version=gate_request.policy_version,
            actor=self.actor,
            created_at=gate_request.created_at,
            evidence_refs=gate_request.evidence_refs,
            parent_cause=gate_request.causal_audit_ref,
        )

    @staticmethod
    def _evaluate(request: EvidenceGateRequest) -> tuple[DecisionCode, str]:
        if not request.causal_authorization_allowed:
            return DecisionCode.BLOCK, "causal_authorization_not_allowed"
        if request.risk_flags:
            return (
                DecisionCode.BLOCK,
                "risk_flags:" + ",".join(request.risk_flags),
            )
        if request.escalation_reasons:
            return (
                DecisionCode.ESCALATE,
                "human_review_required:" + ",".join(request.escalation_reasons),
            )
        if request.missing_evidence_refs:
            return (
                DecisionCode.HOLD,
                "missing_evidence:" + ",".join(request.missing_evidence_refs),
            )
        if not request.evidence_refs:
            return DecisionCode.HOLD, "no_evidence_references"
        if not request.artifact_verified or not request.artifact_digest:
            return DecisionCode.HOLD, "evidence_artifact_not_verified"
        return DecisionCode.ALLOW, "evidence_policy_and_causal_checks_passed"


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def evidence_decision_ref(decision: EvidenceDecision) -> str:
    digest = hashlib.sha256(
        canonical_json(decision.to_dict()).encode("utf-8")
    ).hexdigest()
    return f"decision:sha256:{digest}"


def require_allow_decision(decision: EvidenceDecision) -> EvidenceDecision:
    if decision.decision is not DecisionCode.ALLOW:
        raise EvidenceDecisionNotAllow(
            f"authorization requires ALLOW, received {decision.decision.value}: "
            f"{decision.reason}"
        )
    if not decision.evidence_refs:
        raise EvidenceDecisionNotAllow("ALLOW decision has no evidence references")
    return decision


def evidence_decision_event(
    decision: EvidenceDecision,
    *,
    event_id: Optional[str] = None,
) -> TrailEvent:
    decision_ref = evidence_decision_ref(decision)
    return TrailEvent(
        event_id=event_id or f"event-{decision_ref.split(':')[-1][:16]}",
        task_id=decision.task_id,
        trail_id=decision.trail_id,
        event_type=TrailEventType.EVIDENCE_DECISION,
        actor=decision.actor,
        created_at=decision.created_at,
        parent_cause=decision.parent_cause,
        evidence_refs=decision.evidence_refs,
        payload={
            **decision.to_dict(),
            "decision_ref": decision_ref,
        },
    )


def append_evidence_decision(
    trail: CognitiveTrail,
    decision: EvidenceDecision,
) -> CognitiveTrail:
    if trail.task_id != decision.task_id or trail.trail_id != decision.trail_id:
        raise EvidenceArtifactMismatchError(
            "evidence decision belongs to another task or trail"
        )
    event = evidence_decision_event(decision)
    return replace(trail, events=(*trail.events, event))


def attach_evidence_decision(
    artifact: ReusableArtifact,
    decision: EvidenceDecision,
) -> ReusableArtifact:
    if artifact.task_id != decision.task_id or artifact.trail_id != decision.trail_id:
        raise EvidenceArtifactMismatchError(
            "evidence decision belongs to another reusable artifact"
        )
    return replace(artifact, decision_ref=evidence_decision_ref(decision))
