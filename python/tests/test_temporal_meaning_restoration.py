from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "temporal_meaning_edge.schema.json"
FIXTURE_PATH = ROOT / "python" / "tests" / "fixtures" / "temporal-meaning-web" / "valid_continuity_restoration.json"


def test_continuity_restoration_fixture_matches_contract() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(payload))

    assert errors == []
    assert payload["transition_class"] == "continuity_restoration"
    assert payload["continuity_impact"] == "continuity_restoration"
    assert payload["congruence_state"]["decision"] == "allow"
    assert payload["temporal_state"]["evidence_validity"] == "valid"
    assert payload["temporal_state"]["action_authority"] == "authorized"
    assert payload["temporal_state"]["resume_policy"] == "continue"
