from __future__ import annotations

import json
from pathlib import Path

from tools import build_fellowship_dataset


def test_build_dataset_copies_council_quality_artifacts(monkeypatch, tmp_path: Path) -> None:
    ledger_dir = tmp_path / "council-ledger"
    quality_dir = tmp_path / "council-quality"
    output_dir = tmp_path / "fellowship-dataset"
    output_ledger_dir = output_dir / "ledgers"
    output_quality_dir = output_dir / "council-quality"
    output_trace_dir = output_dir / "traces"
    ledger_dir.mkdir()
    quality_dir.mkdir()

    ledger_payload = {
        "cycle_id": "cycle-001",
        "goal": {"summary": "real goal"},
        "participants": [{"model_id": "local-qwen"}],
        "final_decision": {"selected_route": "route-a"},
        "outcome": {"success": True, "receiver_resonance_score": 0.8},
        "attribution": {"best_contributor_score": 0.9},
    }
    quality_payload = {
        "cycle_id": "cycle-001",
        "quality_score": 0.83,
        "liminalqa": {"published": True, "status_code": 200},
        "operator_guidance": {"risk_state": "repair"},
        "liminalqa": {
            "published": True,
            "status_code": 200,
            "incident": {"published": True, "status_code": 200},
        },
    }
    (ledger_dir / "cycle-001.json").write_text(json.dumps(ledger_payload), encoding="utf-8")
    (quality_dir / "cycle-001.json").write_text(json.dumps(quality_payload), encoding="utf-8")

    monkeypatch.setattr(build_fellowship_dataset, "LEDGER_DIR", ledger_dir)
    monkeypatch.setattr(build_fellowship_dataset, "QUALITY_DIR", quality_dir)
    monkeypatch.setattr(build_fellowship_dataset, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(build_fellowship_dataset, "OUTPUT_LEDGER_DIR", output_ledger_dir)
    monkeypatch.setattr(build_fellowship_dataset, "OUTPUT_QUALITY_DIR", output_quality_dir)
    monkeypatch.setattr(build_fellowship_dataset, "OUTPUT_TRACE_DIR", output_trace_dir)

    manifest = build_fellowship_dataset.build_dataset()

    assert manifest["summary"]["ledger_count"] == 1
    assert manifest["summary"]["avg_quality_score"] == 0.83
    assert manifest["summary"]["liminalqa_published_count"] == 1
    assert manifest["summary"]["risky_cycle_count"] == 1
    assert manifest["summary"]["incident_count"] == 1
    assert manifest["items"][0]["quality_file"] == "council-quality/cycle-001.json"
    assert manifest["items"][0]["risk_state"] == "repair"
    assert manifest["items"][0]["incident_published"] is True
    assert (output_quality_dir / "cycle-001.json").exists()
