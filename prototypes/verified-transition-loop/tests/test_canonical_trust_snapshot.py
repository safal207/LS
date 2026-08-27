from __future__ import annotations

import base64
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import verified_transition_loop.canonical_trust_snapshot as snapshot_module
from verified_transition_loop.canonical import (
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    strict_loads,
)
from verified_transition_loop.canonical_trust_snapshot import (
    CANONICAL_PROFILE,
    TRUST_ROOT_PROFILE_ID,
    snapshot_digest,
    verify_canonical_trust_snapshot,
)
from verified_transition_loop.canonical_trust_snapshot_conformance import run_fixture

FIXTURE = Path(__file__).parents[1] / "fixtures" / "canonical-trust-root-snapshot-v0.12.json"
SCHEMA = Path(__file__).parents[1] / "schemas" / "canonical-trust-root-snapshot-v0.12.schema.json"


def _fixture() -> dict:
    return strict_loads(FIXTURE.read_text(encoding="utf-8"))


def _variant(fixture: dict, name: str) -> dict:
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot.update(copy.deepcopy(fixture["snapshot_variants"][name]))
    return snapshot


def test_machine_readable_fixture_passes() -> None:
    result = run_fixture(_fixture())
    assert result["canonical_profile"] == CANONICAL_PROFILE
    assert result["summary"] == {
        "total": 20,
        "passed": 20,
        "failed": 0,
        "all_passed": True,
    }
    assert result["parity"]["signed_payload_matches_expected"] is True
    assert result["parity"]["signature_matches_expected"] is True
    assert result["parity"]["snapshot_digest_matches_expected"] is True


def test_fixture_matches_published_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fixture = _fixture()

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(fixture)


def test_v012_uses_a_distinct_embedded_trust_root_identity() -> None:
    fixture = _fixture()

    assert TRUST_ROOT_PROFILE_ID == "vtl-canonical-trust-root/v0.12"
    assert fixture["base_snapshot"]["trust_root"]["profile_id"] == TRUST_ROOT_PROFILE_ID
    assert TRUST_ROOT_PROFILE_ID != "vtl-canonical-trust-root/v0.11"


def test_fresh_snapshot_verifies_exact_signed_bytes_and_digest() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        copy.deepcopy(fixture["base_snapshot"]),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.valid is True
    assert result.bootstrap_signature_valid is True
    assert result.signed_payload_base64 == fixture["expected_fresh_signed_payload_base64"]
    assert result.snapshot_digest == fixture["expected_fresh_snapshot_digest"]


def test_historically_signed_snapshot_cannot_roll_back_checkpoint() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        _variant(fixture, "historical"),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["known_gen2"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.freshness_valid is True
    assert result.continuity_valid is False
    assert result.reason_codes == ("SNAPSHOT_ROLLBACK",)
    assert result.valid is False


def test_validly_signed_same_generation_fork_is_rejected() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        _variant(fixture, "fork"),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.snapshot_integrity_valid is True
    assert result.continuity_valid is False
    assert result.reason_codes == ("SNAPSHOT_FORK_DETECTED",)


def test_wrong_canonical_profile_can_be_signed_but_is_not_accepted() -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        _variant(fixture, "bad_profile"),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.canonical_profile_valid is False
    assert result.snapshot_integrity_valid is False
    assert result.reason_codes == ("CANONICAL_PROFILE_MISMATCH",)
    assert result.valid is False


def test_root_payload_tamper_does_not_invalidate_historical_signature_but_fails_integrity() -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot["trust_root"]["keys"][0]["revoked"] = True
    result = verify_canonical_trust_snapshot(
        snapshot,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.bootstrap_signature_valid is True
    assert result.snapshot_integrity_valid is False
    assert result.reason_codes == ("TRUST_ROOT_DIGEST_MISMATCH",)
    assert result.valid is False


def test_incomplete_checkpoint_fails_before_trust_claims() -> None:
    fixture = _fixture()
    checkpoint = copy.deepcopy(fixture["checkpoints"]["base"])
    checkpoint["known_generation"] = None
    result = verify_canonical_trust_snapshot(
        copy.deepcopy(fixture["base_snapshot"]),
        copy.deepcopy(fixture["bootstrap_authority"]),
        checkpoint,
        now_ms=fixture["base_now_ms"],
    )
    assert result.valid is False
    assert result.snapshot_integrity_valid is False
    assert result.bootstrap_signature_valid is False
    assert result.reason_codes == ("CHECKPOINT_KNOWN_STATE_INCOMPLETE",)


def test_unsafe_generation_fails_closed() -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot["generation"] = MAX_SAFE_INTEGER + 1
    result = verify_canonical_trust_snapshot(
        snapshot,
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["checkpoints"]["base"]),
        now_ms=fixture["base_now_ms"],
    )
    assert result.valid is False
    assert result.reason_codes == ("SNAPSHOT_SCHEMA_INVALID:generation",)


@pytest.mark.parametrize(
    ("target", "reason"),
    (
        ("snapshot", "SNAPSHOT_FIELDS_INVALID"),
        ("trust_root", "SNAPSHOT_TRUST_ROOT_FIELDS_INVALID"),
        ("trust_key", "SNAPSHOT_TRUST_KEY_FIELDS_INVALID:0"),
        ("bootstrap", "BOOTSTRAP_AUTHORITY_FIELDS_INVALID"),
        ("bootstrap_key", "BOOTSTRAP_KEY_FIELDS_INVALID:0"),
        ("checkpoint", "CHECKPOINT_FIELDS_INVALID"),
    ),
)
def test_unpublished_fields_fail_closed(target: str, reason: str) -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    authority = copy.deepcopy(fixture["bootstrap_authority"])
    checkpoint = copy.deepcopy(fixture["checkpoints"]["base"])
    if target == "snapshot":
        snapshot["unsigned_claim"] = "permit"
    elif target == "trust_root":
        snapshot["trust_root"]["unsigned_claim"] = "permit"
    elif target == "trust_key":
        snapshot["trust_root"]["keys"][0]["unsigned_claim"] = "permit"
    elif target == "bootstrap":
        authority["unsigned_claim"] = "permit"
    elif target == "bootstrap_key":
        authority["keys"][0]["unsigned_claim"] = "permit"
    else:
        checkpoint["unsigned_claim"] = "permit"

    result = verify_canonical_trust_snapshot(
        snapshot, authority, checkpoint, now_ms=fixture["base_now_ms"]
    )

    assert result.valid is False
    assert reason in result.reason_codes


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    (
        (
            "profile_id",
            "vtl-canonical-trust-root-snapshot-v999",
            "SNAPSHOT_SCHEMA_INVALID:profile_id",
        ),
        (
            "schema_version",
            "vtl.canonical-trust-root-snapshot/v999",
            "SNAPSHOT_SCHEMA_INVALID:schema_version",
        ),
    ),
)
def test_snapshot_profile_and_schema_are_exact_contract_fields(
    field: str, value: str, reason: str
) -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot[field] = value

    result = verify_canonical_trust_snapshot(
        snapshot,
        fixture["bootstrap_authority"],
        fixture["checkpoints"]["base"],
        now_ms=fixture["base_now_ms"],
    )

    assert result.valid is False
    assert result.reason_codes == (reason,)


@pytest.mark.parametrize("now_ms", (-1, True, MAX_SAFE_INTEGER + 1))
def test_verifier_time_must_be_non_negative_safe_integer(now_ms: int) -> None:
    fixture = _fixture()
    result = verify_canonical_trust_snapshot(
        fixture["base_snapshot"],
        fixture["bootstrap_authority"],
        fixture["checkpoints"]["base"],
        now_ms=now_ms,
    )
    assert result.reason_codes == ("NOW_MS_INVALID",)


@pytest.mark.parametrize(
    ("target", "reason"),
    (
        ("snapshot", "SNAPSHOT_SCHEMA_INVALID:issued_at_ms"),
        ("trust_key", "SNAPSHOT_TRUST_KEY_SCHEMA_INVALID:0.not_before_ms"),
        ("bootstrap_key", "BOOTSTRAP_KEY_SCHEMA_INVALID:0.not_before_ms"),
        ("checkpoint", "CHECKPOINT_TIME_INVALID"),
    ),
)
def test_negative_epoch_milliseconds_are_schema_invalid(
    target: str, reason: str
) -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    authority = copy.deepcopy(fixture["bootstrap_authority"])
    checkpoint = copy.deepcopy(fixture["checkpoints"]["base"])
    if target == "snapshot":
        snapshot["issued_at_ms"] = -1
    elif target == "trust_key":
        snapshot["trust_root"]["keys"][0]["not_before_ms"] = -1
    elif target == "bootstrap_key":
        authority["keys"][0]["not_before_ms"] = -1
    else:
        checkpoint["checkpointed_at_ms"] = -1

    result = verify_canonical_trust_snapshot(
        snapshot, authority, checkpoint, now_ms=fixture["base_now_ms"]
    )

    assert result.valid is False
    assert reason in result.reason_codes


@pytest.mark.parametrize("target", ("trust_key", "bootstrap_key"))
def test_revocation_state_must_be_boolean(target: str) -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    authority = copy.deepcopy(fixture["bootstrap_authority"])
    if target == "trust_key":
        snapshot["trust_root"]["keys"][0]["revoked"] = 0
        reason = "SNAPSHOT_TRUST_KEY_SCHEMA_INVALID:0.revoked"
    else:
        authority["keys"][0]["revoked"] = 0
        reason = "BOOTSTRAP_KEY_SCHEMA_INVALID:0.revoked"

    result = verify_canonical_trust_snapshot(
        snapshot,
        authority,
        fixture["checkpoints"]["base"],
        now_ms=fixture["base_now_ms"],
    )

    assert result.valid is False
    assert reason in result.reason_codes


@pytest.mark.parametrize(
    "signature",
    (
        "AQ==",
        "LEojO1CsM1/5lzgnKmKFgEAJ9kbC2P6CRTbuy1hzSDMGj2GgWYviC0TrZH6iP62jXgOU08N8"
        "BTLezLIXhjg9Aw==\n",
    ),
)
def test_snapshot_signature_requires_canonical_ed25519_material(
    signature: str,
) -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    snapshot["signature"] = signature

    result = verify_canonical_trust_snapshot(
        snapshot,
        fixture["bootstrap_authority"],
        fixture["checkpoints"]["base"],
        now_ms=fixture["base_now_ms"],
    )

    assert result.valid is False
    assert result.reason_codes == ("SNAPSHOT_SCHEMA_INVALID:signature",)


def test_malformed_bootstrap_key_material_fails_without_signature_claim() -> None:
    fixture = _fixture()
    authority = copy.deepcopy(fixture["bootstrap_authority"])
    authority["keys"][0]["public_key_base64"] = "AAAA"

    result = verify_canonical_trust_snapshot(
        fixture["base_snapshot"],
        authority,
        fixture["checkpoints"]["base"],
        now_ms=fixture["base_now_ms"],
    )

    assert result.valid is False
    assert result.bootstrap_signature_valid is False
    assert result.reason_codes == ("BOOTSTRAP_KEY_MATERIAL_INVALID",)


def test_verifier_snapshots_caller_inputs_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    snapshot = copy.deepcopy(fixture["base_snapshot"])
    authority = copy.deepcopy(fixture["bootstrap_authority"])
    checkpoint = copy.deepcopy(fixture["checkpoints"]["base"])
    original_validate = snapshot_module.validate_snapshot_shape

    def mutate_callers_after_snapshot(candidate: object) -> tuple[str, ...]:
        reasons = original_validate(candidate)
        snapshot["trust_root"]["policy_version"] = "caller-race"
        authority["keys"][0]["revoked"] = True
        checkpoint["minimum_generation"] = 99
        return reasons

    monkeypatch.setattr(
        snapshot_module, "validate_snapshot_shape", mutate_callers_after_snapshot
    )
    result = verify_canonical_trust_snapshot(
        snapshot, authority, checkpoint, now_ms=fixture["base_now_ms"]
    )

    assert result.valid is True
    assert snapshot["trust_root"]["policy_version"] == "caller-race"
    assert authority["keys"][0]["revoked"] is True
    assert checkpoint["minimum_generation"] == 99


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_root_field",
        "empty_cases",
        "duplicate_case_id",
        "extra_case_field",
        "dangling_variant",
        "dangling_checkpoint",
        "unused_variant",
        "unused_checkpoint",
        "extra_variant_field",
        "no_op_variant",
        "dangerous_path",
        "missing_path",
        "no_op_mutation",
    ),
)
def test_fixture_contract_fails_closed(mutation: str) -> None:
    fixture = _fixture()
    if mutation == "extra_root_field":
        fixture["claimed_valid"] = True
    elif mutation == "empty_cases":
        fixture["cases"] = []
    elif mutation == "duplicate_case_id":
        fixture["cases"][1]["id"] = fixture["cases"][0]["id"]
    elif mutation == "extra_case_field":
        fixture["cases"][0]["claimed_valid"] = True
    elif mutation == "dangling_variant":
        fixture["cases"][0]["variant_ref"] = "missing"
    elif mutation == "dangling_checkpoint":
        fixture["cases"][0]["checkpoint_ref"] = "missing"
    elif mutation == "unused_variant":
        fixture["snapshot_variants"]["unused"] = {
            "canonical_profile": "rfc8785-safe-integer/unused"
        }
    elif mutation == "unused_checkpoint":
        fixture["checkpoints"]["unused"] = copy.deepcopy(
            fixture["checkpoints"]["base"]
        )
    elif mutation == "extra_variant_field":
        fixture["snapshot_variants"]["expired"]["claimed_valid"] = True
    elif mutation == "no_op_variant":
        fixture["snapshot_variants"]["expired"]["canonical_profile"] = fixture[
            "base_snapshot"
        ]["canonical_profile"]
    elif mutation == "dangerous_path":
        fixture["cases"][0]["snapshot_mutations"] = [
            {"path": "__proto__.polluted", "value": True}
        ]
    elif mutation == "missing_path":
        fixture["cases"][0]["snapshot_mutations"] = [
            {"path": "trust_root.missing", "value": True}
        ]
    else:
        fixture["cases"][0]["snapshot_mutations"] = [
            {"path": "generation", "value": fixture["base_snapshot"]["generation"]}
        ]

    with pytest.raises(CanonicalizationError) as excinfo:
        run_fixture(fixture)
    assert excinfo.value.code == "FIXTURE_SCHEMA_INVALID"


def test_invalid_base_cannot_produce_all_passed_fixture() -> None:
    fixture = _fixture()
    invalid_signature = base64.b64encode(bytes(64)).decode("ascii")
    fixture["base_snapshot"]["signature"] = invalid_signature
    fixture["expected_fresh_signature_base64"] = invalid_signature
    fixture["expected_fresh_snapshot_digest"] = snapshot_digest(
        fixture["base_snapshot"]
    )
    fixture["snapshot_variants"] = {}
    fixture["checkpoints"] = {"base": fixture["checkpoints"]["base"]}
    fixture["cases"] = [
        {
            "id": "invalid-base",
            "checkpoint_ref": "base",
            "expected": {
                "valid": False,
                "snapshot_integrity_valid": True,
                "canonical_profile_valid": True,
                "bootstrap_signature_valid": False,
                "bootstrap_authority_valid": True,
                "freshness_valid": True,
                "continuity_valid": True,
                "reason_codes": ["SNAPSHOT_SIGNATURE_INVALID"],
            },
        }
    ]

    result = run_fixture(fixture)

    assert result["cases"][0]["passed"] is True
    assert result["parity"]["signed_payload_matches_expected"] is True
    assert result["parity"]["signature_matches_expected"] is True
    assert result["parity"]["snapshot_digest_matches_expected"] is True
    assert result["summary"] == {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "all_passed": False,
    }
