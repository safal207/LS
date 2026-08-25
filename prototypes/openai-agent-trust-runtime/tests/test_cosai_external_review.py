from __future__ import annotations

from ls_agent_trust import TrustRuntime


def test_recovery_revalidates_authority_after_parent_revocation() -> None:
    """CoSAI #158: carried-forward scope must not outlive its parent grant."""

    # Disable the separate human-approval gate so this fixture isolates authority
    # freshness rather than passing because deploy is protected by default.
    runtime = TrustRuntime(protected_effects=())
    original = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Deploy Agent instance-1",
        task="Deploy the reviewed release",
        authority_scope=("deploy",),
    )

    # Parent/policy authority changes after D1 was issued. The recorded maximum
    # scope remains unchanged, but current authority no longer admits deploy.
    runtime.revoke_authority(original.receipt_id, effect="deploy")

    replacement = runtime.recover_dispatch(
        original.receipt_id,
        replacement_agent="Deploy Agent instance-2",
    )
    assert replacement.authority_scope == original.authority_scope

    result = runtime.submit_result(
        dispatch_id=replacement.receipt_id,
        agent="Deploy Agent instance-2",
        status="COMPLETED",
        summary="Recovery worker completed the delegated task.",
        evidence=("cosai:authority-revalidation-vector",),
    )
    decision = runtime.authorize_effect(
        dispatch_id=replacement.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="deploy",
    )

    assert decision.allowed is False
    assert decision.reason == "authority was revoked or is no longer current"


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

    approval = runtime.grant_human_approval(
        dispatch_id=dispatch.receipt_id,
        effect=original_request["effect"],
        effect_request=original_request,
        approver="reviewer",
        reason="Approve payment of 10 to Alice only.",
    )
    assert approval.effect_request_digest

    decision = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect=mutated_request["effect"],
        effect_request=mutated_request,
    )

    assert decision.allowed is False
    assert decision.effect_request_digest != approval.effect_request_digest
