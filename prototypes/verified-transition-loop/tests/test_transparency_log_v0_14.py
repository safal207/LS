from __future__ import annotations

import base64
import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

import verified_transition_loop.transparency_log as log_module
from verified_transition_loop.canonical import (
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    canonical_bytes,
)
from verified_transition_loop.transparency_log import (
    MAX_PROOF_NODES,
    checkpoint_digest,
    merkle_leaf_hash,
    signed_checkpoint_payload,
    verify_consistency_proof,
    verify_inclusion_proof,
)
from verified_transition_loop.transparency_log_conformance import (
    load_fixture,
    run_fixture,
)
from verified_transition_loop.transparency_log_strict import (
    verify_transparency_log,
)

ROOT = Path(__file__).parents[1]
FIXTURE = ROOT / "fixtures" / "transparency-log-v0.14.json"
SCHEMA = ROOT / "schemas" / "transparency-log-v0.14.schema.json"
V013_FIXTURE = ROOT / "fixtures" / "witnessed-freshness-v0.13.json"
NODE_VERIFIER = ROOT / "reference" / "transparency-log-v0.14.mjs"


def _fixture() -> dict:
    return load_fixture(FIXTURE)


def _verify(bundle: object, *, now_ms: object | None = None):
    fixture = _fixture()
    return verify_transparency_log(
        copy.deepcopy(bundle),
        now_ms=fixture["base_now_ms"] if now_ms is None else now_ms,
    )


def _set_path(document: object, path: str, value: object) -> None:
    parts = path.split(".")
    cursor = document
    for part in parts[:-1]:
        cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
    final = parts[-1]
    if isinstance(cursor, list):
        cursor[int(final)] = value
    else:
        cursor[final] = value


def test_v014_fixture_all_26_vectors_pass() -> None:
    result = run_fixture(_fixture())
    failed = [case["id"] for case in result["cases"] if not case["passed"]]
    false_parity = [
        key
        for key, value in result["parity"].items()
        if key.endswith("_matches_expected") and value is not True
    ]
    assert result["summary"] == {
        "total": 26,
        "passed": 26,
        "failed": 0,
        "all_passed": True,
    }, {"failed_cases": failed, "false_parity": false_parity}


def test_fixture_matches_published_schema() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_fixture())


def test_v014_target_binds_current_v013_fixture_digest() -> None:
    fixture = _fixture()
    v013 = json.loads(V013_FIXTURE.read_text(encoding="utf-8"))
    expected = "9bd59187591ed2d259a438af8ea2cdd4d5ffa616327e2ac93712a4bb295433bc"
    assert fixture["base_bundle"]["target"]["snapshot_digest"] == expected
    assert fixture["base_bundle"]["entry"]["snapshot_digest"] == expected
    assert v013["snapshot_view"]["snapshot_digest"] == expected


def test_all_canonical_and_signature_anchors_are_load_bearing() -> None:
    fixture = _fixture()
    base = fixture["base_bundle"]
    assert (
        base64.b64encode(canonical_bytes(base["entry"])).decode("ascii")
        == fixture["expected_base_entry_canonical_base64"]
    )
    assert merkle_leaf_hash(base["entry"]) == fixture["expected_base_leaf_hash"]
    assert (
        base64.b64encode(signed_checkpoint_payload(base["checkpoint"])).decode(
            "ascii"
        )
        == fixture["expected_base_checkpoint_signed_payload_base64"]
    )
    assert (
        base["checkpoint"]["signature"]
        == fixture["expected_base_checkpoint_signature_base64"]
    )
    assert (
        checkpoint_digest(base["checkpoint"])
        == fixture["expected_base_checkpoint_digest"]
    )
    assert (
        base["checkpoint"]["root_hash"]
        == fixture["expected_base_root_hash"]
    )


def test_inclusion_proof_accepts_target_leaf() -> None:
    bundle = _fixture()["base_bundle"]
    assert verify_inclusion_proof(
        leaf_index=bundle["leaf_index"],
        tree_size=bundle["checkpoint"]["tree_size"],
        leaf_hash=merkle_leaf_hash(bundle["entry"]),
        root_hash=bundle["checkpoint"]["root_hash"],
        audit_path=bundle["inclusion_path"],
    )


def test_inclusion_proof_rejects_tampered_path() -> None:
    bundle = _fixture()["base_bundle"]
    path = copy.deepcopy(bundle["inclusion_path"])
    path[0] = "00" * 32
    assert not verify_inclusion_proof(
        leaf_index=bundle["leaf_index"],
        tree_size=bundle["checkpoint"]["tree_size"],
        leaf_hash=merkle_leaf_hash(bundle["entry"]),
        root_hash=bundle["checkpoint"]["root_hash"],
        audit_path=path,
    )


def test_consistency_proof_accepts_append_only_extension() -> None:
    bundle = _fixture()["base_bundle"]
    previous = bundle["verifier_checkpoint"]
    current = bundle["checkpoint"]
    assert verify_consistency_proof(
        old_size=previous["known_tree_size"],
        new_size=current["tree_size"],
        old_root_hash=previous["known_root_hash"],
        new_root_hash=current["root_hash"],
        proof=bundle["consistency_path"],
    )


def test_consistency_proof_rejects_mutation() -> None:
    bundle = _fixture()["base_bundle"]
    previous = bundle["verifier_checkpoint"]
    current = bundle["checkpoint"]
    proof = copy.deepcopy(bundle["consistency_path"])
    proof[0] = "00" * 32
    assert not verify_consistency_proof(
        old_size=previous["known_tree_size"],
        new_size=current["tree_size"],
        old_root_hash=previous["known_root_hash"],
        new_root_hash=current["root_hash"],
        proof=proof,
    )


def test_valid_peer_split_view_blocks_valid_local_proofs() -> None:
    fixture = _fixture()
    bundle = copy.deepcopy(fixture["base_bundle"])
    bundle["peer_checkpoints"] = [
        copy.deepcopy(fixture["checkpoint_variants"]["conflict"])
    ]
    result = _verify(bundle)
    assert result.inclusion_valid is True
    assert result.consistency_valid is True
    assert result.log_equivocation_detected is True
    assert result.view_consistency_valid is False
    assert result.valid is False


def test_invalid_peer_cannot_make_an_equivocation_claim() -> None:
    fixture = _fixture()
    bundle = copy.deepcopy(fixture["base_bundle"])
    peer = copy.deepcopy(fixture["checkpoint_variants"]["conflict"])
    peer["signature"] = "AQ=="
    bundle["peer_checkpoints"] = [peer]
    result = _verify(bundle)
    assert result.log_equivocation_detected is False
    assert result.view_consistency_valid is False
    assert "PEER_CHECKPOINT_INVALID:0" in result.reason_codes
    assert result.valid is False


def test_valid_log_proof_cannot_rescue_invalid_v013_witness_layer() -> None:
    bundle = copy.deepcopy(_fixture()["base_bundle"])
    bundle["local_witnessed_freshness_valid"] = False
    result = _verify(bundle)
    assert result.inclusion_valid is True
    assert result.consistency_valid is True
    assert result.local_witnessed_freshness_valid is False
    assert result.valid is False


@pytest.mark.parametrize(
    ("target", "reason"),
    (
        ("bundle", "TRANSPARENCY_BUNDLE_FIELDS_INVALID"),
        ("target", "TARGET_FIELDS_INVALID"),
        ("entry", "ENTRY_FIELDS_INVALID"),
        ("checkpoint", "CHECKPOINT_FIELDS_INVALID"),
        ("authority", "LOG_AUTHORITY_FIELDS_INVALID"),
        ("key", "LOG_KEY_FIELDS_INVALID:0"),
        ("verifier_checkpoint", "LOG_VERIFIER_CHECKPOINT_FIELDS_INVALID"),
    ),
)
def test_unpublished_fields_fail_closed(target: str, reason: str) -> None:
    bundle = copy.deepcopy(_fixture()["base_bundle"])
    destinations = {
        "bundle": bundle,
        "target": bundle["target"],
        "entry": bundle["entry"],
        "checkpoint": bundle["checkpoint"],
        "authority": bundle["log_authority"],
        "key": bundle["log_authority"]["keys"][0],
        "verifier_checkpoint": bundle["verifier_checkpoint"],
    }
    destinations[target]["unsigned_claim"] = "permit"
    result = _verify(bundle)
    assert result.valid is False
    assert reason in result.reason_codes


@pytest.mark.parametrize("now_ms", (-1, True, MAX_SAFE_INTEGER + 1))
def test_verifier_time_must_be_non_negative_safe_integer(now_ms: object) -> None:
    result = _verify(_fixture()["base_bundle"], now_ms=now_ms)
    assert result.reason_codes == ("NOW_MS_INVALID",)


@pytest.mark.parametrize(
    ("path", "reason"),
    (
        ("checkpoint.issued_at_ms", "CHECKPOINT_ISSUED_AT_INVALID"),
        ("checkpoint.not_before_ms", "CHECKPOINT_NOT_BEFORE_INVALID"),
        ("checkpoint.not_after_ms", "CHECKPOINT_NOT_AFTER_INVALID"),
        (
            "log_authority.keys.0.not_before_ms",
            "LOG_KEY_SCHEMA_INVALID:0.not_before_ms",
        ),
        (
            "log_authority.keys.0.not_after_ms",
            "LOG_KEY_SCHEMA_INVALID:0.not_after_ms",
        ),
        (
            "verifier_checkpoint.checkpointed_at_ms",
            "LOG_VERIFIER_CHECKPOINT_TIME_INVALID",
        ),
    ),
)
def test_negative_epoch_milliseconds_fail_closed(path: str, reason: str) -> None:
    bundle = copy.deepcopy(_fixture()["base_bundle"])
    _set_path(bundle, path, -1)
    result = _verify(bundle)
    assert result.valid is False
    assert reason in result.reason_codes


def test_revocation_state_must_be_boolean_without_erasing_signature_math() -> None:
    bundle = copy.deepcopy(_fixture()["base_bundle"])
    bundle["log_authority"]["keys"][0]["revoked"] = 0
    result = _verify(bundle)
    assert result.log_checkpoint_signature_valid is True
    assert result.log_checkpoint_authority_valid is False
    assert "LOG_KEY_SCHEMA_INVALID:0.revoked" in result.reason_codes
    assert result.valid is False


@pytest.mark.parametrize(
    "signature",
    (
        "AQ==",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==\n",
    ),
)
def test_checkpoint_signature_requires_canonical_ed25519_material(
    signature: str,
) -> None:
    bundle = copy.deepcopy(_fixture()["base_bundle"])
    bundle["checkpoint"]["signature"] = signature
    result = _verify(bundle)
    assert result.log_checkpoint_signature_valid is False
    assert "CHECKPOINT_SIGNATURE_ENCODING_INVALID" in result.reason_codes
    assert result.valid is False


@pytest.mark.parametrize(
    "public_key_base64",
    (
        "AAAA",
        "yFOtDwzSthmuqSzuxP1Wok1kmdWEznklfkXP2BObYKc",
    ),
)
def test_log_key_requires_canonical_ed25519_material(
    public_key_base64: str,
) -> None:
    bundle = copy.deepcopy(_fixture()["base_bundle"])
    bundle["log_authority"]["keys"][0][
        "public_key_base64"
    ] = public_key_base64
    result = _verify(bundle)
    assert result.log_checkpoint_signature_valid is False
    assert result.log_checkpoint_authority_valid is False
    assert "LOG_KEY_MATERIAL_INVALID" in result.reason_codes
    assert result.valid is False


def test_proof_paths_are_bounded() -> None:
    fixture = _fixture()
    bundle = fixture["base_bundle"]
    too_long = ["00" * 32] * (MAX_PROOF_NODES + 1)
    assert not verify_inclusion_proof(
        leaf_index=bundle["leaf_index"],
        tree_size=bundle["checkpoint"]["tree_size"],
        leaf_hash=merkle_leaf_hash(bundle["entry"]),
        root_hash=bundle["checkpoint"]["root_hash"],
        audit_path=too_long,
    )
    assert not verify_consistency_proof(
        old_size=3,
        new_size=6,
        old_root_hash=bundle["verifier_checkpoint"]["known_root_hash"],
        new_root_hash=bundle["checkpoint"]["root_hash"],
        proof=too_long,
    )


def test_node_merkle_arithmetic_preserves_integers_above_32_bits() -> None:
    leaf_index = (1 << 32) + 1
    tree_size = (1 << 32) + 3
    leaf_hash = hashlib.sha256(b"large-safe-index-leaf").hexdigest()
    running = bytes.fromhex(leaf_hash)
    fn = leaf_index
    sn = tree_size - 1
    proof: list[str] = []
    counter = 0
    while sn:
        sibling = hashlib.sha256(f"sibling-{counter}".encode()).digest()
        proof.append(sibling.hex())
        if (fn & 1) or fn == sn:
            running = hashlib.sha256(b"\x01" + sibling + running).digest()
            while fn and (fn & 1) == 0:
                fn >>= 1
                sn >>= 1
        else:
            running = hashlib.sha256(b"\x01" + running + sibling).digest()
        fn >>= 1
        sn >>= 1
        counter += 1
    root_hash = running.hex()
    assert len(proof) <= MAX_PROOF_NODES
    assert verify_inclusion_proof(
        leaf_index=leaf_index,
        tree_size=tree_size,
        leaf_hash=leaf_hash,
        root_hash=root_hash,
        audit_path=proof,
    )

    script = """
      import {verifyInclusionProof} from './reference/transparency-log-v0.14.mjs';
      const input = JSON.parse(process.argv[1]);
      process.stdout.write(JSON.stringify(verifyInclusionProof(input)));
    """
    node_input = {
        "leafIndex": leaf_index,
        "treeSize": tree_size,
        "leafHash": leaf_hash,
        "rootHash": root_hash,
        "auditPath": proof,
    }
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", script, json.dumps(node_input)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(completed.stdout) is True


def test_verifier_snapshots_caller_bundle_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    bundle = copy.deepcopy(fixture["base_bundle"])
    original = log_module._checkpoint_shape_reasons
    mutated = False

    def mutate_caller_after_snapshot(candidate: object) -> list[str]:
        nonlocal mutated
        reasons = original(candidate)
        if not mutated:
            bundle["entry"]["snapshot_digest"] = "0" * 64
            bundle["log_authority"]["keys"][0]["revoked"] = True
            bundle["verifier_checkpoint"]["minimum_tree_size"] = 99
            mutated = True
        return reasons

    monkeypatch.setattr(
        log_module,
        "_checkpoint_shape_reasons",
        mutate_caller_after_snapshot,
    )
    result = verify_transparency_log(
        bundle,
        now_ms=fixture["base_now_ms"],
    )
    assert result.valid is True
    assert bundle["entry"]["snapshot_digest"] == "0" * 64
    assert bundle["log_authority"]["keys"][0]["revoked"] is True
    assert bundle["verifier_checkpoint"]["minimum_tree_size"] == 99


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_root_field",
        "empty_cases",
        "duplicate_case_id",
        "extra_case_field",
        "dangling_checkpoint_ref",
        "unused_checkpoint",
        "dangerous_path",
        "missing_path",
        "no_op_mutation",
        "duplicate_mutation_path",
        "partial_expected",
        "duplicate_verification_input",
        "negative_base_time",
        "base_checkpoint_extra_field",
        "base_key_algorithm",
        "base_key_material",
        "base_key_interval",
        "base_verifier_extra_field",
    ),
)
def test_fixture_contract_fails_closed(mutation: str) -> None:
    fixture = _fixture()
    first = fixture["cases"][0]
    if mutation == "extra_root_field":
        fixture["claimed_valid"] = True
    elif mutation == "empty_cases":
        fixture["cases"] = []
    elif mutation == "duplicate_case_id":
        fixture["cases"][1]["id"] = first["id"]
    elif mutation == "extra_case_field":
        first["claimed_valid"] = True
    elif mutation == "dangling_checkpoint_ref":
        first["checkpoint_ref"] = "missing"
    elif mutation == "unused_checkpoint":
        fixture["checkpoint_variants"]["unused"] = copy.deepcopy(
            fixture["checkpoint_variants"]["base"]
        )
    elif mutation == "dangerous_path":
        first["mutations"] = [{"path": "__proto__.polluted", "value": True}]
    elif mutation == "missing_path":
        first["mutations"] = [{"path": "target.missing", "value": True}]
    elif mutation == "no_op_mutation":
        first["mutations"] = [
            {
                "path": "target.log_id",
                "value": fixture["base_bundle"]["target"]["log_id"],
            }
        ]
    elif mutation == "duplicate_mutation_path":
        first["mutations"] = [
            {"path": "target.log_id", "value": "other-a"},
            {"path": "target.log_id", "value": "other-b"},
        ]
    elif mutation == "partial_expected":
        first["expected"].pop("entry_integrity_valid")
    elif mutation == "duplicate_verification_input":
        duplicate = copy.deepcopy(first)
        duplicate["id"] = "duplicate-input"
        fixture["cases"].append(duplicate)
    elif mutation == "negative_base_time":
        fixture["base_now_ms"] = -1
    elif mutation == "base_checkpoint_extra_field":
        fixture["base_bundle"]["checkpoint"]["unsigned_claim"] = True
    elif mutation == "base_key_algorithm":
        fixture["base_bundle"]["log_authority"]["keys"][0][
            "algorithm"
        ] = "OTHER"
    elif mutation == "base_key_material":
        fixture["base_bundle"]["log_authority"]["keys"][0][
            "public_key_base64"
        ] = "AAAA"
    elif mutation == "base_key_interval":
        fixture["base_bundle"]["log_authority"]["keys"][0][
            "not_after_ms"
        ] = 0
    else:
        fixture["base_bundle"]["verifier_checkpoint"][
            "unsigned_claim"
        ] = True

    with pytest.raises(CanonicalizationError) as excinfo:
        run_fixture(fixture)
    assert excinfo.value.code == "FIXTURE_SCHEMA_INVALID"


@pytest.mark.parametrize(
    "anchor",
    (
        "expected_base_entry_canonical_base64",
        "expected_base_leaf_hash",
        "expected_base_checkpoint_signed_payload_base64",
        "expected_base_checkpoint_signature_base64",
        "expected_base_checkpoint_digest",
        "expected_base_root_hash",
    ),
)
def test_anchor_drift_prevents_conformance_success(anchor: str) -> None:
    fixture = _fixture()
    if anchor.endswith("_base64"):
        raw = base64.b64decode(fixture[anchor])
        fixture[anchor] = base64.b64encode(bytes([raw[0] ^ 1]) + raw[1:]).decode(
            "ascii"
        )
    else:
        fixture[anchor] = (
            ("0" if fixture[anchor][0] != "0" else "1") + fixture[anchor][1:]
        )
    result = run_fixture(fixture)
    assert result["summary"]["all_passed"] is False
    assert any(
        key.endswith("_matches_expected") and value is False
        for key, value in result["parity"].items()
    )


def test_complete_expected_result_detects_lower_claim_drift() -> None:
    fixture = _fixture()
    fixture["cases"][0]["expected"]["local_witnessed_freshness_valid"] = False
    result = run_fixture(fixture)
    assert result["cases"][0]["passed"] is False
    assert result["summary"]["failed"] == 1
    assert result["summary"]["all_passed"] is False


def test_all_negative_fixture_cannot_report_all_passed() -> None:
    fixture = _fixture()
    fixture["checkpoint_variants"] = {
        "base": fixture["checkpoint_variants"]["base"]
    }
    fixture["verifier_checkpoint_variants"] = {
        "base": fixture["verifier_checkpoint_variants"]["base"]
    }
    fixture["inclusion_path_variants"] = {
        "base": fixture["inclusion_path_variants"]["base"]
    }
    fixture["consistency_path_variants"] = {
        "base": fixture["consistency_path_variants"]["base"]
    }
    fixture["cases"] = [
        next(
            copy.deepcopy(case)
            for case in fixture["cases"]
            if case["id"] == "inherited-v013-failure-not-rescued"
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
