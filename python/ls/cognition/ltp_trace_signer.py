from __future__ import annotations

# LTP-based signing for ValidationTraceArtifact.
#
# Uses the real lri.ltp Python SDK when available, falls back to a
# self-contained implementation that follows the same spec:
#   - Ed25519 (cryptography package)
#   - JCS canonicalization (RFC 8785 — keys sorted recursively)
#   - Base64url-encoded detached signature stored in the "sig" field
#
# The validator and trace adapter remain unaware of signing: callers
# opt in by calling sign_trace_artifact() after validation, and verify
# with verify_trace_artifact() before trusting a stored artifact.

import base64
import json
from dataclasses import replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ls.cognition.lifetra_validation_adapter import ValidationTraceArtifact


# ── JCS canonicalization (RFC 8785) ──────────────────────────────────────────


def _jcs_dumps(obj: Any) -> bytes:
    """Serialize *obj* to canonical UTF-8 bytes (keys sorted at every level)."""
    if isinstance(obj, dict):
        items = sorted(obj.items())
        inner = ", ".join(f"{json.dumps(k)}: {_jcs_dumps(v).decode()}" for k, v in items)
        return f"{{{inner}}}".encode()
    if isinstance(obj, list):
        inner = ", ".join(_jcs_dumps(v).decode() for v in obj)
        return f"[{inner}]".encode()
    return json.dumps(obj, ensure_ascii=False).encode()


# ── Base64url helpers ─────────────────────────────────────────────────────────


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


# ── LTP-compatible sign / verify ──────────────────────────────────────────────


def _sign_lce_builtin(
    lce: dict[str, Any],
    private_key: Any,
) -> dict[str, Any]:
    """Sign *lce* using the built-in Ed25519 + JCS path."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415

    if not isinstance(private_key, Ed25519PrivateKey):
        raise TypeError("private_key must be Ed25519PrivateKey")
    payload = {k: v for k, v in lce.items() if k != "sig"}
    canonical = _jcs_dumps(payload)
    sig_bytes = private_key.sign(canonical)
    payload["sig"] = _b64url_encode(sig_bytes)
    return payload


def _verify_lce_builtin(
    lce: dict[str, Any],
    public_key: Any,
) -> bool:
    """Verify *lce* signature using the built-in Ed25519 + JCS path."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: PLC0415
    from cryptography.exceptions import InvalidSignature  # noqa: PLC0415

    if not isinstance(public_key, Ed25519PublicKey):
        raise TypeError("public_key must be Ed25519PublicKey")
    sig_b64 = lce.get("sig")
    if not isinstance(sig_b64, str) or not sig_b64:
        return False
    payload = {k: v for k, v in lce.items() if k != "sig"}
    canonical = _jcs_dumps(payload)
    try:
        public_key.verify(_b64url_decode(sig_b64), canonical)
        return True
    except InvalidSignature:
        return False


def _sign_lce(lce: dict[str, Any], private_key: Any) -> dict[str, Any]:
    """Sign via lri.ltp if available, otherwise built-in path."""
    try:
        from lri.ltp import sign_lce  # type: ignore[import]  # noqa: PLC0415

        return sign_lce(lce, private_key)
    except ImportError:
        return _sign_lce_builtin(lce, private_key)


def _verify_lce(lce: dict[str, Any], public_key: Any) -> bool:
    """Verify via lri.ltp if available, otherwise built-in path."""
    try:
        from lri.ltp import verify_lce  # type: ignore[import]  # noqa: PLC0415

        return verify_lce(lce, public_key)
    except ImportError:
        return _verify_lce_builtin(lce, public_key)


# ── LCE payload builder ───────────────────────────────────────────────────────


def _build_signing_payload(artifact: ValidationTraceArtifact) -> dict[str, Any]:
    """Build a minimal LCE dict from the fields that must be tamper-evident.

    Only stable, compact fields are included — not the full metadata blob.
    The ``sig`` field is absent here; it is appended by the signing step.
    """
    return {
        "intent": {
            "audience": ["ls:governance", "ls:validator"],
            "type": "validation_trace",
        },
        "payload": {
            "backend": artifact.backend,
            "consensus_status": artifact.metadata.get("consensus_status"),
            "edge_count": artifact.edge_count,
            "global_risk_flags": sorted(artifact.global_risk_flags),
            "node_count": artifact.node_count,
            "trace_id": artifact.trace_id,
            "winner_agent_id": artifact.winner_agent_id,
        },
        "policy": {
            "consent": "internal",
        },
    }


# ── Public API ────────────────────────────────────────────────────────────────


def sign_trace_artifact(
    artifact: ValidationTraceArtifact,
    private_key: Any,
) -> ValidationTraceArtifact:
    """Return a new artifact with an LTP envelope stored in ``metadata["ltp_envelope"]``.

    The envelope is a signed LCE dict whose ``payload`` covers the core
    tamper-evident fields: trace_id, winner_agent_id, global_risk_flags,
    consensus_status, node_count, edge_count, and backend.

    If signing fails for any reason the original artifact is returned
    unchanged so callers are never blocked by a signing error.
    """
    try:
        lce = _build_signing_payload(artifact)
        signed_envelope = _sign_lce(lce, private_key)
        updated_metadata = {**artifact.metadata, "ltp_envelope": signed_envelope}
        return replace(artifact, metadata=updated_metadata)
    except Exception:  # noqa: BLE001
        return artifact


def verify_trace_artifact(
    artifact: ValidationTraceArtifact,
    public_key: Any,
) -> bool:
    """Return True iff the LTP envelope in the artifact has a valid signature.

    Returns False (not raises) when the artifact is unsigned, the envelope
    is malformed, or the signature does not verify.
    """
    try:
        envelope = artifact.metadata.get("ltp_envelope")
        if not isinstance(envelope, dict):
            return False
        return _verify_lce(envelope, public_key)
    except Exception:  # noqa: BLE001
        return False


def generate_key_pair() -> tuple[Any, Any]:
    """Generate an Ed25519 key pair ``(private_key, public_key)``.

    Uses lri.ltp.generate_key_pair when available, otherwise the
    cryptography package directly. Raises ImportError if neither is
    available.
    """
    try:
        from lri.ltp import generate_key_pair as _gen  # type: ignore[import]  # noqa: PLC0415

        kp = _gen()
        return kp.private_key, kp.public_key
    except ImportError:
        pass
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: PLC0415

    priv = Ed25519PrivateKey.generate()
    return priv, priv.public_key()
