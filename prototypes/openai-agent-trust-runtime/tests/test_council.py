from __future__ import annotations

from ls_agent_trust.council import (
    AGENT_PROFILES,
    CouncilRole,
    SevenAgentCouncil,
    agent_profile,
)
from ls_agent_trust.cross_thread import DispositionStatus


def test_seven_distinct_agent_profiles_exist() -> None:
    assert len(AGENT_PROFILES) == 7
    assert {profile.role for profile in AGENT_PROFILES} == set(CouncilRole)
    assert {profile.russian_name for profile in AGENT_PROFILES} == {
        "Агент Идея",
        "Агент Заказчик",
        "Агент Потребитель",
        "Агент Проектировщик",
        "Агент Исполнитель",
        "Агент Стабилизатор",
        "Агент Новатор",
    }


def test_profiles_preserve_authority_boundaries() -> None:
    executor = agent_profile(CouncilRole.EXECUTOR)
    stabilizer = agent_profile(CouncilRole.STABILIZER)
    innovator = agent_profile(CouncilRole.INNOVATOR)

    assert "deploy" in executor.prohibited
    assert "merge" in executor.prohibited
    assert "waive missing evidence" in stabilizer.prohibited
    assert "expand authority" in innovator.prohibited


def test_full_council_run_accepts_all_seven_stages() -> None:
    run = SevenAgentCouncil().run(
        "Create a safe evidence-aware protocol for durable AI-agent threads."
    )

    assert len(run.stages) == 7
    assert [stage.role for stage in run.stages] == list(SevenAgentCouncil.FLOW)
    assert all(
        stage.decision.status == DispositionStatus.ACCEPTED
        for stage in run.stages
    )
    assert run.trust_ledger_valid is True
    assert run.cross_thread_audit_valid is True
    assert "HOLD unless all conformance tests pass" in run.final_verdict


def test_council_output_is_machine_readable() -> None:
    run = SevenAgentCouncil().run("Build the smallest safe demo.")
    payload = run.to_dict()

    assert payload["trajectory_id"].startswith("project:")
    assert payload["stages"][0]["role"] == "idea"
    assert payload["stages"][-1]["role"] == "innovator"
    assert payload["cross_thread_audit_valid"] is True
