from __future__ import annotations

from modules.venture import (
    IdeaObject,
    PFCPPolicy,
    PortfolioFlowController,
    PortfolioFlowError,
    PortfolioState,
    ValidationRecord,
    WIPLimits,
)


def _make_controller(*, treasury: float = 100_000.0, max_incubation: int = 2) -> PortfolioFlowController:
    policy = PFCPPolicy(
        dynamic_cutoff_base=50_000.0,
        min_runway_by_project_type={"default": 8_000.0, "saas_b2b": 20_000.0},
        wip_limits=WIPLimits(
            max_active_projects_total=10,
            max_active_projects_incubation=max_incubation,
            max_active_projects_scale=3,
        ),
    )
    return PortfolioFlowController(state=PortfolioState(treasury=treasury), policy=policy)


def test_admission_accept_creates_project_and_ledger_event() -> None:
    controller = _make_controller()
    idea = IdeaObject("idea_1", "AI QA", upside=350_000.0, p_success=0.5, execution_risk_penalty=5_000)
    vr = ValidationRecord("vr_1", "idea_1", "saas_b2b")

    decision = controller.evaluate_admission(idea, vr, required_capital=25_000.0, trace_id="t1")

    assert decision.decision == "accept"
    assert decision.expected_value is not None and decision.expected_value > decision.dynamic_cutoff
    assert "project_idea_1" in controller.state.active_projects
    assert controller.state.treasury == 75_000.0
    assert any(e.event_type == "PFC_ADMISSION_DECIDED" for e in controller.list_ledger_events())


def test_admission_queue_when_wip_limit_reached() -> None:
    controller = _make_controller(max_incubation=1)
    idea1 = IdeaObject("idea_1", "P1", upside=300_000.0, p_success=0.5)
    idea2 = IdeaObject("idea_2", "P2", upside=300_000.0, p_success=0.5)
    vr1 = ValidationRecord("vr_1", "idea_1", "saas_b2b")
    vr2 = ValidationRecord("vr_2", "idea_2", "saas_b2b")

    d1 = controller.evaluate_admission(idea1, vr1, required_capital=20_000.0)
    d2 = controller.evaluate_admission(idea2, vr2, required_capital=20_000.0)

    assert d1.decision == "accept"
    assert d2.decision == "queue"
    assert "idea_2" in controller.state.admission_queue


def test_gate_freeze_and_kill_generate_ledger_events() -> None:
    controller = _make_controller()
    idea = IdeaObject("idea_1", "AI QA", upside=500_000.0, p_success=0.5)
    vr = ValidationRecord("vr_1", "idea_1", "saas_b2b")
    controller.evaluate_admission(idea, vr, required_capital=20_000.0)
    project_id = "project_idea_1"

    freeze_decision = controller.evaluate_gate(
        project_id,
        stage="early_pmf",
        metrics={"activation_rate": 0.24, "retention_d7": 0.19, "retention_d30": 0.02},
    )
    assert freeze_decision.decision == "freeze"

    # manually move back to scale state to validate kill path
    controller.state.active_projects[project_id].stage = "scale"
    controller.state.active_projects[project_id].frozen = False
    kill_decision = controller.evaluate_gate(
        project_id,
        stage="scale",
        metrics={"ltv_cac": 1.2, "payback_period_months": 20.0, "gross_margin": 0.2},
    )

    assert kill_decision.decision == "kill"
    events = [e.event_type for e in controller.list_ledger_events()]
    assert "PFC_PROJECT_FROZEN" in events
    assert "PFC_PROJECT_KILLED" in events


def test_reprioritization_respects_focus_window() -> None:
    controller = _make_controller()
    idea = IdeaObject("idea_1", "AI QA", upside=400_000.0, p_success=0.5)
    vr = ValidationRecord("vr_1", "idea_1", "saas_b2b")
    controller.evaluate_admission(idea, vr, required_capital=20_000.0)

    try:
        controller.reprioritize_project("project_idea_1")
    except PortfolioFlowError as exc:
        assert exc.code == "FOCUS_WINDOW_ACTIVE"
    else:
        raise AssertionError("Expected focus window error")


def test_trace_project_returns_end_to_end_chain() -> None:
    controller = _make_controller()
    idea = IdeaObject("idea_1", "AI QA", upside=500_000.0, p_success=0.5)
    vr = ValidationRecord("vr_1", "idea_1", "saas_b2b")
    controller.evaluate_admission(idea, vr, required_capital=20_000.0)
    controller.evaluate_gate(
        "project_idea_1",
        stage="early_pmf",
        metrics={"activation_rate": 0.4, "retention_d7": 0.3, "retention_d30": 0.2},
    )
    controller.rebalance_allocations()

    chain = controller.trace_project("project_idea_1")
    kinds = {c.decision_type for c in chain}
    assert "admission" in kinds
    assert "gate" in kinds
