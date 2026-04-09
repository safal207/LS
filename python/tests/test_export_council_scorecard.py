from __future__ import annotations

import json
from pathlib import Path

from tools.export_council_scorecard import export_scorecard


def _write_ledger(path: Path, *, cycle_id: str, model_id: str, model_type: str, route: str, success: bool, resonance: float, network: float, score: float) -> None:
    payload = {
        "cycle_id": cycle_id,
        "timestamp": "2026-04-08T06:30:00Z",
        "participants": [
            {
                "model_id": model_id,
                "model_type": model_type,
            }
        ],
        "final_decision": {"selected_route": route},
        "outcome": {
            "success": success,
            "receiver_resonance_score": resonance,
            "network_improvement": network,
        },
        "attribution": {
            "best_contributor_model_id": model_id,
            "best_contributor_score": score,
            "contribution_breakdown": [
                {
                    "model_id": model_id,
                    "total_contribution_score": score,
                }
            ],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_export_scorecard_from_real_ledgers(tmp_path: Path) -> None:
    input_dir = tmp_path / "council-ledger"
    quality_dir = tmp_path / "council-quality"
    output_path = tmp_path / "councilScorecard.json"
    input_dir.mkdir()
    quality_dir.mkdir()
    _write_ledger(input_dir / "a.json", cycle_id="cycle-a", model_id="local-qwen", model_type="local", route="route_a", success=True, resonance=0.82, network=0.17, score=0.86)
    _write_ledger(input_dir / "b.json", cycle_id="cycle-b", model_id="gpt-web", model_type="web", route="route_b", success=False, resonance=0.61, network=0.03, score=0.51)
    (quality_dir / "cycle-a.json").write_text(json.dumps({"cycle_id": "cycle-a", "quality_score": 0.93}), encoding="utf-8")
    (quality_dir / "cycle-b.json").write_text(json.dumps({"cycle_id": "cycle-b", "quality_score": 0.41}), encoding="utf-8")

    payload = export_scorecard(input_dir, output_path)

    assert payload["source"] == "artifact"
    assert payload["summary"]["ledgers"] == 2
    assert payload["summary"]["avg_quality"] == 67.0
    assert payload["summary"]["top_contributor"] in {"local-qwen", "gpt-web"}
    assert output_path.exists()
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["summary"]["ledgers"] == 2
    assert written["bars"]["route_wins"]


def test_export_scorecard_keeps_existing_snapshot_when_empty(tmp_path: Path) -> None:
    input_dir = tmp_path / "council-ledger"
    output_path = tmp_path / "councilScorecard.json"
    input_dir.mkdir()
    output_path.write_text(json.dumps({"source": "artifact", "summary": {"ledgers": 7}}), encoding="utf-8")

    payload = export_scorecard(input_dir, output_path, keep_existing_on_empty=True)

    assert payload["summary"]["ledgers"] == 7
    assert json.loads(output_path.read_text(encoding="utf-8"))["summary"]["ledgers"] == 7


def test_export_scorecard_normalizes_low_signal_labels(tmp_path: Path) -> None:
    input_dir = tmp_path / "council-ledger"
    output_path = tmp_path / "councilScorecard.json"
    input_dir.mkdir()
    _write_ledger(
        input_dir / "a.json",
        cycle_id="cycle-a",
        model_id="callable:unknown",
        model_type="local",
        route="unknown",
        success=True,
        resonance=0.4,
        network=0.0,
        score=0.8,
    )

    payload = export_scorecard(input_dir, output_path)

    assert payload["summary"]["top_contributor"] == "local-council-llm"
    assert payload["bars"]["route_wins"][0]["label"] == "route-pending"
