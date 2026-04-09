from __future__ import annotations

from pathlib import Path

from ls.agent_shell.cli import CouncilLLMMode
from tools import run_fellowship_demo


class _FakeAgent:
    def __init__(self) -> None:
        self._council_ledger_dir: Path | None = None

    def process_text(self, prompt: str) -> dict:
        artifact_path = self._council_ledger_dir / "cycle-001.json"  # type: ignore[operator]
        artifact_path.write_text("{}", encoding="utf-8")
        quality_dir = self._council_ledger_dir.parent / "council-quality"  # type: ignore[operator]
        quality_dir.mkdir(parents=True, exist_ok=True)
        quality_path = quality_dir / "cycle-001.json"
        quality_path.write_text('{"cycle_id":"cycle-001","quality_score":0.81,"liminalqa":{"published":false,"status_code":null}}', encoding="utf-8")
        return {
            "cycle_id": "cycle-001",
            "final_output": f"demo for {prompt}",
            "council_contribution_ledger_artifact": str(artifact_path),
            "council_quality_artifact": str(quality_path),
            "council_contribution_ledger": {
                "final_decision": {"selected_route": "route-a"},
                "outcome": {
                    "success": True,
                    "receiver_resonance_score": 0.7,
                    "network_improvement": 0.2,
                },
                "attribution": {
                    "best_contributor_model_id": "local-council-llm",
                    "best_contributor_score": 0.9,
                },
            },
        }


def test_run_demo_writes_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run_fellowship_demo, "ARTIFACT_DIR", tmp_path / "council-ledger")
    monkeypatch.setattr(run_fellowship_demo, "SUMMARY_DIR", tmp_path / "fellowship-demo")
    monkeypatch.setattr(run_fellowship_demo, "SUMMARY_PATH", tmp_path / "fellowship-demo" / "demo-summary.json")
    monkeypatch.setattr(run_fellowship_demo, "build_council_agent", lambda **_: _FakeAgent())
    monkeypatch.setattr(
        run_fellowship_demo,
        "build_dataset",
        lambda: {"summary": {"ledger_count": 3, "success_count": 2}},
    )
    monkeypatch.setattr(
        run_fellowship_demo,
        "export_scorecard_with_preferred_sources",
        lambda *_, **__: {"source": "artifact", "summary": {"ledgers": 3, "success_rate": 66.67}},
    )

    summary = run_fellowship_demo.run_demo(
        prompt="demo prompt",
        llm_mode=CouncilLLMMode.DRY_RUN,
        artifact_dir=tmp_path / "council-ledger",
    )

    assert summary["cycle_id"] == "cycle-001"
    assert summary["selected_route"] == "route-a"
    assert summary["quality_score"] == 0.81
    assert summary["best_contributor_model_id"] == "local-council-llm"
    assert summary["dataset_summary"]["ledger_count"] == 3
    assert summary["scorecard_summary"]["ledgers"] == 3
    assert run_fellowship_demo.SUMMARY_PATH.exists()
