#!/usr/bin/env python3
"""Canonical merge binding for repository, PR, base, head, and evidence bytes."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any

REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
GATEWAY_MODE = "in-process://review-decision-gateway-v0.1"


class BindingError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def make_binding(
    repository: str,
    pull_request_number: int,
    expected_base_sha: str,
    expected_head_sha: str,
    expected_evidence_sha256: str,
) -> dict[str, Any]:
    return {
        "action": "github.merge_pull_request",
        "repository": repository,
        "pull_request_number": pull_request_number,
        "expected_base_sha": expected_base_sha,
        "expected_head_sha": expected_head_sha,
        "expected_evidence_sha256": expected_evidence_sha256,
    }


def binding_digest(binding: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(binding)).hexdigest()


def approval_id(binding: dict[str, Any]) -> str:
    return "github-merge:" + binding_digest(binding)


def evidence_ref(evidence_sha256: str) -> str:
    return "exact-head-evidence:" + evidence_sha256


def validate(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BindingError("INVALID_INPUT", "input must be an object")
    allowed = {
        "repository",
        "pull_request_number",
        "expected_base_sha",
        "expected_head_sha",
        "expected_evidence_sha256",
        "gateway_mode",
        "approval",
    }
    extra = set(value) - allowed
    if extra:
        raise BindingError("INVALID_INPUT", f"unsupported fields: {sorted(extra)}")

    repository = value.get("repository")
    pr_number = value.get("pull_request_number")
    base_sha = value.get("expected_base_sha")
    head_sha = value.get("expected_head_sha")
    evidence_sha256 = value.get("expected_evidence_sha256")
    approval = value.get("approval")

    if not isinstance(repository, str) or not REPOSITORY_PATTERN.fullmatch(repository):
        raise BindingError("INVALID_REPOSITORY", "repository must match owner/name")
    if type(pr_number) is not int or pr_number <= 0:
        raise BindingError("INVALID_PULL_REQUEST", "pull_request_number must be positive")
    if not isinstance(base_sha, str) or not SHA1_PATTERN.fullmatch(base_sha):
        raise BindingError("INVALID_EXACT_BASE", "expected_base_sha must be lowercase 40-character hex")
    if not isinstance(head_sha, str) or not SHA1_PATTERN.fullmatch(head_sha):
        raise BindingError("INVALID_EXACT_HEAD", "expected_head_sha must be lowercase 40-character hex")
    if not isinstance(evidence_sha256, str) or not SHA256_PATTERN.fullmatch(evidence_sha256):
        raise BindingError("INVALID_EVIDENCE_DIGEST", "expected_evidence_sha256 must be lowercase 64-character hex")
    if value.get("gateway_mode") != GATEWAY_MODE:
        raise BindingError("NON_LOCAL_GATEWAY", "v0.1 accepts only the in-process Gateway")
    if not isinstance(approval, dict):
        raise BindingError("INVALID_APPROVAL", "approval must be an object")

    binding = make_binding(repository, pr_number, base_sha, head_sha, evidence_sha256)
    digest = binding_digest(binding)
    if approval.get("approval_id") != "github-merge:" + digest:
        raise BindingError("APPROVAL_BINDING_MISMATCH", "approval_id does not match the exact binding")
    if approval.get("exact_bindings_match") is not True:
        raise BindingError("APPROVAL_BINDING_MISMATCH", "exact_bindings_match must be true")
    if approval.get("evidence_ref") != evidence_ref(evidence_sha256):
        raise BindingError("EVIDENCE_BINDING_MISMATCH", "approval evidence_ref does not match evidence digest")

    return {
        "binding": binding,
        "binding_digest": digest,
        "approval": deepcopy(approval),
    }
