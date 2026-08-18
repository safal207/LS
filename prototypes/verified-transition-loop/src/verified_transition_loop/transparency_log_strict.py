from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .transparency_log import verify_transparency_log as _verify_transparency_log_raw

_CHECKPOINT_INTEGRITY_REASONS = frozenset(
    {
        "CHECKPOINT_INVALID",
        "CHECKPOINT_PROFILE_INVALID",
        "CHECKPOINT_SCHEMA_VERSION_INVALID",
        "CHECKPOINT_LOG_ID_INVALID",
        "CHECKPOINT_TREE_SIZE_INVALID",
        "CHECKPOINT_ROOT_HASH_INVALID",
        "CHECKPOINT_ISSUER_INVALID",
        "CHECKPOINT_AUTHORITY_ID_INVALID",
        "CHECKPOINT_KEY_ID_INVALID",
        "CHECKPOINT_ALGORITHM_INVALID",
        "CHECKPOINT_SIGNATURE_ENCODING_INVALID",
        "CHECKPOINT_ID_INVALID",
    }
)


@dataclass(frozen=True)
class StrictTransparencyLogResult:
    valid: bool
    local_witnessed_freshness_valid: bool
    entry_integrity_valid: bool
    log_checkpoint_integrity_valid: bool
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


def verify_transparency_log(bundle: Any, *, now_ms: Any) -> StrictTransparencyLogResult:
    """Fail-closed public v0.14 verifier.

    The low-level Merkle/crypto engine records structural checkpoint failures as
    reason codes. This public boundary makes those codes load-bearing rather than
    diagnostic: a malformed checkpoint can never become valid merely because its
    signature, authority, freshness, inclusion, and consistency are otherwise
    self-consistent.
    """

    raw = _verify_transparency_log_raw(bundle, now_ms=now_ms)
    checkpoint_integrity_valid = not any(
        reason in _CHECKPOINT_INTEGRITY_REASONS for reason in raw.reason_codes
    )
    return StrictTransparencyLogResult(
        valid=raw.valid and checkpoint_integrity_valid,
        local_witnessed_freshness_valid=raw.local_witnessed_freshness_valid,
        entry_integrity_valid=raw.entry_integrity_valid,
        log_checkpoint_integrity_valid=checkpoint_integrity_valid,
        log_checkpoint_signature_valid=raw.log_checkpoint_signature_valid,
        log_checkpoint_authority_valid=raw.log_checkpoint_authority_valid,
        log_checkpoint_freshness_valid=raw.log_checkpoint_freshness_valid,
        inclusion_valid=raw.inclusion_valid,
        consistency_valid=raw.consistency_valid,
        view_consistency_valid=raw.view_consistency_valid,
        log_equivocation_detected=raw.log_equivocation_detected,
        accepted_tree_size=raw.accepted_tree_size,
        accepted_root_hash=raw.accepted_root_hash,
        reason_codes=raw.reason_codes,
    )
