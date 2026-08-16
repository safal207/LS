from verified_transition_loop import OutcomeVerdict, UseTimeVerdict
from verified_transition_loop.deployment_demo import run_deployment_demo


def test_healthy_deployment_commits_after_use_time_revalidation():
    result = run_deployment_demo(fail_health=False)
    assert result.deploy_use.verdict is UseTimeVerdict.EXECUTE
    assert result.execution_performed
    assert result.deploy_outcome is not None
    assert result.deploy_outcome.verdict is OutcomeVerdict.COMMIT
    assert result.rollback_outcome is None
    assert result.final_state.endswith("b" * 40)
    assert result.ledger_valid


def test_health_failure_rolls_back_through_second_verified_transition():
    result = run_deployment_demo(fail_health=True)
    assert result.deploy_use.verdict is UseTimeVerdict.EXECUTE
    assert result.deploy_outcome is not None
    assert result.deploy_outcome.verdict is OutcomeVerdict.ROLLBACK
    assert result.rollback_authorization is not None
    assert result.rollback_use is not None
    assert result.rollback_use.verdict is UseTimeVerdict.EXECUTE
    assert result.rollback_execution_performed
    assert result.rollback_outcome is not None
    assert result.rollback_outcome.verdict is OutcomeVerdict.COMMIT
    assert result.final_state.endswith("a" * 40)
    assert result.ledger_valid


def test_policy_drift_before_execute_blocks_without_execution():
    result = run_deployment_demo(fail_health=False, drift_before_execute=True)
    assert result.deploy_authorization.verdict.value == "AUTHORIZE"
    assert result.deploy_use.verdict is UseTimeVerdict.BLOCK
    assert "POLICY_REF_CHANGED" in result.deploy_use.reason_codes
    assert not result.execution_performed
    assert result.deploy_outcome is None
    assert result.final_state.endswith("a" * 40)
    assert result.ledger_valid


def test_demo_is_deterministic():
    first = run_deployment_demo(fail_health=True)
    second = run_deployment_demo(fail_health=True)
    assert first.deploy_authorization.decision_id == second.deploy_authorization.decision_id
    assert first.deploy_use.use_id == second.deploy_use.use_id
    assert first.deploy_outcome is not None and second.deploy_outcome is not None
    assert first.deploy_outcome.outcome_id == second.deploy_outcome.outcome_id
    assert first.ledger_head == second.ledger_head
