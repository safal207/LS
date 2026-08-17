import json
from pathlib import Path

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


def test_schema_and_fixture_are_valid_json_documents():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validate_fixture_shape(fixture)
    assert fixture["schema_version"] == SCHEMA_VERSION
    assert fixture["profile"]["profile_id"] == PROFILE_ID
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == SCHEMA_VERSION
    assert schema["properties"]["profile"]["properties"]["profile_id"]["const"] == PROFILE_ID


def test_vendor_neutral_use_time_vectors_all_pass():
    result = run_fixture(load_fixture(FIXTURE_PATH))
    assert result["summary"] == {
        "total": 9,
        "passed": 9,
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


def test_conformance_run_is_deterministic_for_same_fixture():
    fixture = load_fixture(FIXTURE_PATH)
    left = run_fixture(fixture)
    right = run_fixture(fixture)
    assert left == right
