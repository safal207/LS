from __future__ import annotations

from ls_agent_trust import TrustRuntime


def test_recovery_revalidates_authority_after_parent_revocation() -> None:
    """CoSAI #158: carried-forward scope must not outlive its parent grant."""

    runtime = TrustRuntime()

    # Model the authoritative parent-side grant that existed when D1 was issued.
    # v0.1 snapshots that grant into authority_scope but has no freshness or
    # revocation input at recovery/effect-admission time.
    authoritative_parent_grants = {"deploy"}

    original = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Deploy Agent instance-1",
        task="Deploy the reviewed release",
        authority_scope=tuple(authoritative_parent_grants),
    )

    # The parent/policy state changes before recovery: deploy is revoked.
    authoritative_parent_grants.remove("deploy")
    assert "deploy" not in authoritative_parent_grants

    replacement = runtime.recover_dispatch(
        original.receipt_id,
        replacement_agent="Deploy Agent instance-2",
    )
    result = runtime.submit_result(
        dispatch_id=replacement.receipt_id,
        agent="Deploy Agent instance-2",
        status="COMPLETED",
        summary="Recovery worker completed the delegated task.",
        evidence=("cosai:authority-revalidation-vector",),
    )
    runtime.grant_human_approval(
        dispatch_id=replacement.receipt_id,
        effect="deploy",
        approver="reviewer",
        reason="Approve only if the recovered authority is still valid.",
    )

    decision = runtime.authorize_effect(
        dispatch_id=replacement.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="deploy",
    )

    assert decision.allowed is False, (
        "recovery reused the predecessor's stale authority_scope after the "
        "authoritative parent grant revoked deploy"
    )


def test_approval_is_bound_to_exact_effect_request() -> None:
    """CoSAI #158: approval for A must not authorize mutated request A-prime."""

    runtime = TrustRuntime()
    original_request = {
        "effect": "payment",
        "amount": 10,
        "recipient": "Alice",
    }
    mutated_request = {
        "effect": "payment",
        "amount": 1000,
        "recipient": "Bob",
    }
    assert original_request != mutated_request

    dispatch = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Payment Agent",
        task="Prepare the exact approved payment",
        authority_scope=("payment",),
    )
    result = runtime.submit_result(
        dispatch_id=dispatch.receipt_id,
        agent="Payment Agent",
        status="COMPLETED",
        summary="Payment request prepared.",
        evidence=("cosai:exact-effect-request-vector",),
    )

    # Approval is currently keyed only by dispatch + result + normalized
    # effect class, so the security-relevant request parameters are not bound.
    runtime.grant_human_approval(
        dispatch_id=dispatch.receipt_id,
        effect=original_request["effect"],
        approver="reviewer",
        reason="Approve payment of 10 to Alice only.",
    )

    decision = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect=mutated_request["effect"],
    )

    assert decision.allowed is False, (
        "approval for payment(amount=10, recipient=Alice) was reused for "
        "payment(amount=1000, recipient=Bob) because only the effect class "
        "is represented at authorization time"
    )
