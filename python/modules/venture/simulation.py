from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .pfc import IdeaObject, PFCDecision, PortfolioFlowController, PortfolioState, ValidationRecord


@dataclass(frozen=True)
class SimulationResult:
    admissions: List[PFCDecision]
    gate_decisions: List[PFCDecision]
    allocation_decision: PFCDecision
    final_state: PortfolioState


def build_sample_inputs(idea_count: int = 10) -> tuple[List[IdeaObject], List[ValidationRecord]]:
    ideas = [
        IdeaObject(
            idea_id=f"idea_{i}",
            title=f"Startup {i}",
            upside=300_000 + i * 25_000,
            p_success=0.1 + 0.05 * i,
            execution_risk_penalty=5_000,
        )
        for i in range(idea_count)
    ]
    validations = [
        ValidationRecord(
            validation_record_id=f"vr_{i}",
            idea_id=idea.idea_id,
            project_type="saas_b2b",
            signup_rate=0.05 + 0.02 * i,
            cac_proxy=20 - 2 * i,
            time_to_mvp_days=30 - 2 * i,
        )
        for i, idea in enumerate(ideas)
    ]
    return ideas, validations


def run_portfolio_simulation(
    *,
    treasury: float = 200_000.0,
    required_capital: float = 20_000.0,
    gate_metrics: Sequence[Dict[str, float]] | None = None,
    idea_count: int = 10,
) -> SimulationResult:
    state = PortfolioState(treasury=treasury)
    controller = PortfolioFlowController(state)

    ideas, validations = build_sample_inputs(idea_count=idea_count)

    admissions: List[PFCDecision] = []
    for idea, validation in zip(ideas, validations):
        admissions.append(controller.evaluate_admission(idea, validation, required_capital=required_capital))

    active_ids = list(state.active_projects.keys())
    gate_metrics = list(
        gate_metrics
        or [
            {"activation_rate": 0.3, "retention_d7": 0.25, "retention_d30": 0.15},
            {"activation_rate": 0.2, "retention_d7": 0.15, "retention_d30": 0.05},
        ]
    )

    gate_decisions: List[PFCDecision] = []
    for project_id, metrics in zip(active_ids, gate_metrics):
        gate_decisions.append(controller.evaluate_gate(project_id, stage="early_pmf", metrics=metrics))

    allocation_decision = controller.rebalance_allocations()
    return SimulationResult(
        admissions=admissions,
        gate_decisions=gate_decisions,
        allocation_decision=allocation_decision,
        final_state=state,
    )
