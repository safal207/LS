import json
from pathlib import Path

from scripts.run_pcg_evaluation import evaluate_sessions, load_sessions
from scripts.run_pcg_red_team import evaluate_scenario, load_json
from scripts.run_pcg_red_team_suite import evaluate_suite, load_suite


FIXTURE_DIR = Path("examples/personal_cognitive_garden")


def test_pcg_red_team_blocks_employer_private_graph_request():
    scenario = load_json(FIXTURE_DIR / "red_team_employer_surveillance_request.json")

    result = evaluate_scenario(scenario)

    assert result["decision"] == "BLOCK"
    assert result["reason"] == "PRIVATE_GRAPH_ACCESS_REQUEST"
    assert result["external_action_allowed"] is False
    assert "private_goals" in result["blocked_requested_fields"]
    assert "weak_skill_map" in result["blocked_requested_fields"]
    assert "private_reflections" in result["blocked_requested_fields"]


def test_pcg_red_team_suite_covers_core_anti_surveillance_boundaries():
    scenarios = load_suite(FIXTURE_DIR / "red_team_suite.json")

    report = evaluate_suite(scenarios)

    assert report["total_scenarios"] == 10
    assert report["passed"] == 10
    assert report["failed"] == 0
    assert report["pass_rate"] == 1.0
    assert report["decision_counts"]["BLOCK"] >= 5
    assert report["decision_counts"]["HUMAN_REVIEW"] >= 2
    assert report["decision_counts"]["LIMITED_CONSENTED_EXPORT"] >= 2


def test_pcg_red_team_suite_blocks_sensitive_third_party_exports():
    scenarios = load_suite(FIXTURE_DIR / "red_team_suite.json")
    report = evaluate_suite(scenarios)

    blocked_ids = {row["scenario_id"] for row in report["rows"] if row["decision"] == "BLOCK"}

    assert "pcg_red_team_001_employer_private_graph_request" in blocked_ids
    assert "pcg_red_team_002_manager_weak_skill_map" in blocked_ids
    assert "pcg_red_team_003_recruiter_growth_score" in blocked_ids
    assert "pcg_red_team_004_platform_training_data" in blocked_ids
    assert "pcg_red_team_005_rejected_updates_export" in blocked_ids


def test_pcg_red_team_suite_allows_only_limited_consented_non_sensitive_exports():
    scenarios = load_suite(FIXTURE_DIR / "red_team_suite.json")
    report = evaluate_suite(scenarios)

    allowed_rows = [row for row in report["rows"] if row["external_action_allowed"] is True]

    assert {row["decision"] for row in allowed_rows} == {"LIMITED_CONSENTED_EXPORT"}
    assert {row["scenario_id"] for row in allowed_rows} == {
        "pcg_red_team_007_user_portfolio_export",
        "pcg_red_team_010_public_artifacts_request",
    }


def test_pcg_evaluation_harness_matches_fixture_expectations():
    sessions = load_sessions(FIXTURE_DIR / "evaluation_sessions.json")

    report = evaluate_sessions(sessions)

    assert report["version"] == "0.2"
    assert report["total"] == 14
    assert report["developmental_accuracy"] == 1.0
    assert report["false_positive_count"] == 0
    assert report["false_negative_count"] == 0
    assert all(row["developmental_match"] for row in report["rows"])


def test_pcg_evaluation_v02_contains_false_positive_traps():
    sessions = load_sessions(FIXTURE_DIR / "evaluation_sessions.json")

    report = evaluate_sessions(sessions)
    trap_rows = [row for row in report["rows"] if row["trap_type"] != "none"]

    assert len(trap_rows) >= 6
    assert all(row["expected_developmental"] is False for row in trap_rows)
    assert all(row["predicted_developmental"] is False for row in trap_rows)
    assert {row["expected_class"] for row in trap_rows} >= {
        "emotional_support",
        "administrative",
        "execution",
        "noise",
    }


def test_pcg_evaluation_v02_reports_class_distribution():
    sessions = load_sessions(FIXTURE_DIR / "evaluation_sessions.json")

    report = evaluate_sessions(sessions)

    assert report["class_counts"]["emotional_support"] == 2
    assert report["class_counts"]["administrative"] == 2
    assert report["class_counts"]["decision_clarification"] == 2
    assert report["class_counts"]["skill_building"] == 2
    assert report["class_counts"]["capital_compounding"] == 2
    assert report["class_counts"]["execution"] == 2
    assert report["class_counts"]["noise"] == 2


def test_pcg_proposed_and_accepted_updates_follow_core_governance_invariants():
    proposed = load_json(FIXTURE_DIR / "proposed_update.json")
    accepted_graph = load_json(FIXTURE_DIR / "accepted_graph_state.json")
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


def test_gateway_to_garden_before_after_has_accepted_and_rejected_outcomes():
    example = load_json(FIXTURE_DIR / "gateway_to_garden_before_after.json")
    cases = example["cases"]

    assert len(cases) == 2
    assert {case["human_review"]["decision"] for case in cases} == {"accept", "reject"}
    assert {case["after_review"]["durable_state_allowed"] for case in cases} == {True, False}
    assert all(case["ls_gateway_decision"]["external_action_allowed"] is False for case in cases)
    assert all(case["pcg_proposal"]["sharing_scope"] == "private" for case in cases)
    assert "No benchmark claim is made by this example." in example["invariants"]


def test_pcg_quick_start_documents_minimal_runner_commands():
    quick_start = Path("docs/PERSONAL_COGNITIVE_GARDEN_QUICK_START.md").read_text(encoding="utf-8")

    assert "python scripts/run_personal_cognitive_garden_demo.py" in quick_start
    assert "python scripts/run_personal_cognitive_garden_demo.py --json" in quick_start
    assert "../README.md#quick-start" in quick_start

    for field in [
        "session_id",
        "session_type",
        "development_class",
        "is_developmental",
        "human_skill_delta",
        "capital_effect",
        "practice_needed",
        "compounding_score",
        "proposed_status",
        "review_decision",
        "reviewed_by",
        "accepted_nodes",
    ]:
        assert f"`{field}`" in quick_start


def test_pcg_fixture_json_is_machine_readable():
    for path in [
        FIXTURE_DIR / "red_team_employer_surveillance_request.json",
        FIXTURE_DIR / "red_team_suite.json",
        FIXTURE_DIR / "evaluation_sessions.json",
        FIXTURE_DIR / "proposed_update.json",
        FIXTURE_DIR / "accepted_graph_state.json",
        FIXTURE_DIR / "gateway_to_garden_before_after.json",
    ]:
        with path.open("r", encoding="utf-8") as file:
            json.load(file)
