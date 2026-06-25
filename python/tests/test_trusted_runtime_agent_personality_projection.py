from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.agent_personality_projection import (
    ProjectionScope,
    ProjectionScopeLevel,
    ProjectionValidity,
    project_agent_personality,
    render_personality_projection_markdown,
    validate_personality_projection,
)
from trusted_runtime.capabilities_constraints_track_center import (
    process_capability_event,
)
from trusted_runtime.capability_contract import (
    CapabilityConstraintEvent,
    CapabilityEventType,
    CapabilityStatus,
    ConstraintKind,
)
from trusted_runtime.continuity_coordinator import KnowledgeClass
from trusted_runtime.identity_governance import IdentityProfile


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = (
    ROOT
    / "schemas/trusted_runtime/agent_personality_projection.schema.json"
)
CREATED_AT = "2026-06-25T10:00:00Z"


def _profile(
    *,
    version: int = 2,
    active: bool = True,
    source_application_ref: str | None = "identity-application:approved:2",
    traits: dict | None = None,
) -> IdentityProfile:
    return IdentityProfile(
        profile_id=f"identity-profile-record:{version}",
        agent_id="agent:qa-01",
        version=version,
        traits=traits
        if traits is not None
        else {
            "communication_style.directness": {
                "value": "high",
                "confidence": 0.94,
                "source_refs": ["identity-influence:directness:v2"],
            },
            "working_tendencies.test_before_claim": {
                "value": True,
                "confidence": 0.98,
                "source_refs": ["identity-influence:evidence-first:v3"],
            },
        },
        created_at="2026-06-25T09:00:00Z",
        previous_profile_ref=(
            None
            if version == 1
            else "identity-profile:sha256:" + "a" * 64
        ),
        source_application_ref=source_application_ref,
        active=active,
        metadata={
            "source_refs": [
                f"identity-approval:{version}",
                f"identity-patch:{version}",
            ]
        },
    )


def _capability_result(
    *,
    event_id: str,
    event_type: CapabilityEventType,
    status: CapabilityStatus,
    constraint: ConstraintKind,
    statement: str,
    context_refs: tuple[str, ...] = ("project:ls",),
):
    event = CapabilityConstraintEvent(
        event_id=event_id,
        capability_id="capability:python-review",
        event_type=event_type,
        capability_status=status,
        constraint_kind=constraint,
        knowledge_class=KnowledgeClass.FACT,
        statement=statement,
        occurred_at="2026-06-25T09:30:00Z",
        confidence=0.93,
        repeat_count=1,
        evidence_refs=(f"evidence:{event_id}",),
        context_refs=context_refs,
        observer_refs=("observer:qa",),
    )
    return process_capability_event(
        event,
        processed_at="2026-06-25T09:31:00Z",
    )


def test_projection_requires_active_governed_identity_profile() -> None:
    with pytest.raises(ValueError, match="inactive identity profile"):
        project_agent_personality(
            _profile(active=False),
            scope=ProjectionScope(ProjectionScopeLevel.INDIVIDUAL),
            created_at=CREATED_AT,
        )

    ungoverned = _profile(
        version=1,
        source_application_ref=None,
    )
    with pytest.raises(ValueError, match="governed application"):
        project_agent_personality(
            ungoverned,
            scope=ProjectionScope(ProjectionScopeLevel.INDIVIDUAL),
            created_at=CREATED_AT,
        )


def test_approved_baseline_profile_is_supported_explicitly() -> None:
    baseline = IdentityProfile(
        profile_id="identity-profile-record:1",
        agent_id="agent:qa-01",
        version=1,
        traits={"working_tendencies.test_before_claim": True},
        created_at="2026-06-25T09:00:00Z",
        previous_profile_ref=None,
        source_application_ref=None,
        active=True,
        metadata={
            "governance_status": "APPROVED_BASELINE",
            "source_refs": ["baseline-approval:1"],
        },
    )
    projection = project_agent_personality(
        baseline,
        scope=ProjectionScope(ProjectionScopeLevel.INDIVIDUAL),
        created_at=CREATED_AT,
    )
    assert projection.working_tendencies[0].value is True
    assert "baseline-approval:1" in projection.source_refs


def test_projection_is_deterministic_provenance_bound_and_schema_valid() -> None:
    scope = ProjectionScope(ProjectionScopeLevel.INDIVIDUAL)
    first = project_agent_personality(
        _profile(),
        scope=scope,
        created_at=CREATED_AT,
    )
    second = project_agent_personality(
        _profile(),
        scope=scope,
        created_at=CREATED_AT,
    )

    assert first.projection_id == second.projection_id
    assert first.projection_digest == second.projection_digest
    assert len(first.communication_style) == 1
    assert len(first.working_tendencies) == 1
    assert first.identity_profile_ref in first.source_refs
    assert all(item.source_refs for item in first.all_items)

    payload = first.to_dict()
    assert all(value is False for value in payload["authority_effects"].values())
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []


def test_relationship_rule_is_only_projected_for_matching_counterparty() -> None:
    traits = {
        "relationship_rules.delegation_style": {
            "value": "proposal_before_action",
            "source_refs": ["identity-influence:alex-delegation:v1"],
            "scope": {
                "level": "relationship",
                "counterparty_ref": "human:alex",
            },
        }
    }
    matching = project_agent_personality(
        _profile(traits=traits),
        scope=ProjectionScope(
            ProjectionScopeLevel.RELATIONSHIP,
            counterparty_ref="human:alex",
        ),
        created_at=CREATED_AT,
    )
    other = project_agent_personality(
        _profile(traits=traits),
        scope=ProjectionScope(
            ProjectionScopeLevel.RELATIONSHIP,
            counterparty_ref="human:other",
        ),
        created_at=CREATED_AT,
    )

    assert len(matching.relationship_rules) == 1
    assert matching.relationship_rules[0].value == "proposal_before_action"
    assert other.relationship_rules == ()
    assert any("scope_mismatch" in ref for ref in other.excluded_or_disputed_refs)


def test_disputed_expired_and_unsupported_traits_are_excluded() -> None:
    traits = {
        "communication_style.disputed": {
            "value": "high",
            "disputed": True,
            "source_refs": ["trait:disputed"],
        },
        "working_tendencies.expired": {
            "value": True,
            "expires_at": "2026-06-25T09:59:59Z",
            "source_refs": ["trait:expired"],
        },
        "untrusted.free_form": "must not project",
    }
    projection = project_agent_personality(
        _profile(traits=traits),
        scope=ProjectionScope(ProjectionScopeLevel.INDIVIDUAL),
        created_at=CREATED_AT,
    )

    assert projection.all_items == ()
    excluded = "\n".join(projection.excluded_or_disputed_refs)
    assert "disputed_or_conflicting" in excluded
    assert "expired" in excluded
    assert "unsupported_namespace" in excluded


def test_accepted_current_capability_and_constraint_preserve_context() -> None:
    capability = _capability_result(
        event_id="current-capability",
        event_type=CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
        status=CapabilityStatus.AVAILABLE,
        constraint=ConstraintKind.NONE,
        statement="Python review is available in the LS project context.",
    )
    limitation = _capability_result(
        event_id="current-limitation",
        event_type=CapabilityEventType.CURRENT_LIMITATION_CLAIM,
        status=CapabilityStatus.CONSTRAINED,
        constraint=ConstraintKind.TEMPORARY,
        statement="Python review is temporarily constrained in this project.",
    )
    projection = project_agent_personality(
        _profile(),
        scope=ProjectionScope(
            ProjectionScopeLevel.PROJECT,
            project_ref="project:ls",
        ),
        created_at=CREATED_AT,
        capability_results=(capability, limitation),
    )

    assert len(projection.capability_claims) == 1
    assert projection.capability_claims[0].status == "AVAILABLE"
    assert projection.capability_claims[0].context_refs == ("project:ls",)
    assert len(projection.active_constraints) == 1
    assert projection.active_constraints[0].status == "CONSTRAINED"
    assert projection.active_constraints[0].metadata["constraint_kind"] == "TEMPORARY"


def test_held_disputed_capability_is_not_projected_as_current() -> None:
    disputed = _capability_result(
        event_id="disputed-capability",
        event_type=CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
        status=CapabilityStatus.DISPUTED,
        constraint=ConstraintKind.UNKNOWN,
        statement="Python review availability is disputed.",
    )
    projection = project_agent_personality(
        _profile(),
        scope=ProjectionScope(
            ProjectionScopeLevel.PROJECT,
            project_ref="project:ls",
        ),
        created_at=CREATED_AT,
        capability_results=(disputed,),
    )

    assert projection.capability_claims == ()
    assert any("not_accepted" in ref for ref in projection.excluded_or_disputed_refs)


def test_capability_context_cannot_inflate_to_another_project_or_system() -> None:
    capability = _capability_result(
        event_id="context-bound-capability",
        event_type=CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
        status=CapabilityStatus.AVAILABLE,
        constraint=ConstraintKind.NONE,
        statement="Capability is verified only for project LS.",
    )
    other_project = project_agent_personality(
        _profile(),
        scope=ProjectionScope(
            ProjectionScopeLevel.PROJECT,
            project_ref="project:other",
        ),
        created_at=CREATED_AT,
        capability_results=(capability,),
    )
    system = project_agent_personality(
        _profile(),
        scope=ProjectionScope(ProjectionScopeLevel.SYSTEM),
        created_at=CREATED_AT,
        capability_results=(capability,),
    )

    assert other_project.capability_claims == ()
    assert system.capability_claims == ()
    assert any("context_mismatch" in ref for ref in other_project.excluded_or_disputed_refs)


def test_projection_becomes_stale_revoked_or_expired_without_mutation() -> None:
    profile = _profile()
    projection = project_agent_personality(
        profile,
        scope=ProjectionScope(ProjectionScopeLevel.INDIVIDUAL),
        created_at=CREATED_AT,
        expires_at="2026-06-26T10:00:00Z",
    )
    current = validate_personality_projection(
        projection,
        active_profile=profile,
        evaluated_at="2026-06-25T11:00:00Z",
    )
    assert current.validity is ProjectionValidity.ACTIVE

    next_profile = IdentityProfile(
        profile_id="identity-profile-record:3",
        agent_id=profile.agent_id,
        version=3,
        traits=profile.traits,
        created_at="2026-06-25T12:00:00Z",
        previous_profile_ref=profile.profile_ref,
        source_application_ref="identity-application:approved:3",
        active=True,
        metadata={"source_refs": ["identity-approval:3"]},
    )
    stale = validate_personality_projection(
        projection,
        active_profile=next_profile,
        evaluated_at="2026-06-25T12:01:00Z",
    )
    assert stale.validity is ProjectionValidity.STALE
    assert "IDENTITY_PROFILE_SUPERSEDED_OR_ROLLED_BACK" in stale.reason_codes

    revoked = validate_personality_projection(
        projection,
        active_profile=profile,
        evaluated_at="2026-06-25T12:01:00Z",
        revoked_source_refs=(projection.source_refs[-1],),
    )
    assert revoked.validity is ProjectionValidity.REVOKED

    expired = validate_personality_projection(
        projection,
        active_profile=profile,
        evaluated_at="2026-06-26T10:00:00Z",
    )
    assert expired.validity is ProjectionValidity.EXPIRED
    assert expired.to_dict()["identity_mutation_allowed"] is False


def test_markdown_adapter_is_bounded_and_non_authoritative() -> None:
    projection = project_agent_personality(
        _profile(),
        scope=ProjectionScope(ProjectionScopeLevel.INDIVIDUAL),
        created_at=CREATED_AT,
    )
    markdown = render_personality_projection_markdown(projection)

    assert "Governed Agent Personality Projection" in markdown
    assert "test_before_claim" in markdown
    assert "Execution authorization: **false**" in markdown
    assert "Tool access grant or denial: **false**" in markdown
    assert "rewrite identity" in markdown
