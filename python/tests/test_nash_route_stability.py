from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_PATH = ROOT / "examples" / "route-stability" / "nash_route_stability_sample.json"
SCHEMA_PATH = ROOT / "schemas" / "route_stability_sample.schema.json"
INVALID_METRIC_VERSION_PATH = (
    ROOT / "python" / "tests" / "fixtures" / "route-stability" / "invalid_metric_version.json"
)


def _run_demo_payload() -> dict:
    script = ROOT / "scripts" / "run_nash_route_stability_demo.py"
    result = subprocess.run(
        [sys.executable, str(script), "--json"],
        check=True,
        capture_output=True,
        encoding="utf-8",
        text=True,
    )
    return json.loads(result.stdout)


def _load_sample() -> dict:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_invalid_metric_version_sample() -> dict:
    return json.loads(INVALID_METRIC_VERSION_PATH.read_text(encoding="utf-8"))


def _route_stability_validator() -> Draft202012Validator:
    schema = _load_schema()
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_nash_route_stability_demo_marks_full_route_stable() -> None:
    payload = _run_demo_payload()

    assert payload["metric_version"] == "nash_route_stability.v0.1"
    assert payload["interpretation_boundary"].startswith("Nash-style route stability proxy")
    assert payload["stability"]["decision"] == "stable_candidate"
    assert payload["stability"]["nash_style_stable"] is True
    assert payload["stability"]["coalition_gain"] > 0
    assert payload["stability"]["stability_margin"] > 0
    assert payload["full_route"]["reward"] > payload["baseline_route"]["reward"]
    assert all(
        item["marginal_contribution"] > 0
        for item in payload["participant_marginal_contributions"]
    )


def test_nash_route_stability_sample_matches_schema() -> None:
    sample = _load_sample()
    validator = _route_stability_validator()
    errors = sorted(validator.iter_errors(sample), key=lambda error: list(error.path))

    assert errors == []


def test_nash_route_stability_schema_rejects_invalid_fixture() -> None:
    invalid_sample = _load_invalid_metric_version_sample()
    validator = _route_stability_validator()
    errors = sorted(validator.iter_errors(invalid_sample), key=lambda error: list(error.path))

    error_messages = [error.message for error in errors]

    assert any("'nash_route_stability.v0.1' was expected" in message for message in error_messages)
    assert any("Additional properties are not allowed" in message for message in error_messages)
    assert any("unexpected_debug_field" in message for message in error_messages)


def test_nash_route_stability_sample_matches_demo_core_fields() -> None:
    sample = _load_sample()
    payload = _run_demo_payload()

    stable_paths = [
        ("demo",),
        ("metric_version",),
        ("trail_metric_version",),
        ("interpretation_boundary",),
        ("thresholds",),
        ("full_route", "label"),
        ("full_route", "route_key"),
        ("full_route", "kind"),
        ("full_route", "reward"),
        ("full_route", "outcome_success"),
        ("full_route", "decision"),
        ("baseline_route", "route_key"),
        ("baseline_route", "reward"),
        ("stability", "nash_style_stable"),
        ("stability", "decision"),
        ("stability", "coalition_gain"),
        ("stability", "best_counterfactual_route"),
        ("stability", "best_counterfactual_reward"),
        ("stability", "stability_margin"),
        ("stability", "minimum_marginal_contribution"),
        ("stability", "needs_more_runs"),
    ]

    for path in stable_paths:
        left = sample
        right = payload
        for key in path:
            left = left[key]
            right = right[key]
        assert left == right, ".".join(path)

    assert sample["counterfactuals"] == payload["counterfactuals"]
    assert sample["participant_marginal_contributions"] == payload[
        "participant_marginal_contributions"
    ]
