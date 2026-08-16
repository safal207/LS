from verified_transition_loop import OutcomeVerdict, TransitionVerdict
from verified_transition_loop.deployment_demo import run_deployment_demo


def test_healthy_deployment_commits_without_rollback():
    result = run_deployment_demo(fail_health=False)
    assert result.deploy_authorization.verdict is TransitionVerdict.AUTHORIZE
    assert result.deploy_outcome.verdict is OutcomeVerdict.COMMIT
    assert result.rollback_authorization is None
    assert result.rollback_outcome is None
    assert result.final_state == f"production:{'b' * 40}"
    assert result.ledger_valid


def test_health_failure_requests_rollback_and_restores_previous_state():
    result = run_deployment_demo(fail_health=True)
    assert result.deploy_outcome.verdict is OutcomeVerdict.ROLLBACK
    assert "INVARIANT_FAILED:health_ok" in result.deploy_outcome.reason_codes
    assert result.rollback_authorization is not None
    assert result.rollback_authorization.verdict is TransitionVerdict.AUTHORIZE
    assert result.rollback_outcome is not None
    assert result.rollback_outcome.verdict is OutcomeVerdict.COMMIT
    assert result.final_state == f"production:{'a' * 40}"
    assert result.ledger_valid


def test_demo_is_deterministic_for_same_inputs():
    left = run_deployment_demo(fail_health=True)
    right = run_deployment_demo(fail_health=True)
    assert left.deploy_authorization.decision_id == right.deploy_authorization.decision_id
    assert left.deploy_outcome.outcome_id == right.deploy_outcome.outcome_id
    assert left.rollback_authorization is not None
    assert right.rollback_authorization is not None
    assert left.rollback_authorization.decision_id == right.rollback_authorization.decision_id
    assert left.ledger_head == right.ledger_head


def test_candidate_commit_changes_receipts_and_final_state():
    first = run_deployment_demo(fail_health=False, candidate_sha="b" * 40)
    second = run_deployment_demo(fail_health=False, candidate_sha="c" * 40)
    assert first.deploy_authorization.decision_id != second.deploy_authorization.decision_id
    assert first.deploy_outcome.outcome_id != second.deploy_outcome.outcome_id
    assert first.final_state != second.final_state
