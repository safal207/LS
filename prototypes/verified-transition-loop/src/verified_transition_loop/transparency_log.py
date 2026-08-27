from __future__ import annotations

import base64
import binascii
import copy
import hashlib
from dataclasses import dataclass
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .canonical import (
    CANONICAL_PROFILE,
    MAX_SAFE_INTEGER,
    CanonicalizationError,
    canonical_bytes,
    canonical_sha256,
)

PROFILE_ID = "vtl-transparency-log-v0.14"
SCHEMA_VERSION = "vtl.transparency-log/v0.14"
FIXTURE_SCHEMA_VERSION = "vtl.transparency-log-fixture/v0.14"
ENTRY_PROFILE_ID = "vtl-transparency-log-entry/v0.14"
CHECKPOINT_PROFILE_ID = "vtl-transparency-log-checkpoint/v0.14"
LOG_AUTHORITY_PROFILE_ID = "vtl-transparency-log-authority/v0.14"
VERIFIER_CHECKPOINT_PROFILE_ID = "vtl-transparency-log-verifier-checkpoint/v0.14"
ED25519 = "ED25519"
PUBLIC_KEY_BYTES = 32
SIGNATURE_BYTES = 64
MAX_PROOF_NODES = 54

_BUNDLE_FIELDS = {
    "local_witnessed_freshness_valid",
    "target",
    "entry",
    "leaf_index",
    "inclusion_path",
    "checkpoint",
    "log_authority",
    "verifier_checkpoint",
    "consistency_path",
    "peer_checkpoints",
}
_TARGET_FIELDS = {
    "log_id",
    "trust_root_id",
    "snapshot_generation",
    "snapshot_digest",
}
_ENTRY_FIELDS = {
    "profile_id",
    "canonical_profile",
    "entry_type",
    "log_id",
    "trust_root_id",
    "snapshot_generation",
    "snapshot_digest",
}
_CHECKPOINT_STATEMENT_FIELDS = (
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
_CHECKPOINT_FIELDS = {
    *_CHECKPOINT_STATEMENT_FIELDS,
    "checkpoint_id",
    "signature",
}
_AUTHORITY_FIELDS = {
    "profile_id",
    "log_authority_id",
    "allowed_algorithms",
    "keys",
}
_KEY_FIELDS = {
    "log_key_id",
    "issuer_id",
    "algorithm",
    "public_key_base64",
    "not_before_ms",
    "not_after_ms",
    "revoked",
}
_VERIFIER_CHECKPOINT_FIELDS = {
    "profile_id",
    "log_id",
    "known_tree_size",
    "known_root_hash",
    "minimum_tree_size",
    "checkpointed_at_ms",
}
_CHECKPOINT_INTEGRITY_REASONS = frozenset(
    {
        "CHECKPOINT_INVALID",
        "CHECKPOINT_FIELDS_INVALID",
        "CHECKPOINT_PROFILE_INVALID",
        "CHECKPOINT_SCHEMA_VERSION_INVALID",
        "CANONICAL_PROFILE_MISMATCH",
        "CHECKPOINT_LOG_ID_INVALID",
        "CHECKPOINT_TREE_SIZE_INVALID",
        "CHECKPOINT_ROOT_HASH_INVALID",
        "CHECKPOINT_ISSUED_AT_INVALID",
        "CHECKPOINT_NOT_BEFORE_INVALID",
        "CHECKPOINT_NOT_AFTER_INVALID",
        "CHECKPOINT_ISSUER_INVALID",
        "CHECKPOINT_AUTHORITY_ID_INVALID",
        "CHECKPOINT_KEY_ID_INVALID",
        "CHECKPOINT_ALGORITHM_INVALID",
        "CHECKPOINT_SIGNATURE_ENCODING_INVALID",
        "CHECKPOINT_ID_INVALID",
    }
)


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


def _invalid_result(
    reasons: list[str] | tuple[str, ...],
    *,
    local_witnessed_freshness_valid: Any = False,
) -> TransparencyLogResult:
    return TransparencyLogResult(
        valid=False,
        local_witnessed_freshness_valid=(
            local_witnessed_freshness_valid is True
        ),
        entry_integrity_valid=False,
        log_checkpoint_signature_valid=False,
        log_checkpoint_authority_valid=False,
        log_checkpoint_freshness_valid=False,
        inclusion_valid=False,
        consistency_valid=False,
        view_consistency_valid=False,
        log_equivocation_detected=False,
        accepted_tree_size=None,
        accepted_root_hash=None,
        reason_codes=tuple(reasons),
    )


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _exact_mapping(value: Any, fields: set[str]) -> bool:
    return _is_mapping(value) and set(value) == fields


def _non_empty_string(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        canonical_bytes(value)
    except CanonicalizationError:
        return False
    return True


def _integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and abs(value) <= MAX_SAFE_INTEGER
    )


def _timestamp(value: Any) -> bool:
    return _integer(value) and value >= 0


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
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        return None
    if base64.b64encode(decoded).decode("ascii") != value:
        return None
    return decoded


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
        or len(audit_path) > MAX_PROOF_NODES
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
        or len(proof) > MAX_PROOF_NODES
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


def checkpoint_statement(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field: checkpoint.get(field)
        for field in _CHECKPOINT_STATEMENT_FIELDS
    }


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


def _checkpoint_shape_reasons(checkpoint: Any) -> list[str]:
    if not _is_mapping(checkpoint):
        return ["CHECKPOINT_INVALID"]
    reasons: list[str] = []
    _add(
        reasons,
        "CHECKPOINT_FIELDS_INVALID",
        set(checkpoint) != _CHECKPOINT_FIELDS,
    )
    _add(
        reasons,
        "CHECKPOINT_PROFILE_INVALID",
        checkpoint.get("profile_id") != CHECKPOINT_PROFILE_ID,
    )
    _add(
        reasons,
        "CHECKPOINT_SCHEMA_VERSION_INVALID",
        checkpoint.get("schema_version") != SCHEMA_VERSION,
    )
    _add(
        reasons,
        "CANONICAL_PROFILE_MISMATCH",
        checkpoint.get("canonical_profile") != CANONICAL_PROFILE,
    )
    _add(
        reasons,
        "CHECKPOINT_LOG_ID_INVALID",
        not _non_empty_string(checkpoint.get("log_id")),
    )
    _add(
        reasons,
        "CHECKPOINT_TREE_SIZE_INVALID",
        not _positive_integer(checkpoint.get("tree_size")),
    )
    _add(
        reasons,
        "CHECKPOINT_ROOT_HASH_INVALID",
        not _hex64(checkpoint.get("root_hash")),
    )
    _add(
        reasons,
        "CHECKPOINT_ISSUED_AT_INVALID",
        not _timestamp(checkpoint.get("issued_at_ms")),
    )
    _add(
        reasons,
        "CHECKPOINT_NOT_BEFORE_INVALID",
        not _timestamp(checkpoint.get("not_before_ms")),
    )
    _add(
        reasons,
        "CHECKPOINT_NOT_AFTER_INVALID",
        not _timestamp(checkpoint.get("not_after_ms")),
    )
    _add(
        reasons,
        "CHECKPOINT_ISSUER_INVALID",
        not _non_empty_string(checkpoint.get("issuer_id")),
    )
    _add(
        reasons,
        "CHECKPOINT_AUTHORITY_ID_INVALID",
        not _non_empty_string(checkpoint.get("log_authority_id")),
    )
    _add(
        reasons,
        "CHECKPOINT_KEY_ID_INVALID",
        not _non_empty_string(checkpoint.get("log_key_id")),
    )
    _add(
        reasons,
        "CHECKPOINT_ALGORITHM_INVALID",
        not _non_empty_string(checkpoint.get("signature_algorithm")),
    )
    signature = _decode_base64(checkpoint.get("signature"))
    _add(
        reasons,
        "CHECKPOINT_SIGNATURE_ENCODING_INVALID",
        signature is None or len(signature) != SIGNATURE_BYTES,
    )
    try:
        expected_id = compute_checkpoint_id(checkpoint)
    except CanonicalizationError:
        expected_id = None
    _add(
        reasons,
        "CHECKPOINT_ID_INVALID",
        checkpoint.get("checkpoint_id") != expected_id,
    )
    return reasons


def _authority_shape_reasons(authority: Any) -> list[str]:
    if not _is_mapping(authority):
        return ["LOG_AUTHORITY_INVALID"]
    reasons: list[str] = []
    _add(
        reasons,
        "LOG_AUTHORITY_FIELDS_INVALID",
        set(authority) != _AUTHORITY_FIELDS,
    )
    _add(
        reasons,
        "LOG_AUTHORITY_PROFILE_INVALID",
        authority.get("profile_id") != LOG_AUTHORITY_PROFILE_ID,
    )
    _add(
        reasons,
        "LOG_AUTHORITY_ID_INVALID",
        not _non_empty_string(authority.get("log_authority_id")),
    )
    allowed = authority.get("allowed_algorithms")
    _add(
        reasons,
        "LOG_ALLOWED_ALGORITHMS_INVALID",
        not isinstance(allowed, list)
        or not allowed
        or not all(_non_empty_string(value) for value in allowed)
        or len(set(allowed)) != len(allowed),
    )
    keys = authority.get("keys")
    if not isinstance(keys, list) or not keys:
        _add(reasons, "LOG_KEYS_INVALID", True)
        return reasons

    for index, key in enumerate(keys):
        if not _is_mapping(key):
            _add(reasons, f"LOG_KEY_INVALID:{index}", True)
            continue
        _add(
            reasons,
            f"LOG_KEY_FIELDS_INVALID:{index}",
            set(key) != _KEY_FIELDS,
        )
        specs = {
            "log_key_id": _non_empty_string,
            "issuer_id": _non_empty_string,
            "algorithm": _non_empty_string,
            "public_key_base64": _non_empty_string,
            "not_before_ms": _timestamp,
            "not_after_ms": _timestamp,
            "revoked": lambda value: isinstance(value, bool),
        }
        for field, predicate in specs.items():
            if field not in key or not predicate(key[field]):
                _add(
                    reasons,
                    f"LOG_KEY_SCHEMA_INVALID:{index}.{field}",
                    True,
                )
    return reasons


def _verify_checkpoint(
    checkpoint: Any,
    authority: Any,
    *,
    now_ms: Any,
) -> tuple[bool, bool, bool, bool, list[str]]:
    checkpoint_reasons = _checkpoint_shape_reasons(checkpoint)
    authority_reasons = _authority_shape_reasons(authority)
    reasons = [*checkpoint_reasons, *authority_reasons]
    checkpoint_integrity_valid = not checkpoint_reasons

    if not _is_mapping(checkpoint) or not _is_mapping(authority):
        return checkpoint_integrity_valid, False, False, False, reasons

    _add(
        reasons,
        "LOG_AUTHORITY_ID_MISMATCH",
        authority.get("log_authority_id")
        != checkpoint.get("log_authority_id"),
    )
    allowed = authority.get("allowed_algorithms")
    algorithm = checkpoint.get("signature_algorithm")
    algorithm_allowed = (
        algorithm == ED25519
        and isinstance(allowed, list)
        and ED25519 in allowed
    )
    _add(reasons, "LOG_ALGORITHM_NOT_ALLOWED", not algorithm_allowed)

    keys = authority.get("keys")
    matches: list[Mapping[str, Any]] = []
    if isinstance(keys, list):
        matches = [
            key
            for key in keys
            if _is_mapping(key)
            and key.get("log_key_id") == checkpoint.get("log_key_id")
        ]
    _add(reasons, "LOG_KEY_NOT_TRUSTED", len(matches) == 0)
    _add(reasons, "LOG_KEY_AMBIGUOUS", len(matches) > 1)

    signature_valid = False
    authority_valid = False
    key = matches[0] if len(matches) == 1 else None
    if key is not None:
        public_key = _decode_base64(key.get("public_key_base64"))
        signature = _decode_base64(checkpoint.get("signature"))
        key_material_valid = (
            public_key is not None and len(public_key) == PUBLIC_KEY_BYTES
        )
        signature_material_valid = (
            signature is not None and len(signature) == SIGNATURE_BYTES
        )
        _add(reasons, "LOG_KEY_MATERIAL_INVALID", not key_material_valid)
        _add(
            reasons,
            "LOG_KEY_ISSUER_MISMATCH",
            key.get("issuer_id") != checkpoint.get("issuer_id"),
        )
        _add(
            reasons,
            "LOG_KEY_ALGORITHM_MISMATCH",
            key.get("algorithm") != algorithm,
        )
        _add(reasons, "LOG_KEY_REVOKED", key.get("revoked") is True)

        key_interval_valid = (
            _timestamp(key.get("not_before_ms"))
            and _timestamp(key.get("not_after_ms"))
            and key["not_after_ms"] >= key["not_before_ms"]
        )
        _add(reasons, "LOG_KEY_VALIDITY_INVALID", not key_interval_valid)
        _add(
            reasons,
            "LOG_KEY_NOT_YET_VALID",
            key_interval_valid and now_ms < key["not_before_ms"],
        )
        _add(
            reasons,
            "LOG_KEY_EXPIRED",
            key_interval_valid and now_ms > key["not_after_ms"],
        )

        if (
            algorithm == ED25519
            and key.get("algorithm") == ED25519
            and key_material_valid
            and signature_material_valid
        ):
            try:
                Ed25519PublicKey.from_public_bytes(public_key).verify(
                    signature,
                    signed_checkpoint_payload(checkpoint),
                )
                signature_valid = True
            except (CanonicalizationError, InvalidSignature, ValueError):
                signature_valid = False
            _add(
                reasons,
                "CHECKPOINT_SIGNATURE_INVALID",
                not signature_valid,
            )

        authority_valid = (
            not authority_reasons
            and authority.get("profile_id") == LOG_AUTHORITY_PROFILE_ID
            and authority.get("log_authority_id")
            == checkpoint.get("log_authority_id")
            and algorithm_allowed
            and key_material_valid
            and key.get("issuer_id") == checkpoint.get("issuer_id")
            and key.get("algorithm") == algorithm
            and key.get("revoked") is False
            and key_interval_valid
            and key["not_before_ms"] <= now_ms <= key["not_after_ms"]
        )

    issued_at = checkpoint.get("issued_at_ms")
    not_before = checkpoint.get("not_before_ms")
    not_after = checkpoint.get("not_after_ms")
    validity_interval_valid = (
        _timestamp(not_before)
        and _timestamp(not_after)
        and not_after >= not_before
    )
    freshness_valid = (
        validity_interval_valid
        and _timestamp(issued_at)
        and issued_at <= now_ms
        and not_before <= now_ms <= not_after
    )
    _add(reasons, "CHECKPOINT_VALIDITY_INVALID", not validity_interval_valid)
    _add(
        reasons,
        "CHECKPOINT_NOT_YET_VALID",
        validity_interval_valid and now_ms < not_before,
    )
    _add(
        reasons,
        "CHECKPOINT_EXPIRED",
        validity_interval_valid and now_ms > not_after,
    )
    _add(
        reasons,
        "CHECKPOINT_ISSUED_IN_FUTURE",
        _timestamp(issued_at) and issued_at > now_ms,
    )

    return (
        checkpoint_integrity_valid,
        signature_valid,
        authority_valid,
        freshness_valid,
        reasons,
    )


def _target_valid(target: Any) -> bool:
    return (
        _exact_mapping(target, _TARGET_FIELDS)
        and _non_empty_string(target.get("log_id"))
        and _non_empty_string(target.get("trust_root_id"))
        and _positive_integer(target.get("snapshot_generation"))
        and _hex64(target.get("snapshot_digest"))
    )


def _entry_valid(entry: Any) -> bool:
    return (
        _exact_mapping(entry, _ENTRY_FIELDS)
        and entry.get("profile_id") == ENTRY_PROFILE_ID
        and entry.get("canonical_profile") == CANONICAL_PROFILE
        and entry.get("entry_type") == "trust-root-snapshot"
        and _non_empty_string(entry.get("log_id"))
        and _non_empty_string(entry.get("trust_root_id"))
        and _positive_integer(entry.get("snapshot_generation"))
        and _hex64(entry.get("snapshot_digest"))
    )


def verify_transparency_log(
    bundle: Any,
    *,
    now_ms: Any,
) -> TransparencyLogResult:
    try:
        bundle = copy.deepcopy(bundle)
    except Exception:
        return _invalid_result(["INPUT_SNAPSHOT_FAILED"])
    if not _is_mapping(bundle):
        return _invalid_result(["TRANSPARENCY_BUNDLE_INVALID"])
    local_valid = bundle.get("local_witnessed_freshness_valid") is True
    if not _timestamp(now_ms):
        return _invalid_result(
            ["NOW_MS_INVALID"],
            local_witnessed_freshness_valid=local_valid,
        )

    reasons: list[str] = []
    bundle_fields_valid = set(bundle) == _BUNDLE_FIELDS
    _add(
        reasons,
        "TRANSPARENCY_BUNDLE_FIELDS_INVALID",
        not bundle_fields_valid,
    )
    _add(
        reasons,
        "LOCAL_WITNESSED_FRESHNESS_INVALID",
        not local_valid,
    )

    target = bundle.get("target")
    entry = bundle.get("entry")
    target_valid = _target_valid(target)
    entry_shape_valid = _entry_valid(entry)
    if not _is_mapping(target) or not _is_mapping(entry):
        _add(reasons, "ENTRY_OR_TARGET_INVALID", True)
    else:
        _add(
            reasons,
            "TARGET_FIELDS_INVALID",
            set(target) != _TARGET_FIELDS,
        )
        _add(
            reasons,
            "TARGET_SCHEMA_INVALID",
            not target_valid and set(target) == _TARGET_FIELDS,
        )
        _add(
            reasons,
            "ENTRY_FIELDS_INVALID",
            set(entry) != _ENTRY_FIELDS,
        )
        _add(
            reasons,
            "ENTRY_PROFILE_INVALID",
            entry.get("profile_id") != ENTRY_PROFILE_ID,
        )
        _add(
            reasons,
            "ENTRY_CANONICAL_PROFILE_INVALID",
            entry.get("canonical_profile") != CANONICAL_PROFILE,
        )
        _add(
            reasons,
            "ENTRY_TYPE_INVALID",
            entry.get("entry_type") != "trust-root-snapshot",
        )

    entry_integrity_valid = target_valid and entry_shape_valid
    if _is_mapping(target) and _is_mapping(entry):
        for field, code in (
            ("log_id", "ENTRY_LOG_ID_MISMATCH"),
            ("trust_root_id", "ENTRY_TRUST_ROOT_MISMATCH"),
            ("snapshot_generation", "ENTRY_GENERATION_MISMATCH"),
            ("snapshot_digest", "ENTRY_SNAPSHOT_DIGEST_MISMATCH"),
        ):
            mismatch = entry.get(field) != target.get(field)
            _add(reasons, code, mismatch)
            entry_integrity_valid = entry_integrity_valid and not mismatch

    leaf_hash: str | None = None
    if _is_mapping(entry):
        try:
            leaf_hash = merkle_leaf_hash(entry)
        except (CanonicalizationError, TypeError, ValueError):
            _add(reasons, "ENTRY_CANONICALIZATION_FAILED", True)
            entry_integrity_valid = False

    checkpoint = bundle.get("checkpoint")
    authority = bundle.get("log_authority")
    (
        checkpoint_integrity_valid,
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
    else:
        fields_valid = set(verifier_checkpoint) == _VERIFIER_CHECKPOINT_FIELDS
        _add(
            reasons,
            "LOG_VERIFIER_CHECKPOINT_FIELDS_INVALID",
            not fields_valid,
        )
        profile_valid = (
            verifier_checkpoint.get("profile_id")
            == VERIFIER_CHECKPOINT_PROFILE_ID
        )
        _add(
            reasons,
            "LOG_VERIFIER_CHECKPOINT_INVALID",
            not profile_valid,
        )
        checkpoint_time = verifier_checkpoint.get("checkpointed_at_ms")
        if not _timestamp(checkpoint_time):
            _add(
                reasons,
                "LOG_VERIFIER_CHECKPOINT_TIME_INVALID",
                True,
            )
            consistency_valid = False
        elif checkpoint_time > now_ms:
            _add(
                reasons,
                "LOG_VERIFIER_CHECKPOINT_FROM_FUTURE",
                True,
            )
            consistency_valid = False

        if not fields_valid or not profile_valid:
            consistency_valid = False
        if (
            not _is_mapping(checkpoint)
            or verifier_checkpoint.get("log_id")
            != checkpoint.get("log_id")
        ):
            _add(reasons, "LOG_ID_MISMATCH", True)
            consistency_valid = False

        known_size = verifier_checkpoint.get("known_tree_size")
        known_root = verifier_checkpoint.get("known_root_hash")
        tree_size = (
            checkpoint.get("tree_size")
            if _is_mapping(checkpoint)
            else None
        )
        root_hash = (
            checkpoint.get("root_hash")
            if _is_mapping(checkpoint)
            else None
        )

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
                elif bundle.get("consistency_path") != []:
                    _add(
                        reasons,
                        "LOG_CONSISTENCY_PROOF_INVALID",
                        True,
                    )
                    consistency_valid = False
            else:
                proof_valid = verify_consistency_proof(
                    old_size=known_size,
                    new_size=tree_size,
                    old_root_hash=known_root,
                    new_root_hash=root_hash,
                    proof=bundle.get("consistency_path"),
                )
                _add(
                    reasons,
                    "LOG_CONSISTENCY_PROOF_INVALID",
                    not proof_valid,
                )
                consistency_valid = consistency_valid and proof_valid

    peers = bundle.get("peer_checkpoints")
    peer_evidence_valid = isinstance(peers, list)
    _add(
        reasons,
        "PEER_CHECKPOINTS_INVALID",
        not peer_evidence_valid,
    )
    seen_peer_ids: set[str] = set()
    if isinstance(peers, list) and _is_mapping(checkpoint):
        for index, peer in enumerate(peers):
            (
                peer_integrity,
                peer_signature,
                peer_authority,
                peer_freshness,
                _,
            ) = _verify_checkpoint(peer, authority, now_ms=now_ms)
            peer_id = (
                peer.get("checkpoint_id")
                if _is_mapping(peer)
                else None
            )
            duplicate = (
                isinstance(peer_id, str)
                and peer_id in seen_peer_ids
            )
            if isinstance(peer_id, str):
                seen_peer_ids.add(peer_id)
            _add(
                reasons,
                "DUPLICATE_PEER_CHECKPOINT",
                duplicate,
            )
            peer_valid = (
                peer_integrity
                and peer_signature
                and peer_authority
                and peer_freshness
                and _is_mapping(peer)
                and peer.get("log_id") == checkpoint.get("log_id")
                and not duplicate
            )
            if not peer_valid:
                _add(
                    reasons,
                    f"PEER_CHECKPOINT_INVALID:{index}",
                    True,
                )
                peer_evidence_valid = False
                continue
            if (
                peer.get("tree_size") == checkpoint.get("tree_size")
                and peer.get("root_hash") != checkpoint.get("root_hash")
            ):
                _add(reasons, "LOG_EQUIVOCATION_DETECTED", True)
                equivocation_detected = True

    view_consistency_valid = (
        peer_evidence_valid and not equivocation_detected
    )
    valid = (
        bundle_fields_valid
        and local_valid
        and entry_integrity_valid
        and checkpoint_integrity_valid
        and checkpoint_signature_valid
        and checkpoint_authority_valid
        and checkpoint_freshness_valid
        and inclusion_valid
        and consistency_valid
        and view_consistency_valid
        and not reasons
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
        accepted_tree_size=(
            checkpoint.get("tree_size")
            if valid and _is_mapping(checkpoint)
            else None
        ),
        accepted_root_hash=(
            checkpoint.get("root_hash")
            if valid and _is_mapping(checkpoint)
            else None
        ),
        reason_codes=tuple(reasons),
    )
