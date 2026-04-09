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
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(dashboard, "COUNCIL_QUALITY_DIR", quality_dir)

    status, payload = dashboard.preview_council_quality_artifact()

    assert status == 200
    assert payload["cycle_id"] == "cycle-001"
    assert payload["quality_score"] == 0.84
    assert payload["relation_adjusted_quality_score"] == 0.71
    assert payload["selected_route"] == "route-a"
    assert payload["best_contributor_model_id"] == "local-qwen"
    assert payload["relation_safety_score"] == 0.48
    assert payload["recommended_mode"] == "validate_before_solve"
    assert payload["liminalqa_published"] is True
    assert payload["liminalqa_status_code"] == 200
