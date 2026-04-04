from modules.venture.simulation import run_portfolio_simulation


def main() -> None:
    result = run_portfolio_simulation()

    for decision in result.admissions:
        print(
            f"Admission {decision.entity_id}: {decision.decision}, "
            f"reasons={decision.reasons}, expected_value={decision.expected_value}"
        )

    for decision in result.gate_decisions:
        print(f"Gate {decision.entity_id}: {decision.decision}, reasons={decision.reasons}")

    print(
        f"Rebalance decision: {result.allocation_decision.decision}, "
        f"reasons={result.allocation_decision.reasons}"
    )

    print("\n--- Final Portfolio State ---")
    print(f"Treasury: {result.final_state.treasury}")
    for project_id, project in result.final_state.active_projects.items():
        print(
            f"{project_id}: stage={project.stage}, budget={project.budget}, "
            f"frozen={project.frozen}, killed={project.killed}"
        )


if __name__ == "__main__":
    main()
