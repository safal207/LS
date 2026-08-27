import copy
from pathlib import Path

import pytest

from verified_transition_loop.trust_snapshot import (
    load_fixture,
    verify_trust_root_snapshot,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "trust-root-snapshot-v0.9.json"
NOW = 1_800_000_001_000


def base_inputs():
    fixture = load_fixture(FIXTURE)
    return (
        copy.deepcopy(fixture["base_snapshot"]),
        copy.deepcopy(fixture["bootstrap_authority"]),
        copy.deepcopy(fixture["base_checkpoint"]),
    )


@pytest.mark.parametrize(
    ("section", "reason"),
    (
        ("snapshot", "SNAPSHOT_SCHEMA_INVALID:additionalProperties"),
        (
            "bootstrap",
            "BOOTSTRAP_AUTHORITY_SCHEMA_INVALID:additionalProperties",
        ),
        ("bootstrap_key", "BOOTSTRAP_KEY_SCHEMA_INVALID:0.additionalProperties"),
        ("embedded_trust_root", "SNAPSHOT_TRUST_ROOT_SHAPE_INVALID"),
        ("checkpoint", "CHECKPOINT_SCHEMA_INVALID:additionalProperties"),
    ),
)
def test_unsigned_or_unpublished_fields_fail_closed(section, reason):
    snapshot, bootstrap, checkpoint = base_inputs()
    if section == "snapshot":
        snapshot["claimed_role"] = "privileged"
    elif section == "bootstrap":
        bootstrap["claimed_tenant"] = "tenant:other"
    elif section == "bootstrap_key":
        bootstrap["keys"][0]["claimed_role"] = "privileged"
    elif section == "embedded_trust_root":
        snapshot["trust_root"]["claimed_role"] = "privileged"
    else:
        checkpoint["claimed_tenant"] = "tenant:other"

    result = verify_trust_root_snapshot(
        snapshot,
        bootstrap,
        checkpoint,
        now_ms=NOW,
    )

    assert result.valid is False
    assert result.bootstrap_signature_valid is False
    assert result.bootstrap_authority_valid is False
    assert result.reason_codes == (reason,)


@pytest.mark.parametrize(
    ("section", "reason"),
    (
        ("snapshot", "SNAPSHOT_SCHEMA_INVALID:issued_at_ms"),
        ("bootstrap_key", "BOOTSTRAP_KEY_SCHEMA_INVALID:0.not_before_ms"),
        ("checkpoint", "CHECKPOINT_TIME_INVALID"),
    ),
)
def test_negative_epoch_milliseconds_are_schema_invalid(section, reason):
    snapshot, bootstrap, checkpoint = base_inputs()
    if section == "snapshot":
        snapshot["issued_at_ms"] = -1
    elif section == "bootstrap_key":
        bootstrap["keys"][0]["not_before_ms"] = -1
    else:
        checkpoint["checkpointed_at_ms"] = -1

    result = verify_trust_root_snapshot(
        snapshot,
        bootstrap,
        checkpoint,
        now_ms=NOW,
    )

    assert result.valid is False
    assert result.reason_codes == (reason,)


@pytest.mark.parametrize("now_ms", (True, -1))
def test_invalid_verification_time_fails_before_time_comparisons(now_ms):
    snapshot, bootstrap, checkpoint = base_inputs()

    result = verify_trust_root_snapshot(
        snapshot,
        bootstrap,
        checkpoint,
        now_ms=now_ms,
    )

    assert result.valid is False
    assert result.reason_codes == ("VERIFICATION_TIME_INVALID",)


def test_non_json_in_memory_value_fails_before_canonicalization():
    snapshot, bootstrap, checkpoint = base_inputs()
    snapshot["issued_at_ms"] = float("nan")

    result = verify_trust_root_snapshot(
        snapshot,
        bootstrap,
        checkpoint,
        now_ms=NOW,
    )

    assert result.valid is False
    assert result.reason_codes == ("SNAPSHOT_CANONICALIZATION_INVALID",)


@pytest.mark.parametrize(
    "second_name",
    ("profile_id", r"profile\u005fid"),
)
def test_fixture_loader_rejects_duplicate_json_member_names(tmp_path, second_name):
    raw = FIXTURE.read_text(encoding="utf-8")
    ambiguous = raw.replace(
        '"profile_id":"vtl-trust-root-snapshot-v0.9"',
        (
            '"profile_id":"wrong",'
            f'"{second_name}":"vtl-trust-root-snapshot-v0.9"'
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
        '"issued_at_ms":1800000000500',
        '"issued_at_ms":NaN',
        1,
    )
    path = tmp_path / "non-finite.json"
    path.write_text(non_json, encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite JSON constant: NaN"):
        load_fixture(path)
