from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from trusted_runtime.continuity_coordinator import ContinuityDecision, KnowledgeClass
from trusted_runtime.goals_commitments_track_center import (
    GOALS_TRACK,
    CommitmentLevel,
    GoalCommitmentEvent,
    GoalEventType,
    GoalStatus,
    process_goal_event,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "schemas/trusted_runtime/goal_commitment_result.schema.json"


def _event(
    event_type: GoalEventType,
    status: GoalStatus,
    level: CommitmentLevel,
    *,
    repeat_count: int = 1,
    candidate: bool = False,
    evidence_refs: tuple[str, ...] = ("evidence:goal:1",),
    context_refs: tuple[str, ...] = ("context:personal",),
    commitment_refs: tuple[str, ...] = ("commitment:1",),
    knowledge: KnowledgeClass = KnowledgeClass.FACT,
) -> GoalCommitmentEvent:
    return GoalCommitmentEvent(
        event_id="goal-event:1",
        goal_id="goal:publish-release",
        event_type=event_type,
        goal_status=status,
        commitment_level=level,
        knowledge_class=knowledge,
        statement="A bounded goal or commitment observation.",
        occurred_at="2026-06-25T09:00:00Z",
        confidence=0.92,
        repeat_count=repeat_count,
        evidence_refs=evidence_refs,
        context_refs=context_refs,
        commitment_refs=commitment_refs,
        identity_candidate_statement=(
            "Confirm scope before accepting a deadline." if candidate else None
        ),
        identity_scope=GOALS_TRACK if candidate else None,
        identity_repeat_key="goals:scope-before-deadline" if candidate else None,
    )


def _process(event: GoalCommitmentEvent):
    return process_goal_event(event, processed_at="2026-06-25T09:01:00Z")


def test_wish_intention_and_plan_create_no_duty_or_lesson() -> None:
    cases = (
        _event(
            GoalEventType.WISH_OBSERVED,
            GoalStatus.PROPOSED,
            CommitmentLevel.WISH,
            knowledge=KnowledgeClass.INFERENCE,
        ),
        _event(
            GoalEventType.INTENTION_STATED,
            GoalStatus.PROPOSED,
            CommitmentLevel.INTENTION,
            knowledge=KnowledgeClass.MEMORY,
        ),
        _event(
            GoalEventType.PLAN_RECORDED,
            GoalStatus.PROPOSED,
            CommitmentLevel.PLAN,
            knowledge=KnowledgeClass.INFERENCE,
        ),
    )
    for event in cases:
        result = _process(event)
        assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
        assert result.assessment.lesson_candidate is None
        assert result.observation.claims_current_intention is False


def test_active_commitment_and_obligation_require_fact_evidence() -> None:
    for event_type, level in (
        (GoalEventType.COMMITMENT_DECLARED, CommitmentLevel.COMMITMENT),
        (GoalEventType.OBLIGATION_ACCEPTED, CommitmentLevel.OBLIGATION),
    ):
        result = _process(_event(event_type, GoalStatus.ACTIVE, level))
        assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
        with pytest.raises(ValueError, match="FACT"):
            _event(
                event_type,
                GoalStatus.ACTIVE,
                level,
                knowledge=KnowledgeClass.INFERENCE,
            )


def test_follow_through_and_release_emit_only_bounded_lessons() -> None:
    shared = {
        "repeat_count": 2,
        "candidate": True,
        "evidence_refs": ("evidence:1", "evidence:2"),
        "context_refs": ("context:work", "context:family"),
        "commitment_refs": ("commitment:1", "commitment:2"),
    }
    events = (
        _event(
            GoalEventType.FOLLOW_THROUGH_VERIFIED,
            GoalStatus.COMPLETED,
            CommitmentLevel.COMMITMENT,
            **shared,
        ),
        _event(
            GoalEventType.COMMITMENT_RELEASE_VERIFIED,
            GoalStatus.CANCELLED,
            CommitmentLevel.COMMITMENT,
            **shared,
        ),
    )
    for event in events:
        result = _process(event)
        assert result.assessment.lesson_candidate is not None
        assert result.to_dict()["obligation_assignment_allowed"] is False
        assert result.to_dict()["stable_identity_update_allowed"] is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (GoalStatus.PAUSED, ContinuityDecision.HOLD_FOR_REVIEW),
        (GoalStatus.DISPUTED, ContinuityDecision.HOLD_FOR_REVIEW),
        (GoalStatus.PROPOSED, ContinuityDecision.HOLD_FOR_REVIEW),
        (GoalStatus.UNKNOWN, ContinuityDecision.HOLD_FOR_REVIEW),
        (GoalStatus.COMPLETED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
        (GoalStatus.CANCELLED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
        (GoalStatus.EXPIRED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
        (GoalStatus.RETIRED, ContinuityDecision.BLOCK_FALSE_PRESENCE),
    ],
)
def test_current_duty_claim_is_fail_closed(
    status: GoalStatus,
    expected: ContinuityDecision,
) -> None:
    result = _process(
        _event(
            GoalEventType.CURRENT_DUTY_CLAIM,
            status,
            CommitmentLevel.COMMITMENT,
        )
    )
    assert result.assessment.decision is expected
    assert result.to_dict()["obligation_assignment_allowed"] is False


def test_active_current_duty_claim_is_bounded_not_authoritative() -> None:
    result = _process(
        _event(
            GoalEventType.CURRENT_DUTY_CLAIM,
            GoalStatus.ACTIVE,
            CommitmentLevel.OBLIGATION,
        )
    )
    assert result.assessment.decision is ContinuityDecision.ACCEPT_BOUNDED_OBSERVATION
    assert result.observation.claims_current_intention is True
    assert result.to_dict()["work_scheduling_allowed"] is False


@pytest.mark.parametrize(
    ("overrides", "match"),
    [
        ({"repeat_count": 1}, "repeated evidence"),
        ({"evidence_refs": ("e1",)}, "two evidence refs"),
        ({"context_refs": ("c1",)}, "cross-context"),
        ({"commitment_refs": ("g1",)}, "distinct commitments"),
    ],
)
def test_lesson_candidate_requires_repeated_cross_context_commitments(
    overrides: dict[str, object],
    match: str,
) -> None:
    kwargs = {
        "repeat_count": 2,
        "candidate": True,
        "evidence_refs": ("e1", "e2"),
        "context_refs": ("c1", "c2"),
        "commitment_refs": ("g1", "g2"),
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError, match=match):
        _event(
            GoalEventType.FOLLOW_THROUGH_VERIFIED,
            GoalStatus.COMPLETED,
            CommitmentLevel.COMMITMENT,
            **kwargs,
        )


def test_current_duty_rejects_wish_intention_and_plan_levels() -> None:
    for level in (
        CommitmentLevel.WISH,
        CommitmentLevel.INTENTION,
        CommitmentLevel.PLAN,
    ):
        with pytest.raises(ValueError, match="commitment or obligation"):
            _event(
                GoalEventType.CURRENT_DUTY_CLAIM,
                GoalStatus.ACTIVE,
                level,
            )


def test_result_is_deterministic_schema_valid_and_non_authoritative() -> None:
    event = _event(
        GoalEventType.FOLLOW_THROUGH_VERIFIED,
        GoalStatus.COMPLETED,
        CommitmentLevel.COMMITMENT,
        repeat_count=2,
        candidate=True,
        evidence_refs=("e1", "e2"),
        context_refs=("c1", "c2"),
        commitment_refs=("g1", "g2"),
    )
    first = _process(event)
    second = _process(event)
    assert first.result_id == second.result_id
    payload = first.to_dict()
    for field in (
        "goal_registry_mutation_allowed",
        "obligation_assignment_allowed",
        "work_scheduling_allowed",
        "priority_mutation_allowed",
        "stable_identity_update_allowed",
        "execution_authorized",
    ):
        assert payload[field] is False
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(payload)) == []
