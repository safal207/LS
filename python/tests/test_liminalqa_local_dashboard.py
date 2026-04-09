from __future__ import annotations

import json
from pathlib import Path

from tools import liminalqa_local_dashboard as dashboard


def test_preview_council_quality_artifact_empty(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(dashboard, "COUNCIL_QUALITY_DIR", tmp_path / "council-quality")

    status, payload = dashboard.preview_council_quality_artifact()

    assert status == 404
    assert payload["error"] == "council-quality artifact not found"


def test_preview_council_quality_artifact_reads_latest(monkeypatch, tmp_path: Path) -> None:
    quality_dir = tmp_path / "council-quality"
    quality_dir.mkdir()
    path = quality_dir / "cycle-001.json"
    path.write_text(
        json.dumps(
            {
                "cycle_id": "cycle-001",
                "task_id": "task-001",
                "relational_episode_path": str(tmp_path / "relational-episodes" / "cycle-001.json"),
                "quality_score": 0.84,
                "relation_adjusted_quality_score": 0.71,
                "council_outcome": {
                    "selected_route": "route-a",
                    "success": True,
                    "receiver_resonance_score": 0.73,
                    "receiver_acceptance_label": "accepted",
                },
                "relational_field": {
                    "relation_safety_score": 0.48,
                    "recommended_mode": "validate_before_solve",
                    "dominant_signal": "tension",
                    "background_pressure": "handoff pressure",
                    "foreground_expression": "mixed signals",
                    "notes": ["Pause before approval"],
                },
                "operator_guidance": {
                    "risk_state": "watch",
                    "approval_posture": "evidence_check",
                    "route_strategy": "validate_current_route",
                    "requires_human_review": False,
                    "rerun_required": False,
                    "suggested_operator_action": "Validate intent before approval.",
                },
                "attribution": {
                    "best_contributor_model_id": "local-qwen",
                    "best_contributor_score": 0.91,
                },
                "cel": {
                    "contribution_records": [{"agent_id": "local-qwen"}],
                    "reputation_updates": [{"agent_id": "local-qwen"}],
                    "merit_updates": [{"model_id": "local-qwen", "merit_score": 0.88}],
                },
                "liminalqa": {
                    "published": True,
                    "status_code": 200,
                    "incident": {
                        "published": True,
                        "status_code": 202,
                    },
                },
                "operator_review": {
                    "decision": "approved",
                    "reviewer": "qa-operator",
                    "forced": False,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard, "COUNCIL_QUALITY_DIR", quality_dir)

    status, payload = dashboard.preview_council_quality_artifact()

    assert status == 200
    assert payload["cycle_id"] == "cycle-001"
    assert payload["relational_episode_path"].endswith("cycle-001.json")
    assert payload["quality_score"] == 0.84
    assert payload["relation_adjusted_quality_score"] == 0.71
    assert payload["selected_route"] == "route-a"
    assert payload["best_contributor_model_id"] == "local-qwen"
    assert payload["relation_safety_score"] == 0.48
    assert payload["recommended_mode"] == "validate_before_solve"
    assert payload["background_pressure"] == "handoff pressure"
    assert payload["foreground_expression"] == "mixed signals"
    assert payload["relational_notes"] == ["Pause before approval"]
    assert payload["risk_state"] == "watch"
    assert payload["approval_posture"] == "evidence_check"
    assert payload["route_strategy"] == "validate_current_route"
    assert payload["requires_human_review"] is False
    assert payload["rerun_required"] is False
    assert payload["suggested_operator_action"] == "Validate intent before approval."
    assert payload["operator_review_decision"] == "approved"
    assert payload["operator_review_reviewer"] == "qa-operator"
    assert payload["operator_review_forced"] is False
    assert payload["liminalqa_published"] is True
    assert payload["liminalqa_status_code"] == 200
    assert payload["liminalqa_incident_published"] is True
    assert payload["liminalqa_incident_status_code"] == 202


def test_preview_council_risk_queue_sorts_high_risk_first(monkeypatch, tmp_path: Path) -> None:
    quality_dir = tmp_path / "council-quality"
    quality_dir.mkdir()
    (quality_dir / "safe.json").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-safe",
                "quality_score": 0.9,
                "council_outcome": {"selected_route": "route-a"},
                "relational_field": {"recommended_mode": "collaborative_progress"},
                "operator_guidance": {"risk_state": "safe", "suggested_operator_action": "continue"},
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "repair.json").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-repair",
                "relation_adjusted_quality_score": 0.4,
                "council_outcome": {"selected_route": "route-b"},
                "relational_field": {"recommended_mode": "decompress_and_repair"},
                "operator_guidance": {"risk_state": "repair", "suggested_operator_action": "pause"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard, "COUNCIL_QUALITY_DIR", quality_dir)

    status, payload = dashboard.preview_council_risk_queue()

    assert status == 200
    assert payload["total"] == 2
    assert payload["items"][0]["cycle_id"] == "cycle-repair"
    assert payload["items"][1]["cycle_id"] == "cycle-safe"
    assert payload["items"][0]["review_status"] == "pending"


def test_build_council_analytics_counts_incidents(monkeypatch, tmp_path: Path) -> None:
    ledger_dir = tmp_path / "council-ledger"
    quality_dir = tmp_path / "council-quality"
    ledger_dir.mkdir()
    quality_dir.mkdir()
    (ledger_dir / "cycle-001.json").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-001",
                "timestamp": "2026-04-09T10:00:00Z",
                "participants": [{"model_id": "local-qwen", "model_type": "local"}],
                "final_decision": {"selected_route": "route-a"},
                "outcome": {"success": True, "receiver_resonance_score": 0.6, "network_improvement": 0.1},
                "attribution": {
                    "best_contributor_model_id": "local-qwen",
                    "best_contributor_score": 0.8,
                    "contribution_breakdown": [{"model_id": "local-qwen", "total_contribution_score": 0.8}],
                },
            }
        ),
        encoding="utf-8",
    )
    (quality_dir / "cycle-001.json").write_text(
        json.dumps(
            {
                "cycle_id": "cycle-001",
                "operator_guidance": {"risk_state": "repair"},
                "liminalqa": {"incident": {"published": True, "status_code": 202}},
                "operator_review": {"decision": "approved"},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard, "COUNCIL_LEDGER_DIR", ledger_dir)
    monkeypatch.setattr(dashboard, "COUNCIL_QUALITY_DIR", quality_dir)

    payload = dashboard.build_council_analytics()

    assert payload["ledgers"] == 1
    assert payload["risky_cycle_count"] == 1
    assert payload["incident_count"] == 1
    assert payload["reviewed_cycle_count"] == 1
    assert payload["approval_conversion_rate"] == 100.0
    assert payload["escalation_rate"] == 0.0
    assert payload["charts"]["incidentTrend"] == [{"label": "2026-04-09", "value": 1}]
