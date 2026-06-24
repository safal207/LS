from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

from ..contracts import DecisionCode, EvidenceDecision
from ..evidence import (
    EvidenceArtifactMismatchError,
    EvidenceGateDisabledError,
    EvidenceGateRequest,
    EvidenceGateUnavailableError,
    MalformedEvidenceDecisionResponseError,
)


PythiaRunner = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class PythiaLabsConfig:
    enabled: bool = False
    actor: str = "adapter:pythia-labs"
    require_verified_artifact_for_allow: bool = True

    def __post_init__(self) -> None:
        if not self.actor:
            raise ValueError("PythiaLabs actor must not be empty")


class PythiaLabsEvidenceAdapter:
    """Normalize PythiaLabs decision artifacts into LS EvidenceDecision."""

    def __init__(
        self,
        config: Optional[PythiaLabsConfig] = None,
        runner: Optional[PythiaRunner] = None,
    ) -> None:
        self.config = config or PythiaLabsConfig()
        self._runner = runner

    @property
    def adapter_name(self) -> str:
        return "pythia-labs"

    def decide(self, request: Mapping[str, Any]) -> EvidenceDecision:
        gate_request = EvidenceGateRequest.from_mapping(request)
        if not self.config.enabled:
            raise EvidenceGateDisabledError(
                "PythiaLabs evidence adapter is disabled; enable it explicitly"
            )
        if self._runner is None:
            raise EvidenceGateUnavailableError(
                "PythiaLabs adapter requires an injected runner"
            )
        try:
            response = self._runner(gate_request.to_dict())
        except EvidenceGateUnavailableError:
            raise
        except Exception as error:
            raise EvidenceGateUnavailableError(
                "PythiaLabs runner failed"
            ) from error
        if not isinstance(response, Mapping):
            raise MalformedEvidenceDecisionResponseError(
                "PythiaLabs response must be an object"
            )
        return self._normalize(gate_request, response)

    def _normalize(
        self,
        request: EvidenceGateRequest,
        response: Mapping[str, Any],
    ) -> EvidenceDecision:
        raw_decision = response.get(
            "decision",
            response.get("final_decision", response.get("status", "")),
        )
        decision = _normalize_decision(raw_decision)
        reason = response.get("reason", response.get("stop_reason", ""))
        if not isinstance(reason, str) or not reason.strip():
            raise MalformedEvidenceDecisionResponseError(
                "PythiaLabs response requires reason or stop_reason"
            )

        response_policy = response.get("policy_version", request.policy_version)
        if response_policy != request.policy_version:
            raise EvidenceArtifactMismatchError(
                "PythiaLabs policy version does not match the LS request"
            )

        response_evidence = response.get("evidence_refs")
        if response_evidence is not None:
            if isinstance(response_evidence, (str, bytes)) or not isinstance(
                response_evidence,
                (list, tuple),
            ):
                raise MalformedEvidenceDecisionResponseError(
                    "PythiaLabs evidence_refs must be a sequence"
                )
            normalized_refs = tuple(str(value) for value in response_evidence)
            if normalized_refs != request.evidence_refs:
                raise EvidenceArtifactMismatchError(
                    "PythiaLabs evidence references do not match the LS request"
                )

        response_digest = response.get(
            "digest",
            response.get("artifact_digest", ""),
        )
        verification_status = response.get(
            "verification_status",
            response.get("self_verify", response.get("artifact_verified")),
        )
        verified = _normalize_verified(verification_status)

        if decision is DecisionCode.ALLOW:
            self._validate_allow(
                request,
                response_digest=response_digest,
                verified=verified,
            )

        response_task = response.get("task_id", request.task_id)
        response_trail = response.get("trail_id", request.trail_id)
        if response_task != request.task_id or response_trail != request.trail_id:
            raise EvidenceArtifactMismatchError(
                "PythiaLabs decision belongs to another task or trail"
            )

        return EvidenceDecision(
            task_id=request.task_id,
            trail_id=request.trail_id,
            decision=decision,
            reason=reason.strip(),
            policy_version=request.policy_version,
            actor=self.config.actor,
            created_at=request.created_at,
            evidence_refs=request.evidence_refs,
            parent_cause=request.causal_audit_ref,
        )

    def _validate_allow(
        self,
        request: EvidenceGateRequest,
        *,
        response_digest: Any,
        verified: bool,
    ) -> None:
        if not request.causal_authorization_allowed:
            raise EvidenceArtifactMismatchError(
                "PythiaLabs cannot ALLOW a causally blocked request"
            )
        if request.risk_flags:
            raise EvidenceArtifactMismatchError(
                "PythiaLabs cannot ALLOW a request with LS risk flags"
            )
        if request.missing_evidence_refs or not request.evidence_refs:
            raise EvidenceArtifactMismatchError(
                "PythiaLabs cannot ALLOW incomplete evidence"
            )
        if self.config.require_verified_artifact_for_allow:
            if not request.artifact_verified or not request.artifact_digest:
                raise EvidenceArtifactMismatchError(
                    "PythiaLabs ALLOW requires a verified LS evidence artifact"
                )
            if not verified:
                raise EvidenceArtifactMismatchError(
                    "PythiaLabs ALLOW response is not verified"
                )
            if not isinstance(response_digest, str) or (
                response_digest != request.artifact_digest
            ):
                raise EvidenceArtifactMismatchError(
                    "PythiaLabs digest does not match the LS evidence artifact"
                )


def _normalize_decision(value: Any) -> DecisionCode:
    normalized = str(value).strip().upper()
    aliases = {
        "ALLOW": DecisionCode.ALLOW,
        "ACCEPT": DecisionCode.ALLOW,
        "ACCEPTED": DecisionCode.ALLOW,
        "HOLD": DecisionCode.HOLD,
        "DEFER": DecisionCode.HOLD,
        "DEFERRED": DecisionCode.HOLD,
        "PENDING": DecisionCode.HOLD,
        "BLOCK": DecisionCode.BLOCK,
        "REJECT": DecisionCode.BLOCK,
        "REJECTED": DecisionCode.BLOCK,
        "ESCALATE": DecisionCode.ESCALATE,
        "ESCALATED": DecisionCode.ESCALATE,
        "HUMAN_REVIEW": DecisionCode.ESCALATE,
    }
    try:
        return aliases[normalized]
    except KeyError as error:
        raise MalformedEvidenceDecisionResponseError(
            f"unsupported PythiaLabs decision: {value!r}"
        ) from error


def _normalize_verified(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {
            "verified",
            "valid",
            "pass",
            "passed",
            "true",
        }
    return False
