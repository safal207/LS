from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from modules.trusted_runtime.pr_review_api import run_trusted_pr_review
from modules.trusted_runtime.pr_review_learning import run_trusted_pr_review_with_episode


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/pr-review"
SCHEMA = ROOT / "schemas/trusted_runtime/verified_episode.schema.json"


def _diff(scenario: str) -> str:
    return (FIXTURES / f"{scenario}.diff").read_text(encoding="utf-8")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_all_scenarios_emit_verified_learning_records(tmp_path: Path) -> None:
    schema = _json(SCHEMA)
    replay = {"allow": "ADMISSIBLE", "hold": "DRIFTED", "block": "ADMISSIBLE"}

    for scenario in ("allow", "hold", "block"):
        root = tmp_path / scenario
        result = run_trusted_pr_review_with_episode(
            _diff(scenario), scenario=scenario, output_dir=root
        )
        episode = _json(root / "verified-episode.json")

        assert not list(Draft202012Validator(schema).iter_errors(episode))
        assert episode["status"] == "VERIFIED"
        assert episode["outcome_status"] == "MATCHED"
        assert episode["decision"] == scenario.upper()
        assert episode["replay_status"] == replay[scenario]
        assert episode["identity_update"]["allowed"] is False
        assert episode["identity_update"]["applied"] is False
        assert result["verified_episode_ref"] == episode["episode_id"]
        assert result["identity_update_allowed"] is False
        assert _json(root / "run-summary.json") == result


def test_stable_api_emits_verified_episode(tmp_path: Path) -> None:
    result = run_trusted_pr_review(
        _diff("allow"), scenario="allow", output_dir=tmp_path
    )

    episode = _json(tmp_path / "verified-episode.json")
    assert result["verified_episode_status"] == "VERIFIED"
    assert episode["lesson"]["repeat_key"] == (
        "trusted-pr-review:allow:one-authorized-effect"
    )
