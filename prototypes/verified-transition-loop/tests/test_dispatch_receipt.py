from dataclasses import asdict
from pathlib import Path

from verified_transition_loop import (
    EvidenceBundle,
    TransitionIntent,
    TransitionProposal,
    evaluate_transition,
    revalidate_authorization_for_use,
)
from verified_transition_loop.autogen_adapter import MissionTransitionRequest
from verified_transition_loop.crewai_adapter import CrewGuardrailRequest, _tool_action
from verified_transition_loop.dispatch_receipt import (
    PROFILE_ID,
    ActionEnvelope,
    build_action_grant_binding,
    build_tool_dispatch_receipt,
    load_fixture,
    main,
    run_fixture,
    transcript_to_dict,
    verify_dispatch_transcript,
    verify_serialized_authorization_receipt,
    verify_serialized_use_time_receipt,
)

NOW = 1_800_000_000_000
ROOT = Path(__file__).resolve().parents[1]


def evidence() -> EvidenceBundle:
    return EvidenceBundle(
        mission_aligned=True,
        exact_source_bound=True,
        tests_passed=True,
        approval_current=True,
        approval_valid_until_ms=NOW + 60_000,
        evidence_refs=("tests:green", "approval:dispatch-v07"),
        source_ref="git:" + ("f" * 40),
        policy_ref="dispatch-policy:v1",
        approval_ref="approval:dispatch-v07",
    )


def release_for(
    *,
    action: str,
    transition_id: str,
    intent_id: str,
    executor_id: str,
    execution_nonce: str,
):
    intent = TransitionIntent(
        intent_id=intent_id,
        actor="runtime-agent",
        action=action,
        purpose="exercise detached dispatch proof",
    )
    proposal = TransitionProposal(
        transition_id=transition_id,
        intent_id=intent_id,
        pre_state="pending",
        action=action,
        expected_post_state="complete",
        invariants=("authorized", "single_use", "outcome_linked"),
    )
    auth = evaluate_transition(
        intent=intent,
        proposal=proposal,
        evidence=evidence(),
        verifier_id="vtl-dispatch-test-verifier",
        executor_id=executor_id,
        now_ms=NOW,
    )
    use = revalidate_authorization_for_use(
        proposal=proposal,
        authorization=auth,
        current_evidence=evidence(),
        executor_id=executor_id,
        now_ms=NOW + 1,
        execution_nonce=execution_nonce,
    )
    return proposal, auth, use


def transcript_for_crewai():
    request = CrewGuardrailRequest(
        tool_name="ShellTool",
        tool_input={"command": "echo verified"},
        agent_role="release-agent",
        task_description="run the exact reviewed command",
        crew_id="crew-v07",
        timestamp="2030-01-01T00:00:00Z",
        tool_call_id="tool-call-v07",
    )
    action = _tool_action(request)
    proposal, auth, use = release_for(
        action=action,
        transition_id="crew-transition-v07",
        intent_id="crew-intent-v07",
        executor_id="crew-runtime-executor",
        execution_nonce="crew-use-v07",
    )
    envelope = ActionEnvelope(
        runtime_surface="crewai",
        transition_id=proposal.transition_id,
        occurrence_id=request.tool_call_id or request.timestamp,
        action=proposal.action,
        payload=asdict(request),
    )
    envelope_dict = asdict(envelope)
    binding = build_action_grant_binding(
        proposal=asdict(proposal),
        authorization=asdict(auth),
        use_time=asdict(use),
        action_envelope=envelope_dict,
        bound_at_ms=NOW + 2,
    )
    outcome = {
        "outcome_ref": "outcome:crew:v07",
        "transition_id": proposal.transition_id,
        "observed_state": "complete",
        "status": "success",
    }
    dispatch = build_tool_dispatch_receipt(
        proposal=asdict(proposal),
        authorization=asdict(auth),
        use_time=asdict(use),
        grant_binding=binding,
        action_envelope=envelope_dict,
        observed_outcome=outcome,
        dispatch_ref="dispatch:crew:v07",
        observed_outcome_ref=outcome["outcome_ref"],
        dispatched_at_ms=NOW + 3,
        observed_at_ms=NOW + 4,
    )
    return transcript_to_dict(
        proposal=asdict(proposal),
        authorization=asdict(auth),
        use_time=asdict(use),
        action_envelope=envelope_dict,
        grant_binding=binding,
        dispatch_receipt=dispatch,
        observed_outcome=outcome,
    )


def transcript_for_autogen():
    request = MissionTransitionRequest(
        mission_id="mission-v07",
        mission_version="v1",
        transition_id="autogen-transition-v07",
        actor_id="coordinator-agent",
        action="deploy-reviewed-artifact",
        rationale="release without mission reinterpretation",
        pre_state="staging",
        expected_post_state="complete",
        invariants=("authorized", "single_use", "outcome_linked"),
        occurrence_id="mission-occurrence-v07",
    )
    proposal, auth, use = release_for(
        action=request.action,
        transition_id=request.transition_id,
        intent_id="autogen-intent-v07",
        executor_id="autogen-runtime-executor",
        execution_nonce=request.occurrence_id,
    )
    envelope = ActionEnvelope(
        runtime_surface="autogen",
        transition_id=proposal.transition_id,
        occurrence_id=request.occurrence_id,
        action=proposal.action,
        payload=asdict(request),
    )
    envelope_dict = asdict(envelope)
    binding = build_action_grant_binding(
        proposal=asdict(proposal),
        authorization=asdict(auth),
        use_time=asdict(use),
        action_envelope=envelope_dict,
        bound_at_ms=NOW + 2,
    )
    outcome = {
        "outcome_ref": "outcome:autogen:v07",
        "transition_id": proposal.transition_id,
        "observed_state": "complete",
        "status": "success",
    }
    dispatch = build_tool_dispatch_receipt(
        proposal=asdict(proposal),
        authorization=asdict(auth),
        use_time=asdict(use),
        grant_binding=binding,
        action_envelope=envelope_dict,
        observed_outcome=outcome,
        dispatch_ref="dispatch:autogen:v07",
        observed_outcome_ref=outcome["outcome_ref"],
        dispatched_at_ms=NOW + 3,
        observed_at_ms=NOW + 4,
    )
    return transcript_to_dict(
        proposal=asdict(proposal),
        authorization=asdict(auth),
        use_time=asdict(use),
        action_envelope=envelope_dict,
        grant_binding=binding,
        dispatch_receipt=dispatch,
        observed_outcome=outcome,
    )


def test_serialized_core_receipts_are_independently_verifiable():
    transcript = transcript_for_crewai()
    assert verify_serialized_authorization_receipt(transcript["authorization"])
    assert verify_serialized_use_time_receipt(transcript["use_time"])


def test_same_detached_verifier_accepts_crewai_and_autogen_shaped_transcripts():
    for transcript in (transcript_for_crewai(), transcript_for_autogen()):
        result = verify_dispatch_transcript(transcript)
        assert result.valid is True
        assert result.reason_codes == ()
        assert transcript["profile_id"] == PROFILE_ID


def test_action_envelope_drift_fails_even_when_dispatch_receipt_is_unchanged():
    transcript = transcript_for_crewai()
    transcript["action_envelope"]["payload"]["tool_input"]["command"] = "echo drifted"

    result = verify_dispatch_transcript(transcript)

    assert result.valid is False
    assert "GRANT_ACTION_ENVELOPE_DIGEST_MISMATCH" in result.reason_codes
    assert "GRANT_ACTION_ID_MISMATCH" in result.reason_codes


def test_sibling_capability_substitution_fails_closed():
    transcript = transcript_for_crewai()
    authorized_action = transcript["dispatch_receipt"]["authorized_action_id"]
    transcript["dispatch_receipt"]["dispatched_action_id"] = (
        authorized_action + "-equivalent-effect-path"
    )

    result = verify_dispatch_transcript(transcript)

    assert result.valid is False
    assert "SIBLING_CAPABILITY_SUBSTITUTION" in result.reason_codes
    assert "DISPATCH_RECEIPT_INVALID" in result.reason_codes


def test_same_use_id_cannot_prove_a_second_dispatch():
    transcript = transcript_for_autogen()
    seen = {transcript["use_time"]["use_id"]}

    result = verify_dispatch_transcript(transcript, seen_use_ids=seen)

    assert result.valid is False
    assert result.reason_codes == ("GRANT_REPLAYED",)


def test_v07_static_fixture_runs_all_negative_vectors():
    fixture = load_fixture(ROOT / "fixtures" / "tool-dispatch-receipt-v0.7.json")
    result = run_fixture(fixture)

    assert result["summary"] == {
        "total": 11,
        "passed": 11,
        "failed": 0,
        "all_passed": True,
    }


def test_v07_cli_accepts_the_static_fixture():
    fixture_path = ROOT / "fixtures" / "tool-dispatch-receipt-v0.7.json"
    assert main([str(fixture_path)]) == 0
