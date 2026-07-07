#!/usr/bin/env python3
"""Pure exact-base/head binding and decision core for GitHub merge preflight v0.1."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

PREFLIGHT_VERSION = "ls-github-merge-preflight-v0.1"
GATEWAY_VERSION = "ls-review-decision-gateway-v0.1"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class PreflightError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def exact_binding(
    repository: str,
    pull_request_number: int,
    expected_base_sha: str,
    expected_head_sha: str,
) -> dict[str, Any]:
    return {
        "action": "github.merge_pull_request",
        "repository": repository,
        "pull_request_number": pull_request_number,
        "expected_base_sha": expected_base_sha,
        "expected_head_sha": expected_head_sha,
    }


def binding_digest(binding: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(binding)).hexdigest()


def expected_approval_id(binding: dict[str, Any]) -> str:
    return "github-merge:" + binding_digest(binding)


def validate_input(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PreflightError("INVALID_INPUT", "input must be an object")
    allowed = {
        "repository",
        "pull_request_number",
        "expected_base_sha",
        "expected_head_sha",
        "gateway_url",
        "approval",
    }
    extra = set(value) - allowed
    if extra:
        raise PreflightError("INVALID_INPUT", f"unsupported input fields: {sorted(extra)}")

    repository = value.get("repository")
    pr_number = value.get("pull_request_number")
    base_sha = value.get("expected_base_sha")
    head_sha = value.get("expected_head_sha")
    approval = value.get("approval")
    gateway_url = value.get("gateway_url")

    if not isinstance(repository, str) or not REPOSITORY_PATTERN.fullmatch(repository):
        raise PreflightError("INVALID_REPOSITORY", "repository must match owner/name")
    if type(pr_number) is not int or pr_number <= 0:
        raise PreflightError("INVALID_PULL_REQUEST", "pull_request_number must be a positive integer")
    if not isinstance(base_sha, str) or not SHA_PATTERN.fullmatch(base_sha):
        raise PreflightError("INVALID_EXACT_BASE", "expected_base_sha must be 40 lowercase hexadecimal characters")
    if not isinstance(head_sha, str) or not SHA_PATTERN.fullmatch(head_sha):
        raise PreflightError("INVALID_EXACT_HEAD", "expected_head_sha must be 40 lowercase hexadecimal characters")
    if not isinstance(gateway_url, str) or not gateway_url:
        raise PreflightError("INVALID_GATEWAY_URL", "gateway_url is required")
    if not isinstance(approval, dict):
        raise PreflightError("INVALID_APPROVAL", "approval must be an object")

    binding = exact_binding(repository, pr_number, base_sha, head_sha)
    digest = binding_digest(binding)
    if approval.get("approval_id") != "github-merge:" + digest:
        raise PreflightError(
            "APPROVAL_BINDING_MISMATCH",
            "approval_id does not bind the exact repository, PR, base, and head",
        )
    if approval.get("exact_bindings_match") is not True:
        raise PreflightError("APPROVAL_BINDING_MISMATCH", "approval must declare exact bindings matched")

    return {
        "binding": binding,
        "binding_digest": digest,
        "gateway_url": gateway_url,
        "approval": deepcopy(approval),
    }


def validate_gateway_response(value: Any, expected_request_id: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PreflightError("GATEWAY_PROTOCOL_ERROR", "gateway response must be an object")
    if value.get("gateway_version") != GATEWAY_VERSION:
        raise PreflightError("GATEWAY_VERSION_MISMATCH", "unexpected gateway version")
    if value.get("request_id") != expected_request_id:
        raise PreflightError("GATEWAY_REQUEST_ID_MISMATCH", "gateway request id does not match")
    if value.get("side_effects_performed") is not False:
        raise PreflightError("GATEWAY_SIDE_EFFECT_VIOLATION", "gateway reported side effects")

    adapter = value.get("adapter")
    projection = value.get("projection")
    if not isinstance(adapter, dict) or not isinstance(projection, dict):
        raise PreflightError("GATEWAY_PROTOCOL_ERROR", "adapter and projection objects are required")
    if type(adapter.get("valid")) is not bool or not isinstance(adapter.get("errors"), list):
        raise PreflightError("GATEWAY_PROTOCOL_ERROR", "adapter validity is malformed")
    if any(not isinstance(error, str) for error in adapter["errors"]):
        raise PreflightError("GATEWAY_PROTOCOL_ERROR", "adapter errors must be strings")
    return value


def classify(response: dict[str, Any], approval: dict[str, Any]) -> tuple[str, str]:
    adapter = response["adapter"]
    projection = response["projection"]
    if adapter["valid"] is not True or adapter["errors"]:
        return "BLOCK", "ADAPTER_REJECTED"
    if approval.get("signal") != "USER_APPROVED":
        return "BLOCK", "EXPLICIT_USER_APPROVAL_REQUIRED"

    authority = projection.get("authority_state")
    if authority == "PENDING":
        return "BLOCK", "PENDING_AUTHORITY"
    if authority in {"REJECTED", "EXPIRED", "INVALIDATED", "LOST"}:
        return "BLOCK", "AUTHORITY_" + authority
    if authority != "APPROVED":
        return "BLOCK", "AUTHORITY_NOT_APPROVED"
    if projection.get("durable_event_type") != "UserApproved":
        return "BLOCK", "USER_APPROVAL_NOT_PROVEN"

    resolution = projection.get("resolution")
    if not isinstance(resolution, dict) or resolution.get("event_type") != "UserApproved":
        return "BLOCK", "USER_APPROVAL_NOT_PROVEN"
    if resolution.get("actor_type") not in {"USER", "REVIEWER"}:
        return "BLOCK", "USER_APPROVAL_NOT_PROVEN"
    if projection.get("execution_state") != "UNUSED":
        return "BLOCK", "EXECUTION_ALREADY_CLAIMED"
    if projection.get("execution_claim_allowed") is not True:
        return "BLOCK", "EXECUTION_CLAIM_NOT_ALLOWED"
    if projection.get("execution_blocked") is not False:
        return "BLOCK", "EXECUTION_BLOCKED"
    return "ALLOW_CLAIM", "EXACT_BASE_HEAD_USER_APPROVAL_VERIFIED"


def envelope(
    validated: dict[str, Any] | None,
    decision: str,
    reason_code: str,
    *,
    detail: str | None = None,
    gateway_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "preflight_version": PREFLIGHT_VERSION,
        "decision": decision,
        "reason_code": reason_code,
        "detail": detail,
        "binding": deepcopy(validated["binding"]) if validated else None,
        "binding_digest": validated["binding_digest"] if validated else None,
        "gateway_request_id": gateway_response.get("request_id") if gateway_response else None,
        "gateway_projection": deepcopy(gateway_response.get("projection")) if gateway_response else None,
        "handoff": {
            "commit_before_effect_eligible": decision == "ALLOW_CLAIM",
            "execution_authorized": False,
        },
        "merge_performed": False,
        "side_effects_performed": False,
    }


def evaluate(value: Any, gateway_response: Any, expected_request_id: str) -> dict[str, Any]:
    validated: dict[str, Any] | None = None
    try:
        validated = validate_input(value)
        response = validate_gateway_response(gateway_response, expected_request_id)
        decision, reason = classify(response, validated["approval"])
        return envelope(validated, decision, reason, gateway_response=response)
    except PreflightError as exc:
        return envelope(validated, "BLOCK", exc.code, detail=exc.detail)
