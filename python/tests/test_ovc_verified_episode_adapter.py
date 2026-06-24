from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from adapt_outcome_verification_to_verified_episode import evaluate  # noqa: E402


def _set_path(target: dict, dotted_path: str, value) -> None:
    parts = dotted_path.split(".")
    current = target
    for part in parts[:-1]:
        current = current[int(part)] if isinstance(current, list) else current[part]
    final = parts[-1]
    if isinstance(current, list):
        current[int(final)] = copy.deepcopy(value)
    else:
        current[final] = copy.deepcopy(value)


def _materialize(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for definition in payload["cases"]:
        case = copy.deepcopy(payload["base_case"])
        case["fixture_id"] = definition["fixture_id"]
        case["expected"] = definition["expected"]
        for dotted_path, value in definition.get("overrides", {}).items():
            _set_path(case, dotted_path, value)
        cases.append(case)
    return cases


def test_ovc_verified_episode_v02_conformance() -> None:
    adapter_schema = json.loads(
        (ROOT / "schemas/trusted_runtime/ovc_verified_episode_adapter_v0.1.schema.json").read_text()
    )
    episode_schema = json.loads(
        (ROOT / "schemas/trusted_runtime/verified_episode_v0.2.schema.json").read_text()
    )
    adapter_validator = Draft202012Validator(adapter_schema)
    episode_validator = Draft202012Validator(episode_schema)

    fixture_paths = [
        ROOT / "fixtures/ovc-verified-episode/mandatory-v0.2.json",
        ROOT / "fixtures/ovc-verified-episode/precedence-v0.2.json",
    ]
    cases = [case for path in fixture_paths for case in _materialize(path)]
    assert len(cases) == 22

    for case in cases:
        request = {
            "adapter": case["adapter"],
            "authoritative_state": case["authoritative_state"],
        }
        assert not list(adapter_validator.iter_errors(request)), case["fixture_id"]

        result = evaluate(case)
        assert result["verdict"] == case["expected"]["verdict"]
        assert result["reason_code"] == case["expected"]["reason_code"]
        assert result["execution_authorized"] is False
        assert result["retroactive_authorization_created"] is False
        assert result["identity_update_applied"] is False
        assert result["downstream_learning_gate_required"] is True

        if result["verdict"] == "WRITE_CANDIDATE":
            assert result["episode"] is not None
            assert not list(episode_validator.iter_errors(result["episode"]))
            assert result["episode"]["identity_update_eligible"] is False
        else:
            assert result["episode"] is None


def test_failed_and_unexpected_do_not_project_as_v01_success() -> None:
    cases = _materialize(ROOT / "fixtures/ovc-verified-episode/mandatory-v0.2.json")
    by_id = {case["fixture_id"]: evaluate(case) for case in cases}

    expected = by_id["expected_verified_episode"]["episode"]
    failed = by_id["failed_verified_episode"]["episode"]
    unexpected = by_id["unexpected_verified_episode"]["episode"]

    assert expected["v0_1_projection"] == {
        "schema_version": "trusted_runtime.verified_episode.v0.1",
        "status": "VERIFIED",
        "outcome_status": "MATCHED",
    }
    for episode in (failed, unexpected):
        assert episode["status"] == "VERIFIED"
        assert episode["v0_1_projection"]["status"] == "UNVERIFIED"
        assert episode["v0_1_projection"]["outcome_status"] == "MISMATCHED"
