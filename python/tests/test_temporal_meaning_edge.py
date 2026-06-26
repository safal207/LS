from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "temporal_meaning_edge.schema.json"
EXAMPLE_PATH = ROOT / "schemas" / "temporal_meaning_edge.example.json"
FIXTURE_ROOT = ROOT / "python" / "tests" / "fixtures" / "temporal-meaning-web"
VALID_CONTINUE_PATH = FIXTURE_ROOT / "valid_congruent_continue.json"
VALID_COUNTEREVIDENCE_PATH = FIXTURE_ROOT / "valid_counterevidence_signal.json"
VALID_CONTINUITY_BREAK_PATH = FIXTURE_ROOT / "valid_continuity_break.json"
INVALID_STALE_ALLOW_PATH = FIXTURE_ROOT / "invalid_allow_with_stale_evidence.json"
INVALID_IDENTITY_FLAG_PATH = FIXTURE_ROOT / "invalid_identity_candidate_flag.json"
INVALID_MISSING_PROVENANCE_PATH = FIXTURE_ROOT / "invalid_missing_provenance.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    schema = _load_json(SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _errors_for(path: Path) -> list:
    errors = list(_validator().iter_errors(_load_json(path)))
    return sorted(errors, key=lambda error: (list(error.path), error.message))


def test_temporal_meaning_edge_schema_is_valid_draft_2020_12() -> None:
    schema = _load_json(SCHEMA_PATH)

    Draft202012Validator.check_schema(schema)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == "temporal_meaning_edge.v0.1"


def test_temporal_meaning_edge_example_matches_schema() -> None:
    example = _load_json(EXAMPLE_PATH)

    assert _errors_for(EXAMPLE_PATH) == []
    assert example["temporal_state"]["memory_freshness"] == "current"
    assert example["temporal_state"]["evidence_validity"] == "revalidation_required"
    assert example["temporal_state"]["action_authority"] == "expired"
    assert example["congruence_state"]["decision"] == "recalibrate"


def test_congruent_current_authorized_fixture_can_continue() -> None:
    payload = _load_json(VALID_CONTINUE_PATH)

    assert _errors_for(VALID_CONTINUE_PATH) == []
    assert payload["congruence_state"]["decision"] == "allow"
    assert payload["temporal_state"] == {
        "memory_freshness": "current",
        "evidence_validity": "valid",
        "action_authority": "authorized",
        "entered_at": "2026-06-26T09:00:00Z",
        "last_validated_at": "2026-06-26T09:00:00Z",
        "validity_horizon": "until_repository_or_user_intent_changes",
        "resume_policy": "continue",
    }


def test_counterevidence_fixture_revalidates_without_identity_promotion() -> None:
    payload = _load_json(VALID_COUNTEREVIDENCE_PATH)

    assert _errors_for(VALID_COUNTEREVIDENCE_PATH) == []
    assert payload["continuity_impact"] == "counterevidence_signal"
    assert payload["congruence_state"]["decision"] == "revalidate"
    assert payload["temporal_state"]["resume_policy"] == "revalidate"
    assert payload["identity_proposal_eligible"] is False
    assert "recompute_track_confidence" in payload["governance_requirements"]


def test_continuity_break_fixture_blocks_authority_inheritance() -> None:
    payload = _load_json(VALID_CONTINUITY_BREAK_PATH)

    assert _errors_for(VALID_CONTINUITY_BREAK_PATH) == []
    assert payload["transition_class"] == "continuity_break"
    assert payload["continuity_impact"] == "continuity_break"
    assert payload["congruence_state"]["decision"] == "block"
    assert payload["temporal_state"]["evidence_validity"] == "invalid"
    assert payload["temporal_state"]["action_authority"] == "blocked"
    assert payload["temporal_state"]["resume_policy"] == "block"
    assert "do_not_inherit_authority" in payload["governance_requirements"]


def test_schema_rejects_allow_when_evidence_or_authority_is_stale() -> None:
    errors = _errors_for(INVALID_STALE_ALLOW_PATH)
    paths = [list(error.path) for error in errors]

    assert ["temporal_state", "evidence_validity"] in paths
    assert ["temporal_state", "action_authority"] in paths
    assert ["temporal_state", "resume_policy"] in paths


def test_schema_rejects_identity_candidate_without_eligibility() -> None:
    errors = _errors_for(INVALID_IDENTITY_FLAG_PATH)

    assert any(
        list(error.path) == ["identity_proposal_eligible"]
        and error.message == "True was expected"
        for error in errors
    )


def test_schema_rejects_meaning_without_source_or_evidence_provenance() -> None:
    errors = _errors_for(INVALID_MISSING_PROVENANCE_PATH)

    assert any(
        list(error.path) == ["source_refs"] and "should be non-empty" in error.message
        for error in errors
    )
    assert any(
        list(error.path) == ["evidence_refs"] and "should be non-empty" in error.message
        for error in errors
    )


def test_meaning_edge_never_exposes_direct_identity_mutation() -> None:
    schema = _load_json(SCHEMA_PATH)
    example = _load_json(EXAMPLE_PATH)

    forbidden_fields = {
        "identity_update",
        "identity_update_record",
        "identity_mutation",
        "approved_identity_state",
    }

    assert forbidden_fields.isdisjoint(schema["properties"])
    assert forbidden_fields.isdisjoint(example)
    assert example["identity_proposal_eligible"] is False
