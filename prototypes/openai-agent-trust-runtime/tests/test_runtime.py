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

    approval = runtime.grant_human_approval(
        dispatch_id=dispatch.receipt_id,
        effect="merge",
        approver="alex",
        reason="Reviewed the evidence and residual risk.",
    )
    assert approval.result_receipt_id == result.receipt_id

    allowed = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="merge",
    )
    assert allowed.allowed is True


def test_human_approval_requires_completed_result() -> None:
    runtime = TrustRuntime()
    dispatch = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Safety Reviewer",
        task="Review the exact patch evidence",
        authority_scope=("merge",),
    )

    with pytest.raises(TrustViolation, match="requires a completed result"):
        runtime.grant_human_approval(
            dispatch_id=dispatch.receipt_id,
            effect="merge",
            approver="alex",
            reason="Premature approval must fail closed.",
        )


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


def test_recovery_cannot_relax_constraints_or_expand_authority() -> None:
    runtime = TrustRuntime()
    original = runtime.issue_dispatch(
        parent_agent="Coordinator",
        child_agent="Research Agent instance-1",
        task="Inspect the dependency contract",
        constraints=("read only",),
        authority_scope=("read_repository",),
    )

    with pytest.raises(TrustViolation, match="original constraints"):
        runtime.issue_dispatch(
            parent_agent="Recovery coordinator",
            child_agent="Research Agent instance-2",
            task=original.task,
            constraints=(),
            authority_scope=original.authority_scope,
            supersedes=original.receipt_id,
        )

    with pytest.raises(TrustViolation, match="original authority scope"):
        runtime.issue_dispatch(
            parent_agent="Recovery coordinator",
            child_agent="Research Agent instance-2",
            task=original.task,
            constraints=original.constraints,
            authority_scope=("read_repository", "merge"),
            supersedes=original.receipt_id,
        )


def test_terminal_dispatch_cannot_be_recovered() -> None:
    runtime = TrustRuntime()
    dispatch, _result = completed_dispatch(runtime)

    with pytest.raises(TrustViolation, match="terminal dispatch"):
        runtime.recover_dispatch(
            dispatch.receipt_id,
            replacement_agent="Safety Reviewer instance-2",
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


def test_empty_protected_effect_set_is_respected() -> None:
    runtime = TrustRuntime(protected_effects=())
    dispatch, result = completed_dispatch(runtime)

    decision = runtime.authorize_effect(
        dispatch_id=dispatch.receipt_id,
        result_receipt_id=result.receipt_id,
        effect="merge",
    )
    assert decision.allowed is True


def test_hash_chain_detects_tampering() -> None:
    runtime = TrustRuntime()
    completed_dispatch(runtime)
    assert runtime.verify_ledger() is True

    tampered = copy.deepcopy(list(runtime.ledger))
    tampered[0]["payload"]["task"] = "silently changed task"
    assert TrustRuntime.verify_records(tampered) is False


def test_unanchored_hash_chain_cannot_detect_suffix_truncation() -> None:
    runtime = TrustRuntime()
    completed_dispatch(runtime)

    truncated_prefix = copy.deepcopy(list(runtime.ledger[:-1]))
    assert TrustRuntime.verify_records(truncated_prefix) is True
