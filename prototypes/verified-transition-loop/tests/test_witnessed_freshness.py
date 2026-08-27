from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import verified_transition_loop.witnessed_freshness as witness_module
from verified_transition_loop.canonical import (
    MAX_SAFE_INTEGER,
    CanonicalizationError,
)
from verified_transition_loop.witnessed_freshness import (
    CANONICAL_PROFILE,
    _utf16_sort_key,
    compute_witness_statement_id,
    verify_witnessed_freshness,
)
from verified_transition_loop.witnessed_freshness_conformance import (
    load_fixture,
    run_fixture,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "fixtures" / "witnessed-freshness-v0.13.json"
SCHEMA = ROOT / "schemas" / "witnessed-freshness-v0.13.schema.json"
V012_FIXTURE = ROOT / "fixtures" / "canonical-trust-root-snapshot-v0.12.json"


def _fixture() -> dict:
    return load_fixture(FIXTURE)


def _verify(
    fixture: dict,
    *,
    snapshot_view: object | None = None,
    statements: object | None = None,
    authority: object | None = None,
    now_ms: object | None = None,
):
    return verify_witnessed_freshness(
        snapshot_view=copy.deepcopy(
            fixture["snapshot_view"] if snapshot_view is None else snapshot_view
        ),
        local_snapshot_valid=True,
        witness_statements=copy.deepcopy(
            [
                fixture["statements"]["a_target"],
                fixture["statements"]["b_target"],
            ]
            if statements is None
            else statements
        ),
        witness_authority=copy.deepcopy(
            fixture["witness_authority"] if authority is None else authority
        ),
        now_ms=fixture["base_now_ms"] if now_ms is None else now_ms,
    )


def test_all_witnessed_freshness_vectors_pass() -> None:
    result = run_fixture(_fixture())
    assert result["summary"] == {
        "total": 20,
        "passed": 20,
        "failed": 0,
        "all_passed": True,
    }


def test_fixture_matches_published_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fixture = _fixture()

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture)


def test_v013_view_binds_current_v012_snapshot_digest() -> None:
    fixture = _fixture()
    v012_fixture = json.loads(V012_FIXTURE.read_text(encoding="utf-8"))

    assert (
        fixture["snapshot_view"]["snapshot_digest"]
        == v012_fixture["expected_fresh_snapshot_digest"]
        == "9bd59187591ed2d259a438af8ea2cdd4d5ffa616327e2ac93712a4bb295433bc"
    )


def test_split_view_blocks_even_when_target_quorum_is_satisfied() -> None:
    result = run_fixture(_fixture())
    case = next(
        item
        for item in result["cases"]
        if item["id"] == "split-view-blocks-even-with-target-quorum"
    )
    assert case["actual"]["witness_quorum_valid"] is True
    assert case["actual"]["equivocation_detected"] is True
    assert case["actual"]["view_consistency_valid"] is False
    assert case["actual"]["valid"] is False


def test_duplicate_witness_identity_does_not_inflate_quorum() -> None:
    result = run_fixture(_fixture())
    case = next(
        item
        for item in result["cases"]
        if item["id"] == "duplicate-witness-does-not-count-twice"
    )
    assert case["actual"]["accepted_witness_ids"] == ["witness-a"]
    assert case["actual"]["witness_quorum_valid"] is False


def test_valid_witnesses_cannot_rescue_invalid_v012_snapshot() -> None:
    result = run_fixture(_fixture())
    case = next(
        item
        for item in result["cases"]
        if item["id"] == "local-v012-failure-not-rescued"
    )
    assert case["actual"]["witness_quorum_valid"] is True
    assert case["actual"]["local_snapshot_valid"] is False
    assert case["actual"]["valid"] is False
    assert case["actual"]["reason_codes"] == ["LOCAL_SNAPSHOT_INVALID"]


def test_statement_identity_is_canonical_and_version_bound() -> None:
    fixture = _fixture()
    statement = fixture["statements"]["a_target"]
    assert statement["canonical_profile"] == CANONICAL_PROFILE
    assert compute_witness_statement_id(statement) == statement["statement_id"]


def test_witness_identity_order_uses_cross_runtime_utf16_order() -> None:
    assert sorted(["\ue000", "😀"], key=_utf16_sort_key) == ["😀", "\ue000"]


def test_revocation_preserves_math_signature_but_removes_authority() -> None:
    fixture = _fixture()
    authority = copy.deepcopy(fixture["witness_authority"])
    authority["keys"][1]["revoked"] = True
    result = _verify(fixture, authority=authority)

    assert result.witness_signature_valid is True
    assert result.witness_authority_valid is False
    assert result.valid is False


def test_conformance_is_deterministic() -> None:
    fixture = _fixture()
    assert run_fixture(fixture) == run_fixture(fixture)


@pytest.mark.parametrize(
    ("target", "reason"),
    (
        ("view", "SNAPSHOT_VIEW_INVALID"),
        ("statement", "WITNESS_STATEMENT_FIELDS_INVALID"),
        ("authority", "WITNESS_AUTHORITY_FIELDS_INVALID"),
        ("key", "WITNESS_KEY_FIELDS_INVALID:0"),
    ),
)
def test_unpublished_fields_fail_closed(target: str, reason: str) -> None:
    fixture = _fixture()
    view = copy.deepcopy(fixture["snapshot_view"])
    statements = [
        copy.deepcopy(fixture["statements"]["a_target"]),
        copy.deepcopy(fixture["statements"]["b_target"]),
    ]
    authority = copy.deepcopy(fixture["witness_authority"])
    if target == "view":
        view["unsigned_claim"] = "permit"
    elif target == "statement":
        statements[0]["unsigned_claim"] = "permit"
    elif target == "authority":
        authority["unsigned_claim"] = "permit"
    else:
        authority["keys"][0]["unsigned_claim"] = "permit"

    result = _verify(
        fixture,
        snapshot_view=view,
        statements=statements,
        authority=authority,
    )

    assert result.valid is False
    assert reason in result.reason_codes


@pytest.mark.parametrize("now_ms", (-1, True, MAX_SAFE_INTEGER + 1))
def test_verifier_time_must_be_non_negative_safe_integer(now_ms: object) -> None:
    fixture = _fixture()
    result = _verify(fixture, now_ms=now_ms)
    assert result.reason_codes == ("NOW_MS_INVALID",)


@pytest.mark.parametrize(
    ("target", "reason"),
    (
        ("statement", "WITNESS_STATEMENT_SCHEMA_INVALID:observed_at_ms"),
        ("key", "WITNESS_KEY_SCHEMA_INVALID:0.not_before_ms"),
    ),
)
def test_negative_epoch_milliseconds_are_schema_invalid(
    target: str, reason: str
) -> None:
    fixture = _fixture()
    statements = [
        copy.deepcopy(fixture["statements"]["a_target"]),
        copy.deepcopy(fixture["statements"]["b_target"]),
    ]
    authority = copy.deepcopy(fixture["witness_authority"])
    if target == "statement":
        statements[0]["observed_at_ms"] = -1
    else:
        authority["keys"][0]["not_before_ms"] = -1

    result = _verify(fixture, statements=statements, authority=authority)

    assert result.valid is False
    assert reason in result.reason_codes


def test_revocation_state_must_be_boolean() -> None:
    fixture = _fixture()
    authority = copy.deepcopy(fixture["witness_authority"])
    authority["keys"][0]["revoked"] = 0

    result = _verify(fixture, authority=authority)

    assert result.valid is False
    assert result.reason_codes == ("WITNESS_KEY_SCHEMA_INVALID:0.revoked",)


@pytest.mark.parametrize(
    "signature",
    (
        "AQ==",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==\n",
    ),
)
def test_signature_requires_canonical_ed25519_material(signature: str) -> None:
    fixture = _fixture()
    statements = [
        copy.deepcopy(fixture["statements"]["a_target"]),
        copy.deepcopy(fixture["statements"]["b_target"]),
    ]
    statements[0]["signature"] = signature

    result = _verify(fixture, statements=statements)

    assert result.valid is False
    assert "WITNESS_STATEMENT_SCHEMA_INVALID:signature" in result.reason_codes


@pytest.mark.parametrize(
    "public_key_base64",
    (
        "AAAA",
        "iojj3XQJ8ZX9UtstPLpdcspnCb8dlBIb83SIAbQPb1w",
    ),
)
def test_malformed_witness_key_material_fails_without_signature_claim(
    public_key_base64: str,
) -> None:
    fixture = _fixture()
    authority = copy.deepcopy(fixture["witness_authority"])
    authority["keys"][0]["public_key_base64"] = public_key_base64

    result = _verify(fixture, authority=authority)

    assert result.valid is False
    assert result.witness_signature_valid is False
    assert result.witness_authority_valid is False
    assert "WITNESS_KEY_MATERIAL_INVALID" in result.reason_codes


def test_non_scalar_unicode_input_fails_closed() -> None:
    fixture = _fixture()
    statements = [
        copy.deepcopy(fixture["statements"]["a_target"]),
        copy.deepcopy(fixture["statements"]["b_target"]),
    ]
    statements[0]["witness_id"] = "\ud800"

    result = _verify(fixture, statements=statements)

    assert result.valid is False
    assert result.witness_statement_integrity_valid is False
    assert "WITNESS_STATEMENT_SCHEMA_INVALID:witness_id" in result.reason_codes


def test_nonconforming_statement_cannot_claim_equivocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    conflicting = copy.deepcopy(fixture["statements"]["a_wrong_digest"])
    target = copy.deepcopy(fixture["statements"]["b_target"])
    conflicting["profile_id"] = "vtl-witness-statement/v999"

    class AcceptingPublicKey:
        def verify(self, signature: bytes, payload: bytes) -> None:
            return None

    monkeypatch.setattr(
        witness_module,
        "compute_witness_statement_id",
        lambda statement: statement["statement_id"],
    )
    monkeypatch.setattr(
        witness_module.Ed25519PublicKey,
        "from_public_bytes",
        lambda material: AcceptingPublicKey(),
    )

    result = _verify(fixture, statements=[conflicting, target])

    assert result.witness_signature_valid is True
    assert result.witness_statement_integrity_valid is False
    assert result.equivocation_detected is False
    assert "WITNESS_PROFILE_MISMATCH" in result.reason_codes


def test_verifier_snapshots_caller_inputs_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    view = copy.deepcopy(fixture["snapshot_view"])
    statements = [
        copy.deepcopy(fixture["statements"]["a_target"]),
        copy.deepcopy(fixture["statements"]["b_target"]),
    ]
    authority = copy.deepcopy(fixture["witness_authority"])
    original_validate = witness_module._validate_statement
    mutated = False

    def mutate_callers_after_snapshot(candidate: object) -> tuple[str, ...]:
        nonlocal mutated
        reasons = original_validate(candidate)
        if not mutated:
            view["snapshot_digest"] = "0" * 64
            statements[0]["signature"] = "AQ=="
            authority["keys"][0]["revoked"] = True
            mutated = True
        return reasons

    monkeypatch.setattr(
        witness_module, "_validate_statement", mutate_callers_after_snapshot
    )
    result = verify_witnessed_freshness(
        snapshot_view=view,
        local_snapshot_valid=True,
        witness_statements=statements,
        witness_authority=authority,
        now_ms=fixture["base_now_ms"],
    )

    assert result.valid is True
    assert view["snapshot_digest"] == "0" * 64
    assert statements[0]["signature"] == "AQ=="
    assert authority["keys"][0]["revoked"] is True


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_root_field",
        "empty_cases",
        "duplicate_case_id",
        "extra_case_field",
        "dangling_statement",
        "unused_statement",
        "dangerous_path",
        "missing_path",
        "no_op_mutation",
        "statement_index_out_of_range",
        "statement_missing_path",
        "statement_no_op",
        "extra_statement_field",
        "missing_expected_claim",
        "duplicate_expected_identity",
        "negative_base_time",
        "baseline_algorithm_set",
        "baseline_key_algorithm",
        "baseline_key_material",
        "baseline_key_interval",
        "baseline_statement_profile",
        "baseline_statement_identity",
        "duplicate_verification_input",
        "duplicate_authority_path",
        "duplicate_statement_target",
    ),
)
def test_fixture_contract_fails_closed(mutation: str) -> None:
    fixture = _fixture()
    first_case = fixture["cases"][0]
    if mutation == "extra_root_field":
        fixture["claimed_valid"] = True
    elif mutation == "empty_cases":
        fixture["cases"] = []
    elif mutation == "duplicate_case_id":
        fixture["cases"][1]["id"] = first_case["id"]
    elif mutation == "extra_case_field":
        first_case["claimed_valid"] = True
    elif mutation == "dangling_statement":
        first_case["statement_refs"][0] = "missing"
    elif mutation == "unused_statement":
        fixture["statements"]["unused"] = copy.deepcopy(
            fixture["statements"]["a_target"]
        )
    elif mutation == "dangerous_path":
        first_case["authority_mutations"] = [
            {"path": "__proto__.polluted", "value": True}
        ]
    elif mutation == "missing_path":
        first_case["authority_mutations"] = [
            {"path": "keys.0.missing", "value": True}
        ]
    elif mutation == "no_op_mutation":
        first_case["authority_mutations"] = [
            {"path": "quorum", "value": fixture["witness_authority"]["quorum"]}
        ]
    elif mutation == "statement_index_out_of_range":
        first_case["statement_mutations"] = [
            {"index": 99, "path": "signature", "value": "AQ=="}
        ]
    elif mutation == "statement_missing_path":
        first_case["statement_mutations"] = [
            {"index": 0, "path": "missing", "value": True}
        ]
    elif mutation == "statement_no_op":
        first_case["statement_mutations"] = [
            {
                "index": 0,
                "path": "signature",
                "value": fixture["statements"]["a_target"]["signature"],
            }
        ]
    elif mutation == "extra_statement_field":
        fixture["statements"]["a_target"]["claimed_valid"] = True
    elif mutation == "missing_expected_claim":
        first_case["expected"].pop("witness_signature_valid")
    elif mutation == "duplicate_expected_identity":
        first_case["expected"]["accepted_witness_ids"].append("witness-a")
    elif mutation == "negative_base_time":
        fixture["base_now_ms"] = -1
    elif mutation == "baseline_algorithm_set":
        fixture["witness_authority"]["allowed_algorithms"].append("OTHER")
    elif mutation == "baseline_key_algorithm":
        fixture["witness_authority"]["keys"][0]["algorithm"] = "OTHER"
    elif mutation == "baseline_key_material":
        fixture["witness_authority"]["keys"][0]["public_key_base64"] = "AAAA"
    elif mutation == "baseline_key_interval":
        fixture["witness_authority"]["keys"][0]["not_after_ms"] = 0
    elif mutation == "baseline_statement_profile":
        fixture["statements"]["a_target"]["profile_id"] = (
            "vtl-witness-statement/v999"
        )
    elif mutation == "baseline_statement_identity":
        fixture["statements"]["a_target"]["statement_id"] = "witness_bad"
    elif mutation == "duplicate_verification_input":
        duplicate = copy.deepcopy(first_case)
        duplicate["id"] = "duplicate-input"
        fixture["cases"].append(duplicate)
    elif mutation == "duplicate_authority_path":
        first_case["authority_mutations"] = [
            {"path": "quorum", "value": 3},
            {"path": "quorum", "value": 2},
        ]
    else:
        first_case["statement_mutations"] = [
            {"index": 0, "path": "signature", "value": "AQ=="},
            {
                "index": 0,
                "path": "signature",
                "value": fixture["statements"]["a_target"]["signature"],
            },
        ]

    with pytest.raises(CanonicalizationError) as excinfo:
        run_fixture(fixture)
    assert excinfo.value.code == "FIXTURE_SCHEMA_INVALID"


def test_complete_expected_result_detects_lower_claim_drift() -> None:
    fixture = _fixture()
    fixture["cases"][0]["expected"]["witness_signature_valid"] = False

    result = run_fixture(fixture)

    assert result["cases"][0]["passed"] is False
    assert result["summary"]["failed"] == 1
    assert result["summary"]["all_passed"] is False


def test_all_negative_fixture_cannot_report_all_passed() -> None:
    fixture = _fixture()
    fixture["statements"] = {
        "a_target": fixture["statements"]["a_target"],
    }
    fixture["cases"] = [
        next(
            copy.deepcopy(case)
            for case in fixture["cases"]
            if case["id"] == "insufficient-quorum"
        )
    ]

    result = run_fixture(fixture)

    assert result["cases"][0]["passed"] is True
    assert result["cases"][0]["actual"]["valid"] is False
    assert result["summary"] == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "all_passed": False,
    }
