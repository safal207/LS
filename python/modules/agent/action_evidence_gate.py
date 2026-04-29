# -*- coding: utf-8 -*-
"""Deterministic evidence gate for state-changing agent actions.

The gate is intentionally LS-native and lightweight: it does not execute an
action. It produces a replayable decision, trace, and digest that integrations
can use before persisting memory/profile writes or letting an external agent act.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value or {}) if isinstance(value, dict) else {}


def _as_text(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "confirmed", "allow", "allowed"}
    return bool(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ActionEvidenceTraceStep:
    check: str
    status: str
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionEvidenceGateResult:
    action_type: str
    decision: str
    stop_reason: str
    trace: list[dict[str, Any]]
    required_evidence: list[str] = field(default_factory=list)
    evidence_artifact: dict[str, Any] = field(default_factory=dict)
    evidence_digest: str = ""
    source: str = "ls.action_evidence_gate.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionEvidenceGateRequest:
    action_type: str
    actor: str
    target: str = ""
    requested_change: Any = None
    evidence: dict[str, Any] = field(default_factory=dict)
    current_context: dict[str, Any] = field(default_factory=dict)


class ActionEvidenceGate:
    """Evaluate evidence before a state-changing agent action is trusted."""

    HIGH_RISK_ACTIONS = {
        "database_drop",
        "deployment_rollback",
        "external_agent_action",
        "file_write",
        "production_action",
        "production_config_change",
        "repo_push",
        "secret_rotate",
        "tool_call",
        "volume_delete",
    }
    MEMORY_WRITE_SCOPES = {"session_memory", "long_term_memory", "memory_write"}
    PROFILE_WRITE_SCOPES = {"operator_profile", "profile_write", "operator_profile_update"}

    def evaluate(
        self,
        request: ActionEvidenceGateRequest | dict[str, Any],
    ) -> ActionEvidenceGateResult:
        req = self._coerce_request(request)
        trace: list[ActionEvidenceTraceStep] = []
        required: list[str] = []

        if not req.action_type:
            return self._finish(
                req,
                decision="reject",
                stop_reason="invalid_action",
                trace=[
                    ActionEvidenceTraceStep(
                        "checked_action_shape",
                        "failed",
                        "action_type is required",
                    )
                ],
                required_evidence=["action_type"],
            )

        trace.append(
            ActionEvidenceTraceStep(
                "checked_action_shape",
                "passed",
                evidence={
                    "action_type": req.action_type,
                    "actor": req.actor,
                    "target": req.target,
                },
            )
        )

        temporal_decision = self._evaluate_bitemporal_authorization(req, trace, required)
        if temporal_decision:
            return self._finish(req, **temporal_decision, trace=trace, required_evidence=required)

        action_type = req.action_type
        if action_type == "agent_output":
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_state_change_request",
                    "passed",
                    "no state-changing action requested",
                )
            )
            return self._finish(
                req,
                decision="allow",
                stop_reason="constraints_satisfied",
                trace=trace,
                required_evidence=required,
            )

        if action_type in self.PROFILE_WRITE_SCOPES:
            return self._evaluate_profile_write(req, trace, required)
        if action_type in self.MEMORY_WRITE_SCOPES:
            return self._evaluate_memory_write(req, trace, required)
        return self._evaluate_external_action(req, trace, required)

    def verify_evidence_artifact(self, artifact: dict[str, Any]) -> ActionEvidenceGateResult:
        payload = dict(artifact or {})
        expected = str(payload.get("evidence_digest") or payload.get("digest") or "")
        payload.pop("evidence_digest", None)
        payload.pop("digest", None)
        actual = _sha256(payload)
        request = ActionEvidenceGateRequest(
            action_type=str(payload.get("action_type") or "evidence_artifact"),
            actor=str(_as_dict(payload.get("request")).get("actor") or "verifier"),
            target=str(_as_dict(payload.get("request")).get("target") or ""),
            requested_change=_as_dict(payload.get("request")).get("requested_change"),
            evidence={"expected_digest": expected, "actual_digest": actual},
        )
        if expected and expected == actual:
            return self._finish(
                request,
                decision="allow",
                stop_reason="constraints_satisfied",
                trace=[
                    ActionEvidenceTraceStep(
                        "verified_evidence_digest",
                        "passed",
                        evidence={"digest": actual},
                    )
                ],
            )
        return self._finish(
            request,
            decision="reject",
            stop_reason="tampered_evidence",
            trace=[
                ActionEvidenceTraceStep(
                    "verified_evidence_digest",
                    "failed",
                    "artifact digest does not match canonical payload",
                    evidence={"expected_digest": expected, "actual_digest": actual},
                )
            ],
            required_evidence=["matching_evidence_digest"],
        )

    def _evaluate_profile_write(
        self,
        req: ActionEvidenceGateRequest,
        trace: list[ActionEvidenceTraceStep],
        required: list[str],
    ) -> ActionEvidenceGateResult:
        evidence = req.evidence
        write_decision = _as_dict(evidence.get("operator_profile_write_decision"))
        policy_decision = str(write_decision.get("decision") or "").strip()

        if policy_decision == "reject_identity_claim":
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_identity_write_policy",
                    "failed",
                    "profile write conflicts with operator identity boundary",
                    evidence=write_decision,
                )
            )
            return self._finish(
                req,
                decision="reject",
                stop_reason="unsafe_profile_write",
                trace=trace,
                required_evidence=required,
            )

        if policy_decision in {"hold_for_identity_review", "requires_continuity_review"}:
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_identity_continuity",
                    "failed",
                    "profile write needs continuity review",
                    evidence=write_decision,
                )
            )
            required.append("continuity_review")
            return self._finish(
                req,
                decision="hold",
                stop_reason="identity_conflict",
                trace=trace,
                required_evidence=required,
            )

        if not self._operator_confirmed(evidence):
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_operator_confirmation",
                    "failed",
                    "profile write requires explicit operator confirmation",
                )
            )
            required.append("operator_confirmation")
            return self._finish(
                req,
                decision="hold",
                stop_reason="missing_operator_confirmation",
                trace=trace,
                required_evidence=required,
            )

        trace.append(
            ActionEvidenceTraceStep(
                "checked_operator_confirmation",
                "passed",
                evidence={"operator_confirmed": True},
            )
        )
        return self._finish(
            req,
            decision="allow",
            stop_reason="constraints_satisfied",
            trace=trace,
            required_evidence=required,
        )

    def _evaluate_memory_write(
        self,
        req: ActionEvidenceGateRequest,
        trace: list[ActionEvidenceTraceStep],
        required: list[str],
    ) -> ActionEvidenceGateResult:
        evidence = req.evidence
        write_decision = _as_dict(evidence.get("operator_profile_write_decision"))
        policy_decision = str(write_decision.get("decision") or "").strip()

        if policy_decision == "reject_identity_claim":
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_memory_write_policy",
                    "failed",
                    "memory write conflicts with operator identity boundary",
                    evidence=write_decision,
                )
            )
            return self._finish(
                req,
                decision="reject",
                stop_reason="unsafe_memory_write",
                trace=trace,
                required_evidence=required,
            )

        if not self._has_source_evidence(evidence):
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_source_evidence",
                    "failed",
                    "memory write needs a source before persistence",
                )
            )
            required.append("source_evidence")
            return self._finish(
                req,
                decision="hold",
                stop_reason="missing_source_evidence",
                trace=trace,
                required_evidence=required,
            )

        trace.append(
            ActionEvidenceTraceStep(
                "checked_source_evidence",
                "passed",
                evidence={"source_evidence_present": True},
            )
        )
        needs_confirmation = (
            str(req.action_type) == "long_term_memory"
            or policy_decision == "requires_operator_confirmation"
            or bool(write_decision.get("requires_operator_confirmation"))
        )
        if needs_confirmation and not self._operator_confirmed(evidence):
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_operator_confirmation",
                    "failed",
                    "long-term memory write requires explicit operator confirmation",
                )
            )
            required.append("operator_confirmation")
            return self._finish(
                req,
                decision="hold",
                stop_reason="missing_operator_confirmation",
                trace=trace,
                required_evidence=required,
            )

        trace.append(ActionEvidenceTraceStep("checked_memory_write_scope", "passed"))
        return self._finish(
            req,
            decision="allow",
            stop_reason="constraints_satisfied",
            trace=trace,
            required_evidence=required,
        )

    def _evaluate_external_action(
        self,
        req: ActionEvidenceGateRequest,
        trace: list[ActionEvidenceTraceStep],
        required: list[str],
    ) -> ActionEvidenceGateResult:
        evidence = req.evidence
        high_risk = self._is_high_risk(req)
        trace.append(
            ActionEvidenceTraceStep(
                "checked_action_risk",
                "passed",
                evidence={"high_risk": high_risk},
            )
        )
        if not high_risk:
            return self._finish(
                req,
                decision="allow",
                stop_reason="constraints_satisfied",
                trace=trace,
                required_evidence=required,
            )

        if not self._operator_confirmed(evidence):
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_operator_confirmation",
                    "failed",
                    "high-risk external action requires operator confirmation",
                )
            )
            required.append("operator_confirmation")
            return self._finish(
                req,
                decision="hold",
                stop_reason="missing_operator_confirmation",
                trace=trace,
                required_evidence=required,
            )

        if not self._scope_authorized(evidence):
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_scope_authorization",
                    "failed",
                    "external action is outside authorized scope",
                )
            )
            required.append("scope_authorization")
            return self._finish(
                req,
                decision="reject",
                stop_reason="external_agent_scope_violation",
                trace=trace,
                required_evidence=required,
            )

        trace.append(
            ActionEvidenceTraceStep(
                "checked_scope_authorization",
                "passed",
                evidence={"scope_authorized": True},
            )
        )
        return self._finish(
            req,
            decision="allow",
            stop_reason="constraints_satisfied",
            trace=trace,
            required_evidence=required,
        )

    def _evaluate_bitemporal_authorization(
        self,
        req: ActionEvidenceGateRequest,
        trace: list[ActionEvidenceTraceStep],
        required: list[str],
    ) -> dict[str, str] | None:
        record = _as_dict(req.evidence.get("permission_record"))
        if not record:
            trace.append(ActionEvidenceTraceStep("checked_bitemporal_authorization", "skipped"))
            return None

        action_time = _parse_time(req.current_context.get("action_time"))
        decision_time = _parse_time(req.current_context.get("decision_time"))
        valid_from = _parse_time(record.get("valid_from"))
        valid_to = _parse_time(record.get("valid_to"))
        recorded_at = _parse_time(record.get("recorded_at"))

        if not action_time or not decision_time or not valid_from or not recorded_at:
            trace.append(
                ActionEvidenceTraceStep(
                    "checked_bitemporal_authorization",
                    "failed",
                    "permission record is missing parseable action, decision, valid_from, or recorded_at time",
                    evidence=record,
                )
            )
            required.append("valid_permission_record")
            return {"decision": "reject", "stop_reason": "invalid_temporal_record"}

        if action_time < valid_from:
            trace.append(ActionEvidenceTraceStep("checked_bitemporal_authorization", "failed", evidence=record))
            return {"decision": "hold", "stop_reason": "authorization_not_yet_valid"}
        if valid_to and action_time > valid_to:
            trace.append(ActionEvidenceTraceStep("checked_bitemporal_authorization", "failed", evidence=record))
            return {"decision": "hold", "stop_reason": "stale_authorization"}
        if recorded_at > decision_time:
            trace.append(ActionEvidenceTraceStep("checked_bitemporal_authorization", "failed", evidence=record))
            return {"decision": "hold", "stop_reason": "authorization_unknown_at_decision_time"}

        trace.append(ActionEvidenceTraceStep("checked_bitemporal_authorization", "passed", evidence=record))
        return None

    @staticmethod
    def _coerce_request(request: ActionEvidenceGateRequest | dict[str, Any]) -> ActionEvidenceGateRequest:
        if isinstance(request, ActionEvidenceGateRequest):
            return request
        data = dict(request or {})
        return ActionEvidenceGateRequest(
            action_type=str(data.get("action_type") or ""),
            actor=str(data.get("actor") or ""),
            target=str(data.get("target") or ""),
            requested_change=data.get("requested_change"),
            evidence=_as_dict(data.get("evidence")),
            current_context=_as_dict(data.get("current_context")),
        )

    @staticmethod
    def _operator_confirmed(evidence: dict[str, Any]) -> bool:
        return any(
            _truthy(evidence.get(key))
            for key in (
                "operator_confirmation",
                "operator_confirmed",
                "confirmed_by_operator",
                "explicit_operator_approval",
            )
        )

    @staticmethod
    def _scope_authorized(evidence: dict[str, Any]) -> bool:
        return any(
            _truthy(evidence.get(key))
            for key in (
                "scope_authorized",
                "scope_ok",
                "authorized_scope",
                "credential_scope_ok",
            )
        )

    @staticmethod
    def _has_source_evidence(evidence: dict[str, Any]) -> bool:
        return any(
            bool(evidence.get(key))
            for key in (
                "source",
                "source_evidence",
                "source_text",
                "source_message_id",
                "conversation_excerpt",
            )
        )

    def _is_high_risk(self, req: ActionEvidenceGateRequest) -> bool:
        evidence = req.evidence
        action_type = str(req.action_type or "").strip().lower()
        target = str(req.target or "").strip().lower()
        requested_change = _canonical_json(req.requested_change).lower()
        explicit_risk = str(evidence.get("risk_level") or evidence.get("risk") or "").strip().lower()
        if explicit_risk in {"high", "critical", "destructive"}:
            return True
        if _truthy(evidence.get("destructive")) or _truthy(evidence.get("production")):
            return True
        if action_type in self.HIGH_RISK_ACTIONS:
            return True
        return any(term in f"{target} {requested_change}" for term in ("production", "delete", "drop", "secret"))

    def _finish(
        self,
        req: ActionEvidenceGateRequest,
        *,
        decision: str,
        stop_reason: str,
        trace: list[ActionEvidenceTraceStep],
        required_evidence: list[str] | None = None,
    ) -> ActionEvidenceGateResult:
        trace_dicts = [step.to_dict() for step in trace]
        artifact = {
            "action_type": req.action_type,
            "decision": decision,
            "stop_reason": stop_reason,
            "request": {
                "actor": req.actor,
                "target": req.target,
                "requested_change": req.requested_change,
            },
            "required_evidence": list(dict.fromkeys(required_evidence or [])),
            "trace": trace_dicts,
            "source": "ls.action_evidence_gate.v1",
        }
        digest = _sha256(artifact)
        artifact["evidence_digest"] = digest
        return ActionEvidenceGateResult(
            action_type=req.action_type,
            decision=decision,
            stop_reason=stop_reason,
            trace=trace_dicts,
            required_evidence=list(dict.fromkeys(required_evidence or [])),
            evidence_artifact=artifact,
            evidence_digest=digest,
        )


action_evidence_gate = ActionEvidenceGate()
