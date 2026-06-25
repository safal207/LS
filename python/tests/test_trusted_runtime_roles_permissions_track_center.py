from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import ContinuityDecision, KnowledgeClass
from trusted_runtime.roles_permissions_track_center import (
    ROLES_PERMISSIONS_TRACK,
    AuthorityBasis,
    AuthorityStatus,
    RolePermissionEvent,
    RolePermissionEventType,
    process_role_permission_event,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/role_permission_result.schema.json"


def _event(
    event_type: RolePermissionEventType,
    status: AuthorityStatus,
    basis: AuthorityBasis,
    *,
    knowledge: KnowledgeClass = KnowledgeClass.FACT,
    evidence: tuple[str, ...] = ("evidence:authority:1",),
    provenance: tuple[str, ...] = ("provenance:policy:1",),
    contexts: tuple[str, ...] = ("context:production",),
    observers: tuple[str, ...] = ("observer:reviewer",),
    approvals: tuple[str, ...] = (),
    repeat_count: int = 1,
    candidate: bool = False,
) -> RolePermissionEvent:
    return RolePermissionEvent(
        event_id="authority-event:1",
        authority_id="authority:deploy-production",
        subject_id="agent:release-bot",
        event_type=event_type,
        authority_status=status,
        authority_basis=basis,
        action="deploy",
        resource="service:payments",
        scope_ref="scope:production",
        knowledge_class=knowledge,
        statement="A bounded role or permission observation.",
        occurred_at="2026-06-25T11:00:00Z",
        confidence=0.94,
        repeat_count=repeat_count,
        evidence_refs=evidence,
        provenance_refs=provenance,
        context_refs=contexts,
        observer_refs=observers,
        role_refs=("role:release-operator",),
        approval_refs=approvals,
        identity_candidate_statement=(
            "Escalate when authority scope is incomplete." if candidate else None
        ),
        identity_scope=ROLES_PERMISSIONS_TRACK if candidate else None,
        identity_repeat_key="authority:escalate-incomplete-scope" if candidate else None,
    )


def _process(event: RolePermissionEvent):
    return process_role_permission_event(
        event,
        processed_at="2026-06-25T11:01:00Z",
    )


def test_role_observation_and_assignment_do_not_authorize_action() -> None:
    observed = _process(
        _event(
            RolePermissionEventType.ROLE_OBSERVED,
            AuthorityStatus.OBSERVED,
            AuthorityBasis.NONE,
            knowledge=KnowledgeClass.INFERENCE,
        )
    )
    assigned = _process(
        _event(
            RolePermissionEventType.ROLE_ASSIGNED,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.ROLE_ASSIGNMENT,
        )
    )
    for result in (observed, assigned):
        assert result.observation.claims_current_presence is False
        assert result.assessment.lesson_candidate is None
        assert result.to_dict()["access_grant_allowed"] is False
        assert result.to_dict()["execution_authorized"] is False


def test_source_backed_authority_events_require_fact_evidence_and_provenance() -> None:
    accepted = _process(
        _event(
            RolePermissionEventType.PERMISSION_GRANTED,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
        )
    )
    assert accepted.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION

    with pytest.raises(ValueError, match="FACT"):
        _event(
            RolePermissionEventType.PERMISSION_GRANTED,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
            knowledge=KnowledgeClass.INFERENCE,
        )
    with pytest.raises(ValueError, match="evidence and provenance"):
        _event(
            RolePermissionEventType.PERMISSION_GRANTED,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
            evidence=(),
        )
    with pytest.raises(ValueError, match="evidence and provenance"):
        _event(
            RolePermissionEventType.PERMISSION_GRANTED,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
            provenance=(),
        )


def test_role_membership_is_not_current_authority() -> None:
    result = _process(
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.ROLE_ASSIGNMENT,
        )
    )
    assert result.observation.claims_current_presence is True
    assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW


def test_valid_current_authority_requires_authorizing_basis_and_provenance() -> None:
    result = _process(
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
        )
    )
    assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    assert result.assessment.lesson_candidate is None
    assert result.to_dict()["access_grant_allowed"] is False


def test_unverified_or_context_missing_current_authority_is_held() -> None:
    cases = (
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
            evidence=(),
        ),
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
            provenance=(),
        ),
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
            contexts=(),
        ),
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.DISPUTED,
            AuthorityBasis.DIRECT_PERMISSION,
        ),
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.PENDING_APPROVAL,
            AuthorityBasis.APPROVAL,
        ),
    )
    for event in cases:
        assert _process(event).assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW


def test_approval_basis_requires_verified_approval_reference() -> None:
    held = _process(
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.APPROVAL,
        )
    )
    accepted = _process(
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.APPROVAL,
            approvals=("approval:change-board:42",),
        )
    )
    assert held.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW
    assert accepted.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION


@pytest.mark.parametrize(
    "status",
    [
        AuthorityStatus.DENIED,
        AuthorityStatus.REVOKED,
        AuthorityStatus.EXPIRED,
        AuthorityStatus.RETIRED,
    ],
)
def test_closed_authority_blocks_current_claim(status: AuthorityStatus) -> None:
    result = _process(
        _event(
            RolePermissionEventType.CURRENT_AUTHORITY_CLAIM,
            status,
            AuthorityBasis.DIRECT_PERMISSION,
        )
    )
    assert result.assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert result.to_dict()["permission_registry_mutation_allowed"] is False


@pytest.mark.parametrize(
    ("event_type", "status", "basis"),
    [
        (
            RolePermissionEventType.AUTHORIZATION_PATTERN_VERIFIED,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
        ),
        (
            RolePermissionEventType.ESCALATION_PATTERN_VERIFIED,
            AuthorityStatus.PENDING_APPROVAL,
            AuthorityBasis.APPROVAL,
        ),
    ],
)
def test_repeated_patterns_emit_only_bounded_lessons(
    event_type: RolePermissionEventType,
    status: AuthorityStatus,
    basis: AuthorityBasis,
) -> None:
    result = _process(
        _event(
            event_type,
            status,
            basis,
            evidence=("evidence:1", "evidence:2"),
            provenance=("provenance:1", "provenance:2"),
            contexts=("context:staging", "context:production"),
            observers=("observer:security", "observer:release"),
            repeat_count=2,
            candidate=True,
        )
    )
    assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    assert result.assessment.lesson_candidate is not None
    assert result.to_dict()["stable_identity_update_allowed"] is False
    assert result.to_dict()["approval_allowed"] is False


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"repeat_count": 1}, "repeated evidence"),
        ({"evidence": ("e1",)}, "two evidence and provenance"),
        ({"provenance": ("p1",)}, "two evidence and provenance"),
        ({"contexts": ("c1",)}, "cross-context independent"),
        ({"observers": ("o1",)}, "cross-context independent"),
    ],
)
def test_lesson_candidate_requires_independent_repetition(
    overrides: dict[str, object],
    match: str,
) -> None:
    kwargs = {
        "evidence": ("e1", "e2"),
        "provenance": ("p1", "p2"),
        "contexts": ("c1", "c2"),
        "observers": ("o1", "o2"),
        "repeat_count": 2,
        "candidate": True,
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError, match=match):
        _event(
            RolePermissionEventType.AUTHORIZATION_PATTERN_VERIFIED,
            AuthorityStatus.ACTIVE,
            AuthorityBasis.DIRECT_PERMISSION,
            **kwargs,
        )


def test_result_is_deterministic_schema_valid_and_non_authoritative() -> None:
    event = _event(
        RolePermissionEventType.AUTHORIZATION_PATTERN_VERIFIED,
        AuthorityStatus.ACTIVE,
        AuthorityBasis.DIRECT_PERMISSION,
        evidence=("e1", "e2"),
        provenance=("p1", "p2"),
        contexts=("c1", "c2"),
        observers=("o1", "o2"),
        repeat_count=2,
        candidate=True,
    )
    first = _process(event)
    second = _process(event)
    assert first.result_id == second.result_id
    payload = first.to_dict()
    denied = (
        "role_registry_mutation_allowed",
        "permission_registry_mutation_allowed",
        "access_grant_allowed",
        "access_denial_allowed",
        "approval_allowed",
        "delegation_allowed",
        "policy_mutation_allowed",
        "work_scheduling_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    )
    assert all(payload[field] is False for field in denied)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
