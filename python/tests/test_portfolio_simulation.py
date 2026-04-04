from modules.venture import run_portfolio_simulation


def test_run_portfolio_simulation_smoke() -> None:
    result = run_portfolio_simulation()

    assert len(result.admissions) == 10
    assert any(d.decision == "accept" for d in result.admissions)
    assert len(result.gate_decisions) == 2
    assert result.allocation_decision.decision == "rebalance"

    assert len(result.final_state.active_projects) >= 1
    assert result.final_state.treasury >= 0
