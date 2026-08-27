#!/usr/bin/env python3
"""Fail-closed evaluation of a ReviewDecision Gateway projection."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

PREFLIGHT_VERSION = "ls-github-merge-preflight-v0.1"
GATEWAY_VERSION = "ls-review-decision-gateway-v0.1"


class ProjectionError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def validate_response(value: Any, expected_request_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectionError("GATEWAY_PROTOCOL_ERROR", "Gateway response must be an object")
    if value.get("gateway_version") != GATEWAY_VERSION:
        raise ProjectionError("GATEWAY_VERSION_MISMATCH", "unexpected Gateway version")
    if value.get("request_id") != expected_request_id:
        raise ProjectionError("GATEWAY_REQUEST_ID_MISMATCH", "Gateway request id mismatch")
    if value.get("side_effects_performed") is not False:
        raise ProjectionError("GATEWAY_SIDE_EFFECT_VIOLATION", "Gateway reported a side effect")

    adapter = value.get("adapter")
    projection = value.get("projection")
    if not isinstance(adapter, dict) or not isinstance(projection, dict):
        raise ProjectionError("GATEWAY_PROTOCOL_ERROR", "adapter and projection objects are required")
    if type(adapter.get("valid")) is not bool or not isinstance(adapter.get("errors"), list):
        raise ProjectionError("GATEWAY_PROTOCOL_ERROR", "adapter validity is malformed")
    if any(not isinstance(error, str) for error in adapter["errors"]):
        raise ProjectionError("GATEWAY_PROTOCOL_ERROR", "adapter errors must be strings")
    return value


def classify(response: dict[str, Any], approval: dict[str, Any]) -> tuple[str, str]:
    adapter = response["adapter"]
    projection = response["projection"]
    if adapter["valid"] is not True or adapter["errors"]:
        return "BLOCK", "ADAPTER_REJECTED"
    if approval.get("signal") != "USER_APPROVED":
        return "BLOCK", "EXPLICIT_USER_APPROVAL_REQUIRED"
    if projection.get("authority_state") == "PENDING":
        return "BLOCK", "PENDING_AUTHORITY"
    if projection.get("authority_state") != "APPROVED":
        return "BLOCK", "AUTHORITY_NOT_APPROVED"
    if projection.get("durable_event_type") != "UserApproved":
        return "BLOCK", "USER_APPROVAL_NOT_PROVEN"

    actor = approval.get("actor")
    resolution = projection.get("resolution")
    if not isinstance(actor, dict) or actor.get("type") not in {"USER", "REVIEWER"}:
        return "BLOCK", "USER_APPROVAL_NOT_PROVEN"
    if not isinstance(resolution, dict) or resolution.get("event_type") != "UserApproved":
        return "BLOCK", "USER_APPROVAL_NOT_PROVEN"
    if resolution.get("actor_type") != actor.get("type") or resolution.get("actor_id") != actor.get("id"):
        return "BLOCK", "APPROVAL_RESOLUTION_MISMATCH"
    if resolution.get("reason") != approval.get("reason"):
        return "BLOCK", "APPROVAL_RESOLUTION_MISMATCH"
    if resolution.get("evidence_ref") != approval.get("evidence_ref"):
        return "BLOCK", "APPROVAL_RESOLUTION_MISMATCH"
    if projection.get("execution_state") != "UNUSED":
        return "BLOCK", "EXECUTION_ALREADY_CLAIMED"
    if projection.get("execution_claim_allowed") is not True or projection.get("execution_blocked") is not False:
        return "BLOCK", "EXECUTION_CLAIM_NOT_ALLOWED"
    return "ALLOW_CLAIM", "EXACT_EVIDENCE_BOUND_APPROVAL_PROJECTED"


def envelope(
    validated: dict[str, Any] | None,
    decision: str,
    reason_code: str,
    *,
    detail: str | None = None,
    response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "preflight_version": PREFLIGHT_VERSION,
        "decision": decision,
        "reason_code": reason_code,
        "detail": detail,
        "binding": deepcopy(validated["binding"]) if validated else None,
        "binding_digest": validated["binding_digest"] if validated else None,
        "gateway_request_id": response.get("request_id") if response else None,
        "gateway_projection": deepcopy(response.get("projection")) if response else None,
        "handoff": {
            "commit_before_effect_eligible": decision == "ALLOW_CLAIM",
            "live_evidence_verified": False,
            "authorization_bundle_verified": False,
            "execution_authorized": False,
        },
        "merge_performed": False,
        "side_effects_performed": False,
    }
