from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.capabilities_constraints_track_center import (
    CAPABILITIES_TRACK,
    CapabilityConstraintEvent,
    CapabilityEventType,
    CapabilityScope,
    CapabilityStatus,
    process_capability_event,
)
from trusted_runtime.continuity_coordinator import ContinuityDecision, KnowledgeClass


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/capability_constraint_result.schema.json"


def _event(
    event_type: CapabilityEventType,
    status: CapabilityStatus,
    *,
    scope: CapabilityScope = CapabilityScope.LOCAL,
    repeat_count: int = 1,
    candidate: bool = False,
    evidence_refs: tuple[str, ...] = ("evidence:capability:1",),
    context_refs: tuple[str, ...] = ("context:repo-a",),
    capability_refs: tuple[str, ...] = ("capability-observation:1",),
    resource_refs: tuple[str, ...] = (),
    knowledge: KnowledgeClass = KnowledgeClass.FACT,
) -> CapabilityConstraintEvent:
    return CapabilityConstraintEvent(
        event_id="capability-event:1",
        capability_id="capability:review-python-change",
        event_type=event_type,
        capability_status=status,
        capability_scope=scope,
        knowledge_class=knowledge,
        statement="A bounded capability or constraint observation.",
        occurred_at="2026-06-25T09:00:00Z",
        confidence=0.92,
        repeat_count=repeat_count,
        evidence_refs=evidence_refs,
        context_refs=context_refs,
        capability_refs=capability_refs,
        resource_refs=resource_refs,
        identity_candidate_statement=(
            "Verify evidence before claiming a capability." if candidate else None
        ),
        identity_scope=CAPABILITIES_TRACK if candidate else None,
        identity_repeat_key=(
            "capabilities:evidence-before-claim" if candidate else None
        ),
    )


def _process(event: CapabilityConstraintEvent):
    return process_capability_event(
        event,
        processed_at="2026-06-25T09:01:00Z",
    )


def test_one_observation_or_constraint_creates_no_global_incapacity_or_lesson() -> None:
    observed = _event(
        CapabilityEventType.ABILITY_OBSERVED,
        CapabilityStatus.OBSERVED,
        knowledge=KnowledgeClass.INFERENCE,
        evidence_refs=(),
    )
    constraint = _event(
        CapabilityEventType.CONSTRAINT_RECORDED,
        CapabilityStatus.CONSTRAINED,
    )

    for event in (observed, constraint):
        result = _process(event)
        assert result.assessment.lesson_candidate is None
        assert result.observation.claims_current_presence is False
        payload = result.to_dict()
        assert payload["permanent_incapacity_assignment_allowed"] is False
        assert payload["stable_identity_update_allowed"] is False


def test_verified_capability_requires_source_backed_fact_evidence() -> None:
    result = _process(
        _event(
            CapabilityEventType.CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
        )
    )
    assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION

    with pytest.raises(ValueError, match="FACT"):
        _event(
            CapabilityEventType.CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            knowledge=KnowledgeClass.INFERENCE,
        )
    with pytest.raises(ValueError, match="require evidence"):
        _event(
            CapabilityEventType.CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            evidence_refs=(),
        )


def test_resource_unavailability_requires_resource_reference() -> None:
    with pytest.raises(ValueError, match="resource refs"):
        _event(
            CapabilityEventType.RESOURCE_UNAVAILABLE,
            CapabilityStatus.UNAVAILABLE,
        )

    result = _process(
        _event(
            CapabilityEventType.RESOURCE_UNAVAILABLE,
            CapabilityStatus.UNAVAILABLE,
            resource_refs=("resource:python-runtime",),
        )
    )
    assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (CapabilityStatus.OBSERVED, ContinuityDecision.HOLD_FOR_REVIEW),
        (CapabilityStatus.DISPUTED, ContinuityDecision.HOLD_FOR_REVIEW),
        (CapabilityStatus.UNKNOWN, ContinuityDecision.HOLD_FOR_REVIEW),
        (CapabilityStatus.AVAILABLE, ContinuityDecision.BLOCK_FALSE_PRESENCE),
        (CapabilityStatus.RECOVERED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
        (CapabilityStatus.EXPIRED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
        (CapabilityStatus.RETIRED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
    ],
)
def test_current_incapacity_claim_is_fail_closed(
    status: CapabilityStatus,
    expected: ContinuityDecision,
) -> None:
    result = _process(
        _event(
            CapabilityEventType.CURRENT_INCAPABILITY_CLAIM,
            status,
        )
    )
    assert result.assessment.decision is expected
    assert result.to_dict()["access_denial_allowed"] is False
    assert result.to_dict()["permanent_incapacity_assignment_allowed"] is False


def test_context_bound_current_constraint_is_bounded_not_authoritative() -> None:
    result = _process(
        _event(
            CapabilityEventType.CURRENT_INCAPABILITY_CLAIM,
            CapabilityStatus.CONSTRAINED,
            scope=CapabilityScope.PROJECT,
            context_refs=("project:ls",),
        )
    )
    assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    assert result.observation.claims_current_presence is True
    assert result.to_dict()["capability_registry_mutation_allowed"] is False
    assert result.to_dict()["training_scheduling_allowed"] is False


def test_repeated_capability_and_recovery_emit_only_bounded_lessons() -> None:
    shared = {
        "scope": CapabilityScope.CROSS_CONTEXT,
        "repeat_count": 2,
        "candidate": True,
        "evidence_refs": ("evidence:1", "evidence:2"),
        "context_refs": ("context:repo-a", "context:repo-b"),
        "capability_refs": ("observation:1", "observation:2"),
    }
    events = (
        _event(
            CapabilityEventType.REPEATED_CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            **shared,
        ),
        _event(
            CapabilityEventType.REPEATED_RECOVERY_VERIFIED,
            CapabilityStatus.RECOVERED,
            **shared,
        ),
    )
    for event in events:
        result = _process(event)
        assert result.assessment.lesson_candidate is not None
        assert result.assessment.lesson_candidate.scope == CAPABILITIES_TRACK
        assert result.to_dict()["stable_identity_update_allowed"] is False
        assert result.to_dict()["execution_authorized"] is False


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"scope": CapabilityScope.LOCAL}, "CROSS_CONTEXT"),
        ({"repeat_count": 1}, "repeated evidence"),
        ({"evidence_refs": ("e1",)}, "two evidence refs"),
        ({"context_refs": ("c1",)}, "cross-context"),
        ({"capability_refs": ("o1",)}, "distinct capability observations"),
    ],
)
def test_lesson_candidate_requires_repeated_cross_context_evidence(
    overrides: dict[str, object],
    match: str,
) -> None:
    kwargs = {
        "scope": CapabilityScope.CROSS_CONTEXT,
        "repeat_count": 2,
        "candidate": True,
        "evidence_refs": ("e1", "e2"),
        "context_refs": ("c1", "c2"),
        "capability_refs": ("o1", "o2"),
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError, match=match):
        _event(
            CapabilityEventType.REPEATED_CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            **kwargs,
        )


def test_cross_context_incapacity_claim_requires_multiple_contexts() -> None:
    with pytest.raises(ValueError, match="two contexts"):
        _event(
            CapabilityEventType.CURRENT_INCAPABILITY_CLAIM,
            CapabilityStatus.CONSTRAINED,
            scope=CapabilityScope.CROSS_CONTEXT,
            context_refs=("context:one",),
        )


def test_outcome_status_contracts_fail_closed() -> None:
    with pytest.raises(ValueError, match="requires AVAILABLE"):
        _event(
            CapabilityEventType.CAPABILITY_VERIFIED,
            CapabilityStatus.CONSTRAINED,
        )
    with pytest.raises(ValueError, match="requires RECOVERED"):
        _event(
            CapabilityEventType.REPEATED_RECOVERY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            scope=CapabilityScope.CROSS_CONTEXT,
            repeat_count=2,
            candidate=True,
            evidence_refs=("e1", "e2"),
            context_refs=("c1", "c2"),
            capability_refs=("o1", "o2"),
        )


def test_result_is_deterministic_schema_valid_and_non_authoritative() -> None:
    event = _event(
        CapabilityEventType.REPEATED_CAPABILITY_VERIFIED,
        CapabilityStatus.AVAILABLE,
        scope=CapabilityScope.CROSS_CONTEXT,
        repeat_count=2,
        candidate=True,
        evidence_refs=("e1", "e2"),
        context_refs=("c1", "c2"),
        capability_refs=("o1", "o2"),
    )
    first = _process(event)
    second = _process(event)
    assert first.result_id == second.result_id
    payload = first.to_dict()
    for field in (
        "capability_registry_mutation_allowed",
        "access_denial_allowed",
        "permanent_incapacity_assignment_allowed",
        "training_scheduling_allowed",
        "priority_mutation_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    ):
        assert payload[field] is False
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
