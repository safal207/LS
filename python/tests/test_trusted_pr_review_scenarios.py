"""End-to-end Trusted PR Review scenario tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from modules.trusted_runtime.pr_review_analysis import analyze_diff, canonical_json
from modules.trusted_runtime.pr_review_mvp import run_trusted_pr_review


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/pr-review"
SCHEMA = ROOT / "schemas/trusted_runtime/pr_review_artifact.schema.json"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _diff(scenario: str) -> str:
    return (FIXTURES / f"{scenario}.diff").read_text(encoding="utf-8")


def test_allow_hold_and_block_effect_boundaries(tmp_path: Path) -> None:
    expected = _load("expected.json")
    for scenario in ("allow", "hold", "block"):
        root = tmp_path / scenario
        result = run_trusted_pr_review(
            _diff(scenario),
            scenario=scenario,
            output_dir=root,
        )
        assert result["decision"] == expected[scenario]["decision"]
        assert result["protected_effect_written"] is expected[scenario][
            "protected_effect_written"
        ]
        assert result["artifact_written"] is expected[scenario]["artifact_written"]
        assert result["replay_decision"] == expected[scenario]["replay_decision"]
        assert (root / "review.md").exists()
        assert (root / "events.jsonl").exists()
        assert (root / "replay/conformance-report.json").exists()

        protected = list((root / "protected").glob("*.review.json"))
        if scenario == "allow":
            assert len(protected) == 1
            assert (root / "artifact.json").exists()
            assert (root / "proofpath/manifest.json").exists()
        else:
            assert protected == []
            assert not (root / "artifact.json").exists()
            assert not (root / "proofpath").exists()


def test_allow_artifact_schema_and_integrity(tmp_path: Path) -> None:
    result = run_trusted_pr_review(
        _diff("allow"),
        scenario="allow",
        output_dir=tmp_path,
    )
    artifact = json.loads((tmp_path / "artifact.json").read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert list(Draft202012Validator(schema).iter_errors(artifact)) == []
    assert artifact["summary"]["decision"] == "ALLOW"
    assert len(artifact["routes"]) == 3
    assert len(artifact["contributions"]) == 3
    assert artifact["execution"]["state"] == "EXECUTED"
    assert artifact["replay"]["record"]["decision"] == "ADMISSIBLE"
    assert artifact["reusable_artifact"]["execution_ref"]
    assert artifact["reusable_artifact"]["replay_ref"] == result["replay_ref"]

    integrity = artifact.pop("integrity")
    digest = hashlib.sha256(canonical_json(artifact).encode("utf-8")).hexdigest()
    assert integrity == {"algorithm": "sha256", "artifact_digest": digest}


def test_block_diff_static_analysis() -> None:
    analysis = analyze_diff(_diff("block"))
    assert "dynamic_code_execution" in analysis.risk_flags
    assert not analysis.test_files


def test_same_output_is_idempotent(tmp_path: Path) -> None:
    first = run_trusted_pr_review(
        _diff("allow"), scenario="allow", output_dir=tmp_path
    )
    second = run_trusted_pr_review(
        _diff("allow"), scenario="allow", output_dir=tmp_path
    )
    assert first["replay_ref"] == second["replay_ref"]
    assert len(list((tmp_path / "protected").glob("*.review.json"))) == 1
