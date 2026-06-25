from __future__ import annotations

import pytest

from trusted_runtime.authorization_contract import (
    ApprovalEvidence,
    ApprovalState,
    AuthorizationDecision,
    AuthorizationRequest,
    ContextState,
    ExecutionContextEvidence,
    PolicyEffect,
    PolicyEvidence,
)
from trusted_runtime.authorization_decision_gate import evaluate_authorization
from trusted_runtime.authorization_evidence_adapters import (
    authority_evidence_from_result,
    capability_evidence_from_result,
)
from trusted_runtime.capabilities_constraints_track_center import (
    CapabilityConstraintEvent,
    CapabilityEventType,
    CapabilityStatus,
    process_capability_event,
)
from trusted_runtime.capability_contract import ConstraintKind
from trusted_runtime.continuity_coordinator import KnowledgeClass
from trusted_runtime.roles_permissions_track_center import (
    AuthorityBasis,
    AuthorityStatus,
    RolePermissionEvent,
    RolePermissionEventType,
    process_role_permission_event,
)

SUBJECT = "agent:release-bot"
ACTION = "deploy"
RESOURCE = "service:payments"
SCOPE = "scope:production"
CAPABILITY = "capability:deploy-service"


def _capability_result():
    event = CapabilityConstraintEvent(
        event_id="capability-event:authz",
        capability_id=CAPABILITY,
        event_type=CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
        capability_status=CapabilityStatus.AVAILABLE,
        constraint_kind=ConstraintKind.NONE,
        knowledge_class=KnowledgeClass.FACT,
        statement="Deployment capability is currently available.",
        occurred_at="2026-06-25T12:10:00Z",
        confidence=0.95,
        repeat_count=1,
        evidence_refs=("evidence:capability:test",),
        context_refs=("context:production",),
        observer_refs=("observer:qa",),
    )
    return process_capability_event(
        event,
        processed_at="2026-06-25T12:10:01Z",
    )


def _authority_result():
    event = RolePermissionEvent(
        event_id="authority-event:authz",
        authority_id="authority:deploy-production",
        subject_id=SUBJECT,
        event_type=RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
        authority_status=AuthorityStatus.ACTIVE,
        authority_basis=AuthorityBasis.DIRECT_PERMISSION,
        action=ACTION,
        resource=RESOURCE,
        scope_ref=SCOPE,
        knowledge_class=KnowledgeClass.FACT,
        statement="Release bot has a scoped deployment permission.",
        occurred_at="2026-06-25T12:10:00Z",
        confidence=0.96,
        repeat_count=1,
        evidence_refs=("evidence:permission:test",),
        provenance_refs=("provenance:policy:test",),
        context_refs=("context:production",),
        observer_refs=("observer:security",),
        role_refs=("role:release-operator",),
    )
    return process_role_permission_event(
        event,
        processed_at="2026-06-25T12:10:01Z",
    )


def test_track_results_adapt_into_allow_decision() -> None:
    capability = capability_evidence_from_result(
        _capability_result(),
        subject_id=SUBJECT,
        subject_binding_ref="binding:agent-capability:test",
    )
    authority = authority_evidence_from_result(_authority_result())
    request = AuthorizationRequest(
        request_id="authorization-request:adapter",
        subject_id=SUBJECT,
        intent_ref="intent:release:adapter",
        action=ACTION,
        resource=RESOURCE,
        scope_ref=SCOPE,
        required_capability_id=CAPABILITY,
        capability_subject_binding_ref="binding:agent-capability:test",
        capability=capability,
        authority=authority,
        policy=PolicyEvidence(
            policy_id="policy:deploy",
            policy_version="v1",
            effect=PolicyEffect.ALLOW,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            evidence_refs=("evidence:policy:test",),
            policy_digest="c" * 64,
        ),
        approval=ApprovalEvidence(
            approval_id="approval:not-required",
            subject_id=SUBJECT,
            state=ApprovalState.NOT_REQUIRED,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            approver_refs=(),
            evidence_refs=(),
            approval_digest="d" * 64,
        ),
        context=ExecutionContextEvidence(
            context_id="context:adapter",
            subject_id=SUBJECT,
            state=ContextState.FRESH,
            action=ACTION,
            resource=RESOURCE,
            scope_ref=SCOPE,
            age_seconds=5,
            max_age_seconds=30,
            evidence_refs=("evidence:context:test",),
            context_digest="e" * 64,
        ),
        requested_at="2026-06-25T12:10:02Z",
    )
    result = evaluate_authorization(
        request,
        evaluated_at="2026-06-25T12:10:03Z",
    )
    assert result.decision is AuthorizationDecision.ALLOW
    assert result.action_authorized is True
    assert result.to_dict()["execution_authorized"] is False


def test_capability_adapter_requires_separate_subject_binding() -> None:
    with pytest.raises(ValueError, match="subject_binding_ref"):
        capability_evidence_from_result(
            _capability_result(),
            subject_id=SUBJECT,
            subject_binding_ref="",
        )
