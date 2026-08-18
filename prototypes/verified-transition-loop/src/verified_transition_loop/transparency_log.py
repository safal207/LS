from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical import CANONICAL_PROFILE, MAX_SAFE_INTEGER, canonical_bytes, canonical_sha256

PROFILE_ID = "vtl-transparency-log-v0.14"
SCHEMA_VERSION = "vtl.transparency-log/v0.14"
FIXTURE_SCHEMA_VERSION = "vtl.transparency-log-fixture/v0.14"
ENTRY_PROFILE_ID = "vtl-transparency-log-entry/v0.14"
CHECKPOINT_PROFILE_ID = "vtl-transparency-log-checkpoint/v0.14"
LOG_AUTHORITY_PROFILE_ID = "vtl-transparency-log-authority/v0.14"
VERIFIER_CHECKPOINT_PROFILE_ID = "vtl-transparency-log-verifier-checkpoint/v0.14"
ED25519 = "ED25519"
PUBLIC_KEY_BYTES = 32


@dataclass(frozen=True)
class TransparencyLogResult:
    valid: bool
    local_witnessed_freshness_valid: bool
    entry_integrity_valid: bool
    log_checkpoint_signature_valid: bool
    log_checkpoint_authority_valid: bool
    log_checkpoint_freshness_valid: bool
    inclusion_valid: bool
    consistency_valid: bool
    view_consistency_valid: bool
    log_equivocation_detected: bool
    accepted_tree_size: int | None
    accepted_root_hash: str | None
    reason_codes: tuple[str, ...]


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and abs(value) <= MAX_SAFE_INTEGER
    )


def _positive_integer(value: Any) -> bool:
    return _integer(value) and value >= 1


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _decode_base64(value: Any) -> bytes | None:
    if not isinstance(value, str):
        return None
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None


def merkle_leaf_hash(entry: Mapping[str, Any]) -> str:
    return hashlib.sha256(b"\x00" + canonical_bytes(dict(entry))).hexdigest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def verify_inclusion_proof(
    *,
    leaf_index: Any,
    tree_size: Any,
    leaf_hash: Any,
    root_hash: Any,
    audit_path: Any,
) -> bool:
    if (
        not _integer(leaf_index)
        or not _positive_integer(tree_size)
        or leaf_index < 0
        or leaf_index >= tree_size
        or not _hex64(leaf_hash)
        or not _hex64(root_hash)
        or not isinstance(audit_path, list)
        or not all(_hex64(value) for value in audit_path)
    ):
        return False

    fn = leaf_index
    sn = tree_size - 1
    running = bytes.fromhex(leaf_hash)

    for value in audit_path:
        if sn == 0:
            return False
        sibling = bytes.fromhex(value)
        if (fn & 1) or fn == sn:
            running = _node_hash(sibling, running)
            while fn != 0 and (fn & 1) == 0:
                fn >>= 1
                sn >>= 1
        else:
            running = _node_hash(running, sibling)
        fn >>= 1
        sn >>= 1

    return sn == 0 and running.hex() == root_hash


def verify_consistency_proof(
    *,
    old_size: Any,
    new_size: Any,
    old_root_hash: Any,
    new_root_hash: Any,
    proof: Any,
) -> bool:
    if (
        not _positive_integer(old_size)
        or not _positive_integer(new_size)
        or old_size > new_size
        or not _hex64(old_root_hash)
        or not _hex64(new_root_hash)
        or not isinstance(proof, list)
        or not all(_hex64(value) for value in proof)
    ):
        return False

    if old_size == new_size:
        return not proof and old_root_hash == new_root_hash

    fn = old_size - 1
    sn = new_size - 1
    while fn & 1:
        fn >>= 1
        sn >>= 1

    nodes = [bytes.fromhex(value) for value in proof]
    if fn == 0:
        old_running = new_running = bytes.fromhex(old_root_hash)
    else:
        if not nodes:
            return False
        old_running = new_running = nodes.pop(0)

    for node in nodes:
        if sn == 0:
            return False
        if (fn & 1) or fn == sn:
            old_running = _node_hash(node, old_running)
            new_running = _node_hash(node, new_running)
            while fn != 0 and (fn & 1) == 0:
                fn >>= 1
                sn >>= 1
        else:
            new_running = _node_hash(new_running, node)
        fn >>= 1
        sn >>= 1

    return (
        sn == 0
        and old_running.hex() == old_root_hash
        and new_running.hex() == new_root_hash
    )


_CHECKPOINT_FIELDS = (
    "profile_id",
    "schema_version",
    "canonical_profile",
    "log_id",
    "tree_size",
    "root_hash",
    "issued_at_ms",
    "not_before_ms",
    "not_after_ms",
    "issuer_id",
    "log_authority_id",
    "log_key_id",
    "signature_algorithm",
)


def checkpoint_statement(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    return {field: checkpoint.get(field) for field in _CHECKPOINT_FIELDS}


def compute_checkpoint_id(checkpoint: Mapping[str, Any]) -> str:
    return "logcp_" + canonical_sha256(checkpoint_statement(checkpoint))[:24]


def signed_checkpoint_payload(checkpoint: Mapping[str, Any]) -> bytes:
    return canonical_bytes(
        {
            "checkpoint_id": checkpoint.get("checkpoint_id"),
            **checkpoint_statement(checkpoint),
        }
    )


def checkpoint_digest(checkpoint: Mapping[str, Any]) -> str:
    return canonical_sha256(dict(checkpoint))


def _verify_checkpoint(
    checkpoint: Any,
    authority: Any,
    *,
    now_ms: Any,
) -> tuple[bool, bool, bool, bool, list[str]]:
    reasons: list[str] = []
    if not _is_mapping(checkpoint):
        return False, False, False, False, ["CHECKPOINT_INVALID"]
    if not _is_mapping(authority):
        return False, False, False, False, ["LOG_AUTHORITY_INVALID"]
    if not _integer(now_ms):
        return False, False, False, False, ["NOW_MS_INVALID"]

    _add(reasons, "CHECKPOINT_PROFILE_INVALID", checkpoint.get("profile_id") != CHECKPOINT_PROFILE_ID)
    _add(reasons, "CHECKPOINT_SCHEMA_VERSION_INVALID", checkpoint.get("schema_version") != SCHEMA_VERSION)
    canonical_profile_valid = checkpoint.get("canonical_profile") == CANONICAL_PROFILE
    _add(reasons, "CANONICAL_PROFILE_MISMATCH", not canonical_profile_valid)
    _add(reasons, "CHECKPOINT_LOG_ID_INVALID", not _non_empty_string(checkpoint.get("log_id")))
    _add(reasons, "CHECKPOINT_TREE_SIZE_INVALID", not _positive_integer(checkpoint.get("tree_size")))
    _add(reasons, "CHECKPOINT_ROOT_HASH_INVALID", not _hex64(checkpoint.get("root_hash")))
    _add(reasons, "CHECKPOINT_ISSUER_INVALID", not _non_empty_string(checkpoint.get("issuer_id")))
    _add(reasons, "CHECKPOINT_AUTHORITY_ID_INVALID", not _non_empty_string(checkpoint.get("log_authority_id")))
    _add(reasons, "CHECKPOINT_KEY_ID_INVALID", not _non_empty_string(checkpoint.get("log_key_id")))
    _add(reasons, "CHECKPOINT_ALGORITHM_INVALID", not _non_empty_string(checkpoint.get("signature_algorithm")))
    _add(reasons, "CHECKPOINT_SIGNATURE_ENCODING_INVALID", _decode_base64(checkpoint.get("signature")) is None)

    try:
        expected_id = compute_checkpoint_id(checkpoint)
    except Exception:
        expected_id = None
    _add(reasons, "CHECKPOINT_ID_INVALID", checkpoint.get("checkpoint_id") != expected_id)

    _add(reasons, "LOG_AUTHORITY_PROFILE_INVALID", authority.get("profile_id") != LOG_AUTHORITY_PROFILE_ID)
    _add(
        reasons,
        "LOG_AUTHORITY_ID_MISMATCH",
        authority.get("log_authority_id") != checkpoint.get("log_authority_id"),
    )
    allowed = authority.get("allowed_algorithms")
    algorithm = checkpoint.get("signature_algorithm")
    algorithm_allowed = isinstance(allowed, list) and algorithm in allowed
    _add(reasons, "LOG_ALGORITHM_NOT_ALLOWED", not algorithm_allowed)

    keys = authority.get("keys")
    matches: list[Mapping[str, Any]] = []
    if isinstance(keys, list):
        matches = [
            key
            for key in keys
            if _is_mapping(key) and key.get("log_key_id") == checkpoint.get("log_key_id")
        ]
    _add(reasons, "LOG_KEY_NOT_TRUSTED", len(matches) == 0)
    _add(reasons, "LOG_KEY_AMBIGUOUS", len(matches) > 1)

    signature_valid = False
    authority_valid = False
    key = matches[0] if len(matches) == 1 else None
    if key is not None:
        public_key = _decode_base64(key.get("public_key_base64"))
        key_material_valid = public_key is not None and len(public_key) == PUBLIC_KEY_BYTES
        _add(reasons, "LOG_KEY_MATERIAL_INVALID", not key_material_valid)
        _add(reasons, "LOG_KEY_ISSUER_MISMATCH", key.get("issuer_id") != checkpoint.get("issuer_id"))
        _add(reasons, "LOG_KEY_ALGORITHM_MISMATCH", key.get("algorithm") != algorithm)
        _add(reasons, "LOG_KEY_REVOKED", key.get("revoked") is True)

        key_interval_valid = (
            _integer(key.get("not_before_ms"))
            and _integer(key.get("not_after_ms"))
            and key.get("not_after_ms") >= key.get("not_before_ms")
        )
        _add(reasons, "LOG_KEY_VALIDITY_INVALID", not key_interval_valid)
        _add(
            reasons,
            "LOG_KEY_NOT_YET_VALID",
            key_interval_valid and now_ms < key.get("not_before_ms"),
        )
        _add(
            reasons,
            "LOG_KEY_EXPIRED",
            key_interval_valid and now_ms > key.get("not_after_ms"),
        )

        signature = _decode_base64(checkpoint.get("signature"))
        if (
            algorithm == ED25519
            and algorithm_allowed
            and key.get("algorithm") == ED25519
            and key_material_valid
            and signature is not None
        ):
            try:
                Ed25519PublicKey.from_public_bytes(public_key).verify(
                    signature,
                    signed_checkpoint_payload(checkpoint),
                )
                signature_valid = True
            except (InvalidSignature, ValueError):
                signature_valid = False
            _add(reasons, "CHECKPOINT_SIGNATURE_INVALID", not signature_valid)

        authority_valid = (
            authority.get("profile_id") == LOG_AUTHORITY_PROFILE_ID
            and authority.get("log_authority_id") == checkpoint.get("log_authority_id")
            and algorithm_allowed
            and key_material_valid
            and key.get("issuer_id") == checkpoint.get("issuer_id")
            and key.get("algorithm") == algorithm
            and key.get("revoked") is False
            and key_interval_valid
            and now_ms >= key.get("not_before_ms")
            and now_ms <= key.get("not_after_ms")
        )

    freshness_valid = True
    validity_interval_valid = (
        _integer(checkpoint.get("not_before_ms"))
        and _integer(checkpoint.get("not_after_ms"))
        and checkpoint.get("not_after_ms") >= checkpoint.get("not_before_ms")
    )
    _add(reasons, "CHECKPOINT_VALIDITY_INVALID", not validity_interval_valid)
    if not validity_interval_valid:
        freshness_valid = False
    if validity_interval_valid and now_ms < checkpoint.get("not_before_ms"):
        _add(reasons, "CHECKPOINT_NOT_YET_VALID", True)
        freshness_valid = False
    if validity_interval_valid and now_ms > checkpoint.get("not_after_ms"):
        _add(reasons, "CHECKPOINT_EXPIRED", True)
        freshness_valid = False
    if not _integer(checkpoint.get("issued_at_ms")) or checkpoint.get("issued_at_ms") > now_ms:
        _add(reasons, "CHECKPOINT_ISSUED_IN_FUTURE", True)
        freshness_valid = False

    return (
        canonical_profile_valid,
        signature_valid,
        authority_valid,
        freshness_valid,
        reasons,
    )


def verify_transparency_log(
    bundle: Any,
    *,
    now_ms: Any,
) -> TransparencyLogResult:
    if not _is_mapping(bundle):
        return TransparencyLogResult(
            False, False, False, False, False, False, False, False, False, False,
            None, None, ("TRANSPARENCY_BUNDLE_INVALID",)
        )

    reasons: list[str] = []
    local_valid = bundle.get("local_witnessed_freshness_valid") is True
    _add(reasons, "LOCAL_WITNESSED_FRESHNESS_INVALID", not local_valid)

    target = bundle.get("target")
    entry = bundle.get("entry")
    entry_integrity_valid = _is_mapping(target) and _is_mapping(entry)
    if not entry_integrity_valid:
        _add(reasons, "ENTRY_OR_TARGET_INVALID", True)
        leaf_hash = None
    else:
        _add(reasons, "ENTRY_PROFILE_INVALID", entry.get("profile_id") != ENTRY_PROFILE_ID)
        _add(reasons, "ENTRY_CANONICAL_PROFILE_INVALID", entry.get("canonical_profile") != CANONICAL_PROFILE)
        for field, code in (
            ("log_id", "ENTRY_LOG_ID_MISMATCH"),
            ("trust_root_id", "ENTRY_TRUST_ROOT_MISMATCH"),
            ("snapshot_generation", "ENTRY_GENERATION_MISMATCH"),
            ("snapshot_digest", "ENTRY_SNAPSHOT_DIGEST_MISMATCH"),
        ):
            mismatch = entry.get(field) != target.get(field)
            _add(reasons, code, mismatch)
            entry_integrity_valid = entry_integrity_valid and not mismatch
        entry_integrity_valid = (
            entry_integrity_valid
            and entry.get("profile_id") == ENTRY_PROFILE_ID
            and entry.get("canonical_profile") == CANONICAL_PROFILE
            and entry.get("entry_type") == "trust-root-snapshot"
            and _non_empty_string(entry.get("log_id"))
            and _non_empty_string(entry.get("trust_root_id"))
            and _positive_integer(entry.get("snapshot_generation"))
            and _hex64(entry.get("snapshot_digest"))
        )
        _add(reasons, "ENTRY_TYPE_INVALID", entry.get("entry_type") != "trust-root-snapshot")
        try:
            leaf_hash = merkle_leaf_hash(entry)
        except Exception:
            leaf_hash = None
            entry_integrity_valid = False
            _add(reasons, "ENTRY_CANONICALIZATION_FAILED", True)

    checkpoint = bundle.get("checkpoint")
    authority = bundle.get("log_authority")
    (
        canonical_profile_valid,
        checkpoint_signature_valid,
        checkpoint_authority_valid,
        checkpoint_freshness_valid,
        checkpoint_reasons,
    ) = _verify_checkpoint(checkpoint, authority, now_ms=now_ms)
    for reason in checkpoint_reasons:
        _add(reasons, reason, True)

    if _is_mapping(entry) and _is_mapping(checkpoint):
        mismatch = entry.get("log_id") != checkpoint.get("log_id")
        _add(reasons, "ENTRY_CHECKPOINT_LOG_ID_MISMATCH", mismatch)
        entry_integrity_valid = entry_integrity_valid and not mismatch

    inclusion_valid = (
        leaf_hash is not None
        and _is_mapping(checkpoint)
        and verify_inclusion_proof(
            leaf_index=bundle.get("leaf_index"),
            tree_size=checkpoint.get("tree_size"),
            leaf_hash=leaf_hash,
            root_hash=checkpoint.get("root_hash"),
            audit_path=bundle.get("inclusion_path"),
        )
    )
    _add(reasons, "INCLUSION_PROOF_INVALID", not inclusion_valid)

    verifier_checkpoint = bundle.get("verifier_checkpoint")
    consistency_valid = True
    equivocation_detected = False
    if not _is_mapping(verifier_checkpoint):
        _add(reasons, "LOG_VERIFIER_CHECKPOINT_INVALID", True)
        consistency_valid = False
    elif verifier_checkpoint.get("profile_id") != VERIFIER_CHECKPOINT_PROFILE_ID:
        _add(reasons, "LOG_VERIFIER_CHECKPOINT_INVALID", True)
        consistency_valid = False
    else:
        if not _integer(verifier_checkpoint.get("checkpointed_at_ms")):
            _add(reasons, "LOG_VERIFIER_CHECKPOINT_TIME_INVALID", True)
            consistency_valid = False
        elif verifier_checkpoint.get("checkpointed_at_ms") > now_ms:
            _add(reasons, "LOG_VERIFIER_CHECKPOINT_FROM_FUTURE", True)
            consistency_valid = False

        if not _is_mapping(checkpoint) or verifier_checkpoint.get("log_id") != checkpoint.get("log_id"):
            _add(reasons, "LOG_ID_MISMATCH", True)
            consistency_valid = False

        known_size = verifier_checkpoint.get("known_tree_size")
        known_root = verifier_checkpoint.get("known_root_hash")
        tree_size = checkpoint.get("tree_size") if _is_mapping(checkpoint) else None
        root_hash = checkpoint.get("root_hash") if _is_mapping(checkpoint) else None

        if (
            not _positive_integer(known_size)
            or not _hex64(known_root)
            or not _positive_integer(tree_size)
            or not _hex64(root_hash)
        ):
            _add(reasons, "LOG_VERIFIER_KNOWN_STATE_INVALID", True)
            consistency_valid = False
        else:
            floor = verifier_checkpoint.get("minimum_tree_size")
            if not _positive_integer(floor):
                _add(reasons, "LOG_MINIMUM_TREE_SIZE_INVALID", True)
                consistency_valid = False
            elif tree_size < floor:
                _add(reasons, "LOG_TREE_SIZE_BELOW_FLOOR", True)
                consistency_valid = False

            if tree_size < known_size:
                _add(reasons, "LOG_CHECKPOINT_ROLLBACK", True)
                consistency_valid = False
            elif tree_size == known_size:
                if root_hash != known_root:
                    _add(reasons, "LOG_EQUIVOCATION_DETECTED", True)
                    equivocation_detected = True
                    consistency_valid = False
                elif bundle.get("consistency_path") not in ([], None):
                    _add(reasons, "LOG_CONSISTENCY_PROOF_INVALID", True)
                    consistency_valid = False
            else:
                proof_valid = verify_consistency_proof(
                    old_size=known_size,
                    new_size=tree_size,
                    old_root_hash=known_root,
                    new_root_hash=root_hash,
                    proof=bundle.get("consistency_path"),
                )
                _add(reasons, "LOG_CONSISTENCY_PROOF_INVALID", not proof_valid)
                consistency_valid = consistency_valid and proof_valid

    peers = bundle.get("peer_checkpoints")
    if isinstance(peers, list) and _is_mapping(checkpoint):
        for peer in peers:
            (
                peer_canonical,
                peer_signature,
                peer_authority,
                peer_freshness,
                _,
            ) = _verify_checkpoint(peer, authority, now_ms=now_ms)
            trusted_peer = (
                peer_canonical
                and peer_signature
                and peer_authority
                and peer_freshness
                and _is_mapping(peer)
                and peer.get("log_id") == checkpoint.get("log_id")
            )
            if (
                trusted_peer
                and peer.get("tree_size") == checkpoint.get("tree_size")
                and peer.get("root_hash") != checkpoint.get("root_hash")
            ):
                _add(reasons, "LOG_EQUIVOCATION_DETECTED", True)
                equivocation_detected = True

    view_consistency_valid = not equivocation_detected
    valid = (
        local_valid
        and entry_integrity_valid
        and canonical_profile_valid
        and checkpoint_signature_valid
        and checkpoint_authority_valid
        and checkpoint_freshness_valid
        and inclusion_valid
        and consistency_valid
        and view_consistency_valid
    )

    accepted_tree_size = (
        checkpoint.get("tree_size")
        if _is_mapping(checkpoint) and _positive_integer(checkpoint.get("tree_size"))
        else None
    )
    accepted_root_hash = (
        checkpoint.get("root_hash")
        if _is_mapping(checkpoint) and _hex64(checkpoint.get("root_hash"))
        else None
    )

    return TransparencyLogResult(
        valid=valid,
        local_witnessed_freshness_valid=local_valid,
        entry_integrity_valid=entry_integrity_valid,
        log_checkpoint_signature_valid=checkpoint_signature_valid,
        log_checkpoint_authority_valid=checkpoint_authority_valid,
        log_checkpoint_freshness_valid=checkpoint_freshness_valid,
        inclusion_valid=inclusion_valid,
        consistency_valid=consistency_valid,
        view_consistency_valid=view_consistency_valid,
        log_equivocation_detected=equivocation_detected,
        accepted_tree_size=accepted_tree_size,
        accepted_root_hash=accepted_root_hash,
        reason_codes=tuple(reasons),
    )
