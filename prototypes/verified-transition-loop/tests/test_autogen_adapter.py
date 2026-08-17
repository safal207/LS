from dataclasses import replace
from pathlib import Path

import pytest

from verified_transition_loop import EvidenceBundle
from verified_transition_loop.autogen_adapter import (
    AutoGenMissionKeeperAdapter,
    AutoGenVTLContext,
    MissionAssessment,
    MissionControlDecision,
    MissionObservedOutcome,
    MissionTransitionRequest,
    link_observed_outcome,
)
from verified_transition_loop.conformance import load_fixture

NOW = 1_800_000_000_000
ROOT = Path(__file__).resolve().parents[1]


class MutableResolver:
    def __init__(self, context: AutoGenVTLContext) -> None:
        self.context = context

    def __call__(self, request: MissionTransitionRequest) -> AutoGenVTLContext:
        return self.context


class FailingResolver:
    def __call__(self, request: MissionTransitionRequest) -> AutoGenVTLContext:
        raise RuntimeError("context unavailable")


def base_evidence() -> EvidenceBundle:
    return EvidenceBundle(
        mission_aligned=True,
        exact_source_bound=True,
        tests_passed=True,
        approval_current=True,
        approval_valid_until_ms=NOW + 60_000,
        evidence_refs=("tests:green", "approval:mission-001"),
        source_ref="git:" + ("d" * 40),
        policy_ref="mission-policy:v1",
        approval_ref="approval:mission-001",
    )


def base_request() -> MissionTransitionRequest:
    return MissionTransitionRequest(
        mission_id="mission-001",
        mission_version="v1",
        transition_id="transition-001",
        actor_id="coordinator-agent",
        action="deploy",
        rationale="release the reviewed artifact without changing the mission",
        pre_state="staging",
        expected_post_state="production-healthy",
        invariants=("goal_aligned", "artifact_matches", "health_ok"),
        occurrence_id="occurrence-001",
    )


def adapter_and_resolver():
    resolver = MutableResolver(
        AutoGenVTLContext(
            current_mission_id="mission-001",
            current_mission_version="v1",
            evidence=base_evidence(),
            executor_id="worker-executor",
        )
    )
    return AutoGenMissionKeeperAdapter(resolver), resolver


def _gate(adapter, record, request, *, now_ms=NOW + 1, execution_nonce=None):
    return adapter.gate(
        record.record_id,
        request,
        now_ms=now_ms,
        execution_nonce=request.occurrence_id if execution_nonce is None else execution_nonce,
    )


def test_context_resolution_failure_rejects_without_secondary_exception():
    adapter = AutoGenMissionKeeperAdapter(FailingResolver())
    record = adapter.assess(base_request(), now_ms=NOW)

    assert record.assessment is MissionAssessment.REJECTED
    assert record.reason_codes == ("CONTEXT_RESOLUTION_FAILED",)
    assert record.execution_allowed is False
    assert record.authorization_decision_id is None
    assert record.proposal_digest is None


def test_historical_alignment_is_not_execution_authority_then_use_time_continues():
    adapter, _ = adapter_and_resolver()
    request = base_request()

    record = adapter.assess(request, now_ms=NOW)
    assert record.assessment is MissionAssessment.ALIGNED
    assert record.execution_allowed is False
    assert not hasattr(adapter, "execute")

    control = _gate(adapter, record, request)
    assert control.decision is MissionControlDecision.CONTINUE
    assert control.transition_may_proceed is True
    assert control.execution_binding == "external"


def test_occurrence_is_bound_to_the_use_time_gate():
    adapter, _ = adapter_and_resolver()
    request = base_request()
    record = adapter.assess(request, now_ms=NOW)

    control = _gate(
        adapter,
        record,
        request,
        execution_nonce="different-occurrence",
    )
    assert control.decision is MissionControlDecision.HALT
    assert control.reason_codes == ("OCCURRENCE_BINDING_MISMATCH",)


def test_same_integrity_record_cannot_release_transition_twice():
    adapter, _ = adapter_and_resolver()
    request = base_request()
    record = adapter.assess(request, now_ms=NOW)

    first = _gate(adapter, record, request)
    assert first.decision is MissionControlDecision.CONTINUE

    replay = _gate(adapter, record, request, now_ms=NOW + 2)
    assert replay.decision is MissionControlDecision.HALT
    assert replay.reason_codes == ("INTEGRITY_RECORD_ALREADY_USED",)


def test_repeating_assess_after_continue_cannot_reset_single_use_state():
    adapter, _ = adapter_and_resolver()
    request = base_request()
    record = adapter.assess(request, now_ms=NOW)
    assert _gate(adapter, record, request).decision is MissionControlDecision.CONTINUE

    repeated = adapter.assess(request, now_ms=NOW + 2)
    assert repeated.assessment is MissionAssessment.REJECTED
    assert repeated.reason_codes == ("OCCURRENCE_ALREADY_RELEASED",)


def test_mission_version_drift_halts_instead_of_silent_reinterpretation():
    adapter, resolver = adapter_and_resolver()
    request = base_request()
    record = adapter.assess(request, now_ms=NOW)

    resolver.context = replace(resolver.context, current_mission_version="v2")
    control = _gate(adapter, record, request)
    assert control.decision is MissionControlDecision.HALT
    assert control.reason_codes == ("MISSION_VERSION_CHANGED",)


def test_unresolved_hold_requires_review_and_carries_no_latent_authority():
    adapter, resolver = adapter_and_resolver()
    resolver.context = replace(
        resolver.context,
        evidence=replace(
            resolver.context.evidence,
            approval_current=None,
            approval_ref=None,
        ),
    )
    request = base_request()
    record = adapter.assess(request, now_ms=NOW)
    assert record.assessment is MissionAssessment.REVIEW_REQUIRED

    control = _gate(adapter, record, request)
    assert control.decision is MissionControlDecision.REQUIRE_REVIEW
    assert control.transition_may_proceed is False


def test_hold_requires_fresh_authorization_before_continue():
    adapter, resolver = adapter_and_resolver()
    resolver.context = replace(
        resolver.context,
        evidence=replace(
            resolver.context.evidence,
            approval_current=None,
            approval_ref=None,
        ),
    )
    request = base_request()
    record = adapter.assess(request, now_ms=NOW)
    assert record.assessment is MissionAssessment.REVIEW_REQUIRED

    resolver.context = replace(resolver.context, evidence=base_evidence())
    control = _gate(adapter, record, request)
    assert control.decision is MissionControlDecision.CONTINUE


def test_mutated_transition_request_cannot_use_old_integrity_record():
    adapter, _ = adapter_and_resolver()
    request = base_request()
    record = adapter.assess(request, now_ms=NOW)

    mutated = replace(request, expected_post_state="different-target")
    control = _gate(adapter, record, mutated)
    assert control.decision is MissionControlDecision.HALT
    assert control.reason_codes == ("REQUEST_BINDING_MISMATCH",)


def test_missing_occurrence_identity_rejects_at_assessment():
    adapter, _ = adapter_and_resolver()
    record = adapter.assess(replace(base_request(), occurrence_id=""), now_ms=NOW)
    assert record.assessment is MissionAssessment.REJECTED
    assert record.reason_codes == ("OCCURRENCE_ID_MISSING",)


def test_verifier_executor_separation_is_mechanical():
    adapter, resolver = adapter_and_resolver()
    resolver.context = replace(
        resolver.context,
        executor_id=resolver.context.verifier_id,
    )
    record = adapter.assess(base_request(), now_ms=NOW)
    assert record.assessment is MissionAssessment.REJECTED
    assert record.reason_codes == ("VERIFIER_EXECUTOR_NOT_SEPARATED",)


def test_observed_outcome_is_a_separate_audit_record():
    adapter, _ = adapter_and_resolver()
    record = adapter.assess(base_request(), now_ms=NOW)
    assert not hasattr(record, "observed_outcome_ref")

    outcome = MissionObservedOutcome(
        transition_id=record.transition_id,
        outcome_ref="outcome:001",
        observed_state="production-healthy",
    )
    link = link_observed_outcome(record, outcome)
    assert link.integrity_record_id == record.record_id
    assert link.outcome_ref == "outcome:001"

    with pytest.raises(ValueError, match="OUTCOME_TRANSITION_MISMATCH"):
        link_observed_outcome(
            record,
            replace(outcome, transition_id="other-transition"),
        )


def test_v04_vectors_map_to_autogen_continue_or_halt_with_same_reasons():
    fixture = load_fixture(ROOT / "fixtures" / "use-time-conformance-v0.4.json")
    base = fixture["base"]

    authorized_data = dict(base["authorization_evidence"])
    authorized_data["evidence_refs"] = tuple(authorized_data["evidence_refs"])
    authorized_evidence = EvidenceBundle(**authorized_data)

    for case in fixture["cases"]:
        # Proposal drift is exercised by the portable core oracle. The AutoGen
        # adapter binds proposal identity through the immutable request digest.
        # Empty nonce is rejected earlier as missing framework occurrence id.
        if "proposal" in case or not case["execution_nonce"]:
            continue

        current_data = dict(case["current_evidence"])
        current_data["evidence_refs"] = tuple(current_data["evidence_refs"])
        current_evidence = EvidenceBundle(**current_data)

        resolver = MutableResolver(
            AutoGenVTLContext(
                current_mission_id="mission-conformance",
                current_mission_version="v1",
                evidence=authorized_evidence,
                executor_id=base["executor_id"],
                verifier_id=base["authorization_verifier_id"],
            )
        )
        adapter = AutoGenMissionKeeperAdapter(resolver)
        request = MissionTransitionRequest(
            mission_id="mission-conformance",
            mission_version="v1",
            transition_id=f"autogen-{case['id']}",
            actor_id="coordinator-agent",
            action=base["proposal"]["action"],
            rationale="conformance",
            pre_state=base["proposal"]["pre_state"],
            expected_post_state=base["proposal"]["expected_post_state"],
            invariants=tuple(base["proposal"]["invariants"]),
            occurrence_id=case["execution_nonce"],
        )

        record = adapter.assess(request, now_ms=base["authorized_at_ms"])
        assert record.assessment is MissionAssessment.ALIGNED

        resolver.context = replace(
            resolver.context,
            evidence=current_evidence,
            executor_id=case["executor_id"],
        )
        control = adapter.gate(
            record.record_id,
            request,
            now_ms=case["checked_at_ms"],
            execution_nonce=request.occurrence_id,
        )

        expected = case["expected"]
        if expected["verdict"] == "EXECUTE":
            assert control.decision is MissionControlDecision.CONTINUE
            assert control.reason_codes == ()
        else:
            assert control.decision is MissionControlDecision.HALT
            assert control.reason_codes == tuple(expected["reason_codes"])
