import copy
import json
from pathlib import Path

import pytest

from verified_transition_loop.conformance import (
    PROFILE_ID,
    SCHEMA_VERSION,
    load_fixture,
    run_fixture,
    validate_fixture_shape,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "fixtures" / "use-time-conformance-v0.4.json"
SCHEMA_PATH = ROOT / "schemas" / "use-time-conformance-v0.4.schema.json"


def fixture_dict():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_schema_and_fixture_are_valid_json_documents():
    fixture = fixture_dict()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validate_fixture_shape(fixture)
    assert fixture["schema_version"] == SCHEMA_VERSION
    assert fixture["profile"]["profile_id"] == PROFILE_ID
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert schema["properties"]["profile"]["properties"]["profile_id"]["const"] == PROFILE_ID
    assert schema["$defs"]["case"]["properties"]["proposal"] == {"$ref": "#/$defs/proposal"}


def test_strict_validation_rejects_unknown_fields():
    fixture = fixture_dict()
    fixture["base"]["unknown"] = "not-in-schema"
    with pytest.raises(ValueError, match="unknown keys"):
        validate_fixture_shape(fixture)


def test_strict_validation_rejects_missing_nested_evidence_fields():
    fixture = fixture_dict()
    del fixture["cases"][0]["current_evidence"]["policy_ref"]
    with pytest.raises(ValueError, match="missing keys"):
        validate_fixture_shape(fixture)


def test_strict_validation_rejects_invalid_primitive_types_without_coercion():
    fixture = fixture_dict()
    fixture["base"]["authorized_at_ms"] = "1000"
    with pytest.raises(ValueError, match="non-negative integer"):
        validate_fixture_shape(fixture)

    fixture = fixture_dict()
    fixture["base"]["proposal"]["transition_id"] = 123
    with pytest.raises(ValueError, match="non-empty string"):
        validate_fixture_shape(fixture)


@pytest.mark.parametrize(
    "second_name",
    ("schema_version", r"schema\u005fversion"),
)
def test_load_fixture_rejects_duplicate_json_member_names(tmp_path, second_name):
    raw = FIXTURE_PATH.read_text(encoding="utf-8")
    ambiguous = raw.replace(
        '"schema_version": "vtl.use-time-conformance/v0.4",',
        (
            '"schema_version": "wrong",\n'
            f'  "{second_name}": "vtl.use-time-conformance/v0.4",'
        ),
        1,
    )
    path = tmp_path / "ambiguous.json"
    path.write_text(ambiguous, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON member name: schema_version"):
        load_fixture(path)


def test_vendor_neutral_use_time_vectors_all_pass():
    result = run_fixture(load_fixture(FIXTURE_PATH))
    assert result["summary"] == {
        "total": 10,
        "passed": 10,
        "failed": 0,
        "all_passed": True,
    }


def test_stable_vector_proves_single_use_execution_receipt():
    result = run_fixture(load_fixture(FIXTURE_PATH))
    case = next(item for item in result["cases"] if item["id"] == "stable-context-executes")
    assert case["actual"]["verdict"] == "EXECUTE"
    assert case["actual"]["reason_codes"] == []
    assert case["actual"]["consume_results"] == [True, False]
    assert case["actual"]["receipt_integrity_valid"] is True


def test_policy_drift_vector_blocks_before_execution():
    result = run_fixture(load_fixture(FIXTURE_PATH))
    case = next(item for item in result["cases"] if item["id"] == "policy-ref-drift-blocks")
    assert case["actual"]["verdict"] == "BLOCK"
    assert case["actual"]["reason_codes"] == [
        "POLICY_REF_CHANGED",
        "EVIDENCE_CONTEXT_CHANGED",
    ]
    assert case["actual"]["consume_results"] == [False]


def test_proposal_drift_vector_blocks_exact_transition_mismatch():
    result = run_fixture(load_fixture(FIXTURE_PATH))
    case = next(
        item for item in result["cases"]
        if item["id"] == "proposal-transition-drift-blocks"
    )
    assert case["actual"]["verdict"] == "BLOCK"
    assert case["actual"]["reason_codes"] == ["AUTHORIZATION_TRANSITION_MISMATCH"]
    assert case["actual"]["consume_results"] == [False]


def test_conformance_run_is_deterministic_for_same_fixture():
    fixture = load_fixture(FIXTURE_PATH)
    left = run_fixture(copy.deepcopy(fixture))
    right = run_fixture(copy.deepcopy(fixture))
    assert left == right
