from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.capabilities_constraints_track_center import (
    CAPABILITIES_TRACK,
    CapabilityConstraintEvent,
    CapabilityEventType,
    CapabilityStatus,
    process_capability_event,
)
from trusted_runtime.capability_contract import ConstraintKind
from trusted_runtime.continuity_coordinator import ContinuityDecision, KnowledgeClass

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/capability_constraint_result.schema.json"


def _event(
    event_type: CapabilityEventType,
    status: CapabilityStatus,
    kind: ConstraintKind,
    *,
    repeat_count: int = 1,
    candidate: bool = False,
    evidence: tuple[str, ...] = ("evidence:capability:1",),
    contexts: tuple[str, ...] = ("context:tool",),
    observers: tuple[str, ...] = ("observer:qa",),
    knowledge: KnowledgeClass = KnowledgeClass.FACT,
) -> CapabilityConstraintEvent:
    return CapabilityConstraintEvent(
        event_id="capability-event:1",
        capability_id="capability:test-api",
        event_type=event_type,
        capability_status=status,
        constraint_kind=kind,
        knowledge_class=knowledge,
        statement="A bounded capability or constraint observation.",
        occurred_at="2026-06-25T10:00:00Z",
        confidence=0.92,
        repeat_count=repeat_count,
        evidence_refs=evidence,
        context_refs=contexts,
        observer_refs=observers,
        identity_candidate_statement=(
            "Verify environment before declaring a capability limit."
            if candidate
            else None
        ),
        identity_scope=CAPABILITIES_TRACK if candidate else None,
        identity_repeat_key="capability:verify-environment" if candidate else None,
    )


def _process(event: CapabilityConstraintEvent):
    return process_capability_event(
        event,
        processed_at="2026-06-25T10:01:00Z",
    )


def test_single_observation_or_constraint_creates_no_global_lesson() -> None:
    cases = (
        _event(
            CapabilityEventType.ABILITY_OBSERVED,
            CapabilityStatus.OBSERVED,
            ConstraintKind.NONE,
            knowledge=KnowledgeClass.INFERENCE,
        ),
        _event(
            CapabilityEventType.CONSTRAINT_RECORDED,
            CapabilityStatus.CONSTRAINED,
            ConstraintKind.CONTEXTUAL,
        ),
    )
    for event in cases:
        result = _process(event)
        assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
        assert result.assessment.lesson_candidate is None
        assert result.observation.claims_current_presence is False
        assert result.observation.metadata["local_failure_is_not_global_limitation"]


def test_verified_capability_requires_fact_and_evidence() -> None:
    result = _process(
        _event(
            CapabilityEventType.CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
        )
    )
    assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    with pytest.raises(ValueError, match="FACT"):
        _event(
            CapabilityEventType.CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
            knowledge=KnowledgeClass.INFERENCE,
        )
    with pytest.raises(ValueError, match="evidence"):
        _event(
            CapabilityEventType.CAPABILITY_VERIFIED,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
            evidence=(),
        )


def test_valid_current_capability_and_limitation_are_bounded() -> None:
    capability = _process(
        _event(
            CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
        )
    )
    limitation = _process(
        _event(
            CapabilityEventType.CURRENT_LIMITATION_CLAIM,
            CapabilityStatus.CONSTRAINED,
            ConstraintKind.TEMPORARY,
        )
    )
    for result in (capability, limitation):
        assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
        assert result.observation.claims_current_presence is True
        assert result.assessment.lesson_candidate is None


def test_unverified_or_context_missing_current_claim_is_held() -> None:
    missing_context = _process(
        _event(
            CapabilityEventType.CURRENT_LIMITATION_CLAIM,
            CapabilityStatus.CONSTRAINED,
            ConstraintKind.CONTEXTUAL,
            contexts=(),
        )
    )
    unsupported = _process(
        _event(
            CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
            evidence=(),
            knowledge=KnowledgeClass.INFERENCE,
        )
    )
    disputed = _process(
        _event(
            CapabilityEventType.CURRENT_LIMITATION_CLAIM,
            CapabilityStatus.DISPUTED,
            ConstraintKind.UNKNOWN,
        )
    )
    for result in (missing_context, unsupported, disputed):
        assert result.assessment.decision is ContinuityDecision.HOLD_FOR_REVIEW


@pytest.mark.parametrize(
    "status",
    [CapabilityStatus.RECOVERED, CapabilityStatus.EXPIRED, CapabilityStatus.RETIRED],
)
def test_closed_constraint_blocks_current_limitation(status: CapabilityStatus) -> None:
    result = _process(
        _event(
            CapabilityEventType.CURRENT_LIMITATION_CLAIM,
            status,
            ConstraintKind.UNKNOWN,
        )
    )
    assert result.assessment.decision is ContinuityDecision.BLOCK_FALSE_PRESENCE
    assert result.to_dict()["global_limitation_assignment_allowed"] is False


def test_repeated_capability_and_recovery_emit_only_bounded_lessons() -> None:
    shared = {
        "repeat_count": 2,
        "candidate": True,
        "evidence": ("evidence:1", "evidence:2"),
        "contexts": ("context:api", "context:ui"),
        "observers": ("observer:qa", "observer:sre"),
    }
    events = (
        _event(
            CapabilityEventType.CAPABILITY_PATTERN_VERIFIED,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
            **shared,
        ),
        _event(
            CapabilityEventType.RECOVERY_PATTERN_VERIFIED,
            CapabilityStatus.RECOVERED,
            ConstraintKind.NONE,
            **shared,
        ),
    )
    for event in events:
        result = _process(event)
        assert result.assessment.lesson_candidate is not None
        assert result.to_dict()["stable_identity_update_allowed"] is False


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"repeat_count": 1}, "repeated evidence"),
        ({"evidence": ("e1",)}, "two evidence refs"),
        ({"contexts": ("c1",)}, "cross-context"),
        ({"observers": ("o1",)}, "independent observers"),
    ],
)
def test_candidate_requires_independent_cross_context_repetition(
    overrides: dict[str, object],
    match: str,
) -> None:
    kwargs = {
        "repeat_count": 2,
        "candidate": True,
        "evidence": ("e1", "e2"),
        "contexts": ("c1", "c2"),
        "observers": ("o1", "o2"),
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError, match=match):
        _event(
            CapabilityEventType.CAPABILITY_PATTERN_VERIFIED,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
            **kwargs,
        )


def test_result_is_deterministic_schema_valid_and_non_authoritative() -> None:
    event = _event(
        CapabilityEventType.CAPABILITY_PATTERN_VERIFIED,
        CapabilityStatus.AVAILABLE,
        ConstraintKind.NONE,
        repeat_count=2,
        candidate=True,
        evidence=("e1", "e2"),
        contexts=("c1", "c2"),
        observers=("o1", "o2"),
    )
    first = _process(event)
    second = _process(event)
    assert first.result_id == second.result_id
    payload = first.to_dict()
    denied = (
        "capability_registry_mutation_allowed",
        "capability_restriction_allowed",
        "global_limitation_assignment_allowed",
        "training_scheduling_allowed",
        "priority_mutation_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    )
    assert all(payload[field] is False for field in denied)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
