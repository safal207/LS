import copy
from pathlib import Path

import pytest

from verified_transition_loop.attestation import (
    load_fixture,
    verify_attested_dispatch,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "attested-dispatch-v0.8.json"
NOW = 1_800_000_001_000


def base_inputs():
    fixture = load_fixture(FIXTURE)
    return (
        copy.deepcopy(fixture["base_envelope"]),
        copy.deepcopy(fixture["trust_root"]),
    )


@pytest.mark.parametrize(
    ("section", "field", "reason"),
    (
        ("envelope", "claimed_role", "ENVELOPE_SCHEMA_INVALID:additionalProperties"),
        ("attestation", "claimed_role", "ATTESTATION_SCHEMA_INVALID:additionalProperties"),
        ("trust_root", "claimed_tenant", "TRUST_ROOT_SCHEMA_INVALID:additionalProperties"),
        ("trust_key", "claimed_role", "TRUST_KEY_SCHEMA_INVALID:0.additionalProperties"),
    ),
)
def test_unsigned_or_unpublished_fields_fail_closed(section, field, reason):
    envelope, trust_root = base_inputs()
    if section == "envelope":
        envelope[field] = "privileged"
    elif section == "attestation":
        envelope["attestation"][field] = "privileged"
    elif section == "trust_root":
        trust_root[field] = "tenant:other"
    else:
        trust_root["keys"][0][field] = "privileged"

    result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)

    assert result.valid is False
    assert result.signature_valid is False
    assert result.trusted_current_authority is False
    assert result.reason_codes == (reason,)


@pytest.mark.parametrize(
    ("section", "reason"),
    (
        ("attestation", "ATTESTATION_SCHEMA_INVALID:issued_at_ms"),
        ("trust_key", "TRUST_KEY_SCHEMA_INVALID:0.not_before_ms"),
    ),
)
def test_negative_epoch_milliseconds_are_schema_invalid(section, reason):
    envelope, trust_root = base_inputs()
    if section == "attestation":
        envelope["attestation"]["issued_at_ms"] = -1
    else:
        trust_root["keys"][0]["not_before_ms"] = -1

    result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)

    assert result.valid is False
    assert result.reason_codes == (reason,)


@pytest.mark.parametrize("now_ms", (True, -1))
def test_invalid_verification_time_fails_before_freshness_comparisons(now_ms):
    envelope, trust_root = base_inputs()

    result = verify_attested_dispatch(envelope, trust_root, now_ms=now_ms)

    assert result.valid is False
    assert result.reason_codes == ("VERIFICATION_TIME_INVALID",)


def test_non_json_in_memory_value_fails_before_canonicalization():
    envelope, trust_root = base_inputs()
    envelope["attestation"]["issued_at_ms"] = float("nan")

    result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)

    assert result.valid is False
    assert result.reason_codes == ("ENVELOPE_CANONICALIZATION_INVALID",)


@pytest.mark.parametrize(
    "second_name",
    ("profile_id", r"profile\u005fid"),
)
def test_fixture_loader_rejects_duplicate_json_member_names(tmp_path, second_name):
    raw = FIXTURE.read_text(encoding="utf-8")
    ambiguous = raw.replace(
        '"profile_id": "vtl-attested-dispatch-v0.8",',
        (
            '"profile_id": "wrong",\n'
            f'      "{second_name}": "vtl-attested-dispatch-v0.8",'
        ),
        1,
    )
    path = tmp_path / "ambiguous.json"
    path.write_text(ambiguous, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON member name: profile_id"):
        load_fixture(path)


def test_fixture_loader_rejects_non_finite_json_constants(tmp_path):
    raw = FIXTURE.read_text(encoding="utf-8")
    non_json = raw.replace(
        '"issued_at_ms": 1800000000500',
        '"issued_at_ms": NaN',
        1,
    )
    path = tmp_path / "non-finite.json"
    path.write_text(non_json, encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite JSON constant: NaN"):
        load_fixture(path)
