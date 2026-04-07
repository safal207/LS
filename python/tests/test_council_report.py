from __future__ import annotations

import json

from modules.cel import load_council_ledgers, summarize_council_ledgers


def test_load_council_ledgers_filters_invalid_files(tmp_path):
    valid = tmp_path / "a.json"
    valid.write_text(json.dumps({"cycle_id": "cycle-a", "timestamp": "2026-04-07T12:00:00Z"}), encoding="utf-8")
    invalid = tmp_path / "bad.json"
    invalid.write_text("{bad", encoding="utf-8")
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")

    ledgers = load_council_ledgers(tmp_path)

    assert len(ledgers) == 1
    assert ledgers[0]["cycle_id"] == "cycle-a"


def test_summarize_council_ledgers_builds_histograms_and_trends():
    ledgers = [
        {
            "cycle_id": "cycle-1",
            "task_id": "task-1",
            "timestamp": "2026-04-07T12:00:00Z",
            "participants": [
                {"model_id": "local-a", "model_type": "local"},
                {"model_id": "web-a", "model_type": "web"},
            ],
            "final_decision": {"selected_route": "route-a"},
            "outcome": {
                "success": True,
                "path_quality": 0.9,
                "network_improvement": 0.2,
                "operator_intervention_required": False,
                "operator_feedback_score": 0.85,
                "drift_detected": False,
                "receiver_resonance_score": 0.88,
            },
            "attribution": {
                "best_contributor_model_id": "local-a",
                "contribution_breakdown": [
                    {"model_id": "local-a", "total_contribution_score": 0.84},
                    {"model_id": "web-a", "total_contribution_score": 0.62},
                ],
            },
        },
        {
            "cycle_id": "cycle-2",
            "task_id": "task-2",
            "timestamp": "2026-04-07T12:05:00Z",
            "participants": [
                {"model_id": "local-a", "model_type": "local"},
                {"model_id": "web-b", "model_type": "web"},
            ],
            "final_decision": {"selected_route": "route-b"},
            "outcome": {
                "success": False,
                "path_quality": 0.6,
                "network_improvement": 0.05,
                "operator_intervention_required": True,
                "operator_feedback_score": 0.5,
                "drift_detected": True,
                "receiver_resonance_score": 0.42,
            },
            "attribution": {
                "best_contributor_model_id": "web-b",
                "contribution_breakdown": [
                    {"model_id": "local-a", "total_contribution_score": 0.33},
                    {"model_id": "web-b", "total_contribution_score": 0.58},
                ],
            },
        },
    ]

    report = summarize_council_ledgers(ledgers)

    assert report["ledger_count"] == 2
    assert report["summary"]["success_rate"] == 0.5
    assert report["summary"]["top_best_contributor_model_id"] in {"local-a", "web-b"}
    assert report["histograms"]["best_contributor_counts"][0]["value"] == 1.0
    assert report["histograms"]["route_wins"][0]["label"] in {"route-a", "route-b"}
    assert report["histograms"]["cumulative_contribution_scores"][0]["label"] == "local-a"
    assert len(report["trends"]["receiver_resonance"]) == 2
    assert report["trends"]["receiver_resonance"][0]["cycle_id"] == "cycle-1"
    assert len(report["trends"]["average_merit_score"]) == 2
