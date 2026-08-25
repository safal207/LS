from __future__ import annotations

from ls_agent_trust import TrustRuntime


def _completed_dispatch(
    runtime: TrustRuntime,
    *,
    child_agent: str,
    authority_scope: tuple[str, ...],
):
    dispatch = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent=child_agent,
        task="Perform the bounded operation",
        constraints=("respect current parent policy",),
        authority_scope=authority_scope,
    )
    result = runtime.submit_result(
        dispatch_id=dispatch.receipt_id,
        agent=child_agent,
        status="COMPLETED",
        summary="Completed with bounded evidence.",
        evidence=("fixture:external-review",),
    )
    return dispatch, result


def test_recovery_revalidates_authority_after_parent_revocation() -> None:
    """A recovered worker must not rely only on a stale copied authority scope."""

    authoritative_parent_scope = {"deploy"}
    runtime = TrustRuntime(
        authority_resolver=lambda _dispatch: tuple(authoritative_parent_scope)
    )

    original = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Deployment Agent instance-1",
        task="Perform the bounded operation",
        constraints=("respect current parent policy",),
        authority_scope=tuple(authoritative_parent_scope),
    )

    # Policy-relevant authority changes after D1 was issued.
    authoritative_parent_scope.remove("deploy")

    replacement = runtime.recover_dispatch(
        original.receipt_id,
        replacement_agent="Deployment Agent instance-2",
    )
    result = runtime.submit_result(
        dispatch_id=replacement.receipt_id,
        agent="Deployment Agent instance-2",
        status="COMPLETED",
        summary="Recovered work completed.",
        evidence=("fixture:recovery",),
    )
    runtime.grant_human_approval(
        dispatch_id=replacement.receipt_id,
        effect="deploy",
        approver="reviewer",
        reason="Approval was evaluated against the recovered work only.",
    )

    decision = runtime.authorize_effect(
        dispatch_id=replacement.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="deploy",
    )

    assert "deploy" not in authoritative_parent_scope
    assert decision.allowed is False
    assert decision.reason == "effect is no longer authorized by current parent/policy state"


def test_approval_is_bound_to_exact_effect_request() -> None:
    """Approval for one payment request must not authorize a mutated payment.

    External-review vector from cosai-oasis/ws4-secure-design-agentic-systems#158.
    The trust layer currently binds approval to dispatch + result + normalized
    effect class, but not policy-relevant target/parameters, so this test is
    intentionally RED until exact-request identity participates in approval.
    """

    runtime = TrustRuntime()
    dispatch, result = _completed_dispatch(
        runtime,
        child_agent="Payment Agent",
        authority_scope=("payment",),
    )

    admitted_request = {
        "effect": "payment",
        "amount": 10,
        "recipient": "Alice",
    }
    runtime.grant_human_approval(
        dispatch_id=dispatch.receipt_id,
        effect=admitted_request["effect"],
        approver="reviewer",
        reason="Approved exactly $10 to Alice.",
    )

    mutated_request = {
        "effect": "payment",
        "amount": 10000,
        "recipient": "Bob",
    }
    assert mutated_request != admitted_request

    decision = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect=mutated_request["effect"],
    )

    assert decision.allowed is False
