from __future__ import annotations

import copy

import pytest

from ls_agent_trust import TrustRuntime, TrustViolation


def completed_dispatch(
    runtime: TrustRuntime,
    *,
    authority_scope: tuple[str, ...] = ("merge",),
):
    dispatch = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Safety Reviewer",
        task="Review the exact patch evidence",
        constraints=("advisory only",),
        authority_scope=authority_scope,
    )
    result = runtime.submit_result(
        dispatch_id=dispatch.receipt_id,
        agent="Safety Reviewer",
        status="COMPLETED",
        summary="The bounded evidence is internally consistent.",
        evidence=("pytest:test_regression",),
    )
    return dispatch, result


def test_protected_effect_requires_human_approval() -> None:
    runtime = TrustRuntime()
    dispatch, result = completed_dispatch(runtime)

    blocked = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="merge",
    )
    assert blocked.allowed is False
    assert blocked.reason == "protected effect requires human approval"

    runtime.grant_human_approval(
        dispatch_id=dispatch.receipt_id,
        effect="merge",
        approver="alex",
        reason="Reviewed the evidence and residual risk.",
    )
    allowed = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="merge",
    )
    assert allowed.allowed is True


def test_wrong_agent_cannot_submit_result() -> None:
    runtime = TrustRuntime()
    dispatch = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="QA Agent",
        task="Validate the patch",
    )

    with pytest.raises(TrustViolation, match="dispatched child agent"):
        runtime.submit_result(
            dispatch_id=dispatch.receipt_id,
            agent="Developer Agent",
            status="COMPLETED",
            summary="Looks good",
            evidence=("fake",),
        )


def test_completed_result_requires_evidence() -> None:
    runtime = TrustRuntime()
    dispatch = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="QA Agent",
        task="Validate the patch",
    )

    with pytest.raises(TrustViolation, match="require at least one evidence"):
        runtime.submit_result(
            dispatch_id=dispatch.receipt_id,
            agent="QA Agent",
            status="COMPLETED",
            summary="Looks good",
        )


def test_recovery_supersedes_stale_dispatch() -> None:
    runtime = TrustRuntime()
    original = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Research Agent instance-1",
        task="Inspect the dependency contract",
        authority_scope=("read_repository",),
    )
    replacement = runtime.recover_dispatch(
        original.receipt_id,
        replacement_agent="Research Agent instance-2",
    )

    assert replacement.supersedes == original.receipt_id
    with pytest.raises(TrustViolation, match="superseded dispatch"):
        runtime.submit_result(
            dispatch_id=original.receipt_id,
            agent="Research Agent instance-1",
            status="COMPLETED",
            summary="Stale work",
            evidence=("stale",),
        )


def test_effect_outside_declared_scope_is_blocked() -> None:
    runtime = TrustRuntime()
    dispatch, result = completed_dispatch(runtime, authority_scope=("run_tests",))
    decision = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="merge",
    )
    assert decision.allowed is False
    assert decision.reason == "effect is outside the delegated authority scope"


def test_hash_chain_detects_tampering() -> None:
    runtime = TrustRuntime()
    completed_dispatch(runtime)
    assert runtime.verify_ledger() is True

    tampered = copy.deepcopy(list(runtime.ledger))
    tampered[0]["payload"]["task"] = "silently changed task"
    assert TrustRuntime.verify_records(tampered) is False
