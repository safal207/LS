import json

from scripts.run_pcg_evaluation import evaluate_sessions, load_sessions
from scripts.run_pcg_red_team import evaluate_scenario, load_json


def test_pcg_red_team_blocks_employer_private_graph_request():
    scenario = load_json("examples/personal_cognitive_garden/red_team_employer_surveillance_request.json")

    result = evaluate_scenario(scenario)

    assert result["decision"] == "BLOCK"
    assert result["reason"] == "PRIVATE_GRAPH_ACCESS_REQUEST"
    assert result["external_action_allowed"] is False
    assert "private_goals" in result["blocked_requested_fields"]
    assert "weak_skill_map" in result["blocked_requested_fields"]
    assert "private_reflections" in result["blocked_requested_fields"]


def test_pcg_evaluation_harness_matches_fixture_expectations():
    sessions = load_sessions("examples/personal_cognitive_garden/evaluation_sessions.json")

    report = evaluate_sessions(sessions)

    assert report["total"] == 7
    assert report["developmental_accuracy"] == 1.0
    assert all(row["developmental_match"] for row in report["rows"])


def test_pcg_proposed_and_accepted_updates_follow_core_governance_invariants():
    proposed = load_json("examples/personal_cognitive_garden/proposed_update.json")
    accepted_graph = load_json("examples/personal_cognitive_garden/accepted_graph_state.json")
    accepted = accepted_graph["accepted_updates"][0]

    assert proposed["status"] == "proposed"
    assert proposed["requires_human_review"] is True
    assert proposed["governance"]["durable_state_allowed"] is False
    assert proposed["governance"]["external_action_allowed"] is False
    assert proposed["governance"]["sharing_scope"] == "private"

    assert accepted["status"] == "accepted"
    assert accepted["requires_human_review"] is True
    assert accepted["review"]["decision"] == "accept"
    assert accepted["governance"]["durable_state_allowed"] is True
    assert accepted["governance"]["external_action_allowed"] is False
    assert accepted["governance"]["sharing_scope"] == "private"


def test_pcg_fixture_json_is_machine_readable():
    for path in [
        "examples/personal_cognitive_garden/red_team_employer_surveillance_request.json",
        "examples/personal_cognitive_garden/evaluation_sessions.json",
        "examples/personal_cognitive_garden/proposed_update.json",
        "examples/personal_cognitive_garden/accepted_graph_state.json",
    ]:
        with open(path, "r", encoding="utf-8") as file:
            json.load(file)
