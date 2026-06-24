"""Acceptance tests for Agent Orientation PR-review artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from modules.trusted_runtime.pr_review_mvp import run_trusted_pr_review


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/pr-review"
SCHEMA = ROOT / "schemas/trusted_runtime/orientation_context.schema.json"


def _diff(scenario: str) -> str:
    return (FIXTURES / f"{scenario}.diff").read_text(encoding="utf-8")


def _orientation(root: Path) -> dict:
    return json.loads(
        (root / "orientation-context.json").read_text(encoding="utf-8")
    )


def test_every_scenario_emits_valid_orientation_context(tmp_path: Path) -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    stages = {"allow": "REPLAYABLE", "hold": "HELD", "block": "BLOCKED"}

    for scenario, expected_stage in stages.items():
        root = tmp_path / scenario
        result = run_trusted_pr_review(
            _diff(scenario),
            scenario=scenario,
            output_dir=root,
        )
        orientation = _orientation(root)

        assert list(Draft202012Validator(schema).iter_errors(orientation)) == []
        assert result["orientation_stage"] == expected_stage
        assert orientation["stage"] == expected_stage
        assert orientation["decision"] == result["decision"]
        assert orientation["replay_ref"] == result["replay_ref"]
        assert orientation["dimensions"] == result["orientation_dimensions"]

        if scenario == "allow":
            assert orientation["authorization_ref"]
            assert orientation["execution_ref"]
            assert orientation["effect_ref"]
            assert orientation["artifact_ref"]
        else:
            assert orientation["authorization_ref"] is None
            assert orientation["execution_ref"] is None
            assert orientation["effect_ref"] is None
            assert orientation["artifact_ref"] is None


def test_allow_artifact_embeds_the_same_orientation(tmp_path: Path) -> None:
    run_trusted_pr_review(
        _diff("allow"),
        scenario="allow",
        output_dir=tmp_path,
    )
    artifact = json.loads((tmp_path / "artifact.json").read_text(encoding="utf-8"))

    assert artifact["orientation"] == _orientation(tmp_path)
    assert artifact["orientation"]["stage"] == "REPLAYABLE"
