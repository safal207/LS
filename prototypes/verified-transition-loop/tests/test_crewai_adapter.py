from dataclasses import replace
from pathlib import Path

from verified_transition_loop import EvidenceBundle
from verified_transition_loop.crewai_adapter import (
    CrewGuardrailDisposition,
    CrewGuardrailRequest,
    CrewVTLContext,
    CrewVTLGuardrailProvider,
)
from verified_transition_loop.conformance import load_fixture

NOW = 1_800_000_000_000
ROOT = Path(__file__).resolve().parents[1]


class MutableResolver:
    def __init__(self, context: CrewVTLContext) -> None:
        self.context = context

    def __call__(self, request: CrewGuardrailRequest) -> CrewVTLContext:
        return self.context


def base_evidence() -> EvidenceBundle:
    return EvidenceBundle(
        mission_aligned=True,
        exact_source_bound=True,
        tests_passed=True,
        approval_current=True,
        approval_valid_until_ms=NOW + 60_000,
        evidence_refs=("tests:green", "approval:deploy-001"),
        source_ref="git:" + ("b" * 40),
        policy_ref="policy:deploy-v1",
        approval_ref="approval:deploy-001",
    )


def base_request() -> CrewGuardrailRequest:
    return CrewGuardrailRequest(
        tool_name="deploy",
        tool_input={"commit": "b" * 40, "environment": "production"},
        agent_role="release-agent",
        task_description="deploy the reviewed commit",
        crew_id="crew-release-1",
        timestamp="2026-08-17T09:00:00+07:00",
        tool_call_id="tool-call-001",
    )


def provider_and_resolver():
    resolver = MutableResolver(
        CrewVTLContext(
            pre_state="production:" + ("a" * 40),
            expected_post_state="production:" + ("b" * 40),
            invariants=("commit_matches", "health_ok"),
            evidence=base_evidence(),
            executor_id="crew-tool-executor",
        )
    )
    return CrewVTLGuardrailProvider(resolver), resolver


def _resume(provider, first, request, *, now_ms=NOW + 1, execution_nonce="occurrence-001"):
    assert first.decision_ref
    assert first.continuation_token
    return provider.resume(
        first.decision_ref,
        first.continuation_token,
        request,
        now_ms=now_ms,
        execution_nonce=execution_nonce,
    )


def test_authorized_tool_call_defers_until_use_time_then_allows():
    provider, _ = provider_and_resolver()
    request = base_request()

    first = provider.evaluate(request, now_ms=NOW)
    assert first.disposition is CrewGuardrailDisposition.DEFER
    assert first.reason_codes == ("USE_TIME_REVALIDATION_REQUIRED",)
    assert first.execution_allowed is False
    assert first.decision_ref
    assert first.continuation_token

    resumed = _resume(provider, first, request)
    assert resumed.disposition is CrewGuardrailDisposition.ALLOW
    assert resumed.execution_allowed is True
    assert resumed.use_id


def test_repeated_pending_evaluate_is_idempotent_and_keeps_secret_token():
    provider, _ = provider_and_resolver()
    request = base_request()
    first = provider.evaluate(request, now_ms=NOW)
    repeated = provider.evaluate(request, now_ms=NOW + 1)

    assert repeated.disposition is CrewGuardrailDisposition.DEFER
    assert repeated.decision_ref == first.decision_ref
    assert repeated.continuation_token == first.continuation_token

    other = replace(request, tool_call_id="tool-call-002")
    other_first = provider.evaluate(other, now_ms=NOW)
    assert other_first.continuation_token
    assert other_first.continuation_token != first.continuation_token


def test_repeating_first_call_after_allow_cannot_reset_single_use_state():
    provider, _ = provider_and_resolver()
    request = base_request()
    first = provider.evaluate(request, now_ms=NOW)
    assert _resume(provider, first, request).disposition is CrewGuardrailDisposition.ALLOW

    repeated = provider.evaluate(request, now_ms=NOW + 2)
    assert repeated.disposition is CrewGuardrailDisposition.DENY
    assert repeated.reason_codes == ("OCCURRENCE_ALREADY_RELEASED",)


def test_wrong_continuation_token_is_rejected():
    provider, _ = provider_and_resolver()
    request = base_request()
    first = provider.evaluate(request, now_ms=NOW)
    assert first.decision_ref

    denied = provider.resume(
        first.decision_ref,
        "cont_wrong",
        request,
        now_ms=NOW + 1,
        execution_nonce="occurrence-001",
    )
    assert denied.disposition is CrewGuardrailDisposition.DENY
    assert denied.reason_codes == ("CONTINUATION_TOKEN_INVALID",)


def test_same_continuation_cannot_release_tool_twice():
    provider, _ = provider_and_resolver()
    request = base_request()
    first = provider.evaluate(request, now_ms=NOW)

    allowed = _resume(provider, first, request)
    assert allowed.disposition is CrewGuardrailDisposition.ALLOW

    replay = _resume(provider, first, request, now_ms=NOW + 2)
    assert replay.disposition is CrewGuardrailDisposition.DENY
    assert replay.reason_codes == ("CONTINUATION_ALREADY_USED",)


def test_policy_drift_denies_before_tool_release():
    provider, resolver = provider_and_resolver()
    request = base_request()
    first = provider.evaluate(request, now_ms=NOW)

    resolver.context = replace(
        resolver.context,
        evidence=replace(
            resolver.context.evidence,
            policy_ref="policy:deploy-v2",
        ),
    )
    resumed = _resume(provider, first, request)
    assert resumed.disposition is CrewGuardrailDisposition.DENY
    assert resumed.reason_codes == (
        "POLICY_REF_CHANGED",
        "EVIDENCE_CONTEXT_CHANGED",
    )
    assert resumed.execution_allowed is False


def test_mutated_request_cannot_resume_old_decision():
    provider, _ = provider_and_resolver()
    request = base_request()
    first = provider.evaluate(request, now_ms=NOW)

    mutated = replace(
        request,
        tool_input={"commit": "c" * 40, "environment": "production"},
    )
    resumed = _resume(provider, first, mutated)
    assert resumed.disposition is CrewGuardrailDisposition.DENY
    assert resumed.reason_codes == ("REQUEST_BINDING_MISMATCH",)


def test_missing_occurrence_identity_denies():
    provider, _ = provider_and_resolver()
    request = replace(base_request(), tool_call_id=None, timestamp="")
    decision = provider.evaluate(request, now_ms=NOW)
    assert decision.disposition is CrewGuardrailDisposition.DENY
    assert decision.reason_codes == ("OCCURRENCE_ID_MISSING",)


def test_async_hold_can_be_resolved_then_use_time_allowed():
    provider, resolver = provider_and_resolver()
    resolver.context = replace(
        resolver.context,
        evidence=replace(
            resolver.context.evidence,
            approval_current=None,
            approval_ref=None,
        ),
    )
    request = base_request()
    first = provider.evaluate(request, now_ms=NOW)
    assert first.disposition is CrewGuardrailDisposition.DEFER

    resolver.context = replace(
        resolver.context,
        evidence=base_evidence(),
    )
    resumed = _resume(provider, first, request)
    assert resumed.disposition is CrewGuardrailDisposition.ALLOW
    assert resumed.execution_allowed is True


def test_v04_vectors_map_to_crewai_allow_or_deny_with_same_reasons():
    fixture = load_fixture(ROOT / "fixtures" / "use-time-conformance-v0.4.json")
    base = fixture["base"]

    authorized_data = dict(base["authorization_evidence"])
    authorized_data["evidence_refs"] = tuple(authorized_data["evidence_refs"])
    authorized_evidence = EvidenceBundle(**authorized_data)

    for case in fixture["cases"]:
        # Proposal drift is exercised directly by the portable core oracle.
        # Framework adapters bind their own generated proposal to the request and
        # cover request mutation separately rather than accepting case overrides.
        if "proposal" in case:
            continue

        current_data = dict(case["current_evidence"])
        current_data["evidence_refs"] = tuple(current_data["evidence_refs"])
        current_evidence = EvidenceBundle(**current_data)

        resolver = MutableResolver(
            CrewVTLContext(
                pre_state=base["proposal"]["pre_state"],
                expected_post_state=base["proposal"]["expected_post_state"],
                invariants=tuple(base["proposal"]["invariants"]),
                evidence=authorized_evidence,
                executor_id=base["executor_id"],
                verifier_id=base["authorization_verifier_id"],
            )
        )
        provider = CrewVTLGuardrailProvider(resolver)
        request = CrewGuardrailRequest(
            tool_name="deploy",
            tool_input={"commit": "fixture"},
            agent_role="release-agent",
            task_description="conformance",
            crew_id="crew-conformance",
            timestamp="2026-08-17T09:00:00+07:00",
            tool_call_id=f"tool-{case['id']}",
        )
        first = provider.evaluate(request, now_ms=base["authorized_at_ms"])
        assert first.decision_ref
        assert first.continuation_token
        assert first.disposition is CrewGuardrailDisposition.DEFER

        resolver.context = replace(
            resolver.context,
            evidence=current_evidence,
            executor_id=case["executor_id"],
        )
        resumed = provider.resume(
            first.decision_ref,
            first.continuation_token,
            request,
            now_ms=case["checked_at_ms"],
            execution_nonce=case["execution_nonce"],
        )

        expected = case["expected"]
        if expected["verdict"] == "EXECUTE":
            assert resumed.disposition is CrewGuardrailDisposition.ALLOW
            assert resumed.reason_codes == ()
        else:
            assert resumed.disposition is CrewGuardrailDisposition.DENY
            assert resumed.reason_codes == tuple(expected["reason_codes"])
