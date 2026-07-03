"""Protocol hardening layer for Route Artifact v2.

This module patches the low-level verifier with protocol-defined promotion floors
and replay evidence digest verification, then re-exports the public API used by
CLI and contract tests.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

import route_artifact as _core

PROTOCOL_PROMOTION_FLOORS = {
    "minimum_t0_runs": 20,
    "minimum_repositories": 2,
    "minimum_task_variants": 2,
    "minimum_sealed_honeypot_runs": 1,
}

_ORIGINAL_VERIFY_REPLAY = _core.verify_replay
_ORIGINAL_VERIFY_PROMOTION = _core.verify_promotion


def replay_evidence_payload(replay: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical replay fields protected by evidence_digest."""
    return {
        "command": replay.get("command"),
        "expected_exit_code": replay.get("expected_exit_code"),
        "observed_exit_code": replay.get("observed_exit_code"),
        "assertions": replay.get("assertions"),
        "passed": replay.get("passed"),
    }


def compute_replay_evidence_digest(replay: Mapping[str, Any]) -> str:
    """Content-address the protected replay evidence payload."""
    payload = replay_evidence_payload(replay)
    return hashlib.sha256(
        _core.canonical_json(payload).encode("utf-8")
    ).hexdigest()


def verify_replay(value: Any) -> None:
    """Verify replay semantics and bind evidence_digest to replay bytes."""
    _ORIGINAL_VERIFY_REPLAY(value)
    replay = _core.obj(value, "verification.replay")
    expected = compute_replay_evidence_digest(replay)
    if replay["evidence_digest"] != expected:
        _core.fail(
            "ROUTE-V2-EVIDENCE",
            f"replay evidence digest mismatch: expected {expected}",
        )


def verify_promotion(route: Mapping[str, Any]) -> None:
    """Reject artifacts that attempt to weaken protocol promotion floors."""
    policy = _core.obj(route.get("promotion_policy"), "route.promotion_policy")
    for key, expected in PROTOCOL_PROMOTION_FLOORS.items():
        observed = policy.get(key)
        if observed != expected:
            _core.fail(
                "ROUTE-V2-POLICY",
                f"{key} must equal protocol floor {expected}, got {observed}",
            )
    _ORIGINAL_VERIFY_PROMOTION(route)


# The low-level verifier resolves these names from its own module globals.
# Patching them once makes all re-exported entry points enforce this protocol.
_core.verify_replay = verify_replay
_core.verify_promotion = verify_promotion

RouteArtifactError = _core.RouteArtifactError
artifact_ref = _core.artifact_ref
build_registry_projection = _core.build_registry_projection
canonical_json = _core.canonical_json
compute_content_digest = _core.compute_content_digest
verify_immutable_update = _core.verify_immutable_update
verify_route_artifact = _core.verify_route_artifact

__all__ = [
    "PROTOCOL_PROMOTION_FLOORS",
    "RouteArtifactError",
    "artifact_ref",
    "build_registry_projection",
    "canonical_json",
    "compute_content_digest",
    "compute_replay_evidence_digest",
    "replay_evidence_payload",
    "verify_immutable_update",
    "verify_promotion",
    "verify_replay",
    "verify_route_artifact",
]
