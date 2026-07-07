#!/usr/bin/env python3
"""Decision-core tests for GitHub merge preflight v0.1."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import github_merge_preflight_core_v0_1 as core


def make_input(head: str = "a" * 40, signal: str = "USER_APPROVED") -> dict:
    binding = core.exact_binding("safal207/LS", 813, head)
    actor_type = "USER" if signal.startswith("USER_") else "AGENT"
    return {
        "repository": "safal207/LS",
        "pull_request_number": 813,
        "expected_head_sha": head,
        "gateway_url": "in-process://review-decision-gateway-v0.1",
        "approval": {
            "approval_id": core.expected_approval_id(binding),
            "signal": signal,
            "actor": {"type": actor_type, "id": "operator-1"},
            "reason": "exact-bound review decision",
            "evidence_ref": None,
            "exact_bindings_match": True,
            "expiry_policy_configured": False,
        },
    }


def approved_response(value: dict) -> dict:
    validated = core.validate_input(value)
    request_id = "merge-preflight-" + validated["binding_digest"][:24]
    return {
        "gateway_version": core.GATEWAY_VERSION,
        "request_id": request_id,
        "adapter": {"valid": True, "errors": []},
        "projection": {
            "durable_event_type": "UserApproved",
            "authority_state": "APPROVED",
            "requester_state": "ATTACHED",
            "presentation_state": "VISIBLE",
            "execution_state": "UNUSED",
            "outward_status": "APPROVED",
            "user_message": "Approved for the exact reviewed action. Nothing has executed yet.",
            "execution_blocked": False,
            "execution_claim_allowed": True,
            "resolution": {
                "event_type": "UserApproved",
                "actor_type": "USER",
                "actor_id": "operator-1",
                "reason": "exact-bound review decision",
                "evidence_ref": None,
            },
        },
        "side_effects_performed": False,
    }


class MergePreflightCoreTests(unittest.TestCase):
    def test_exact_bound_approval_allows_only_downstream_claim(self) -> None:
        value = make_input()
        validated = core.validate_input(value)
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        result = core.evaluate(value, approved_response(value), request_id)
        self.assertEqual("ALLOW_CLAIM", result["decision"])
        self.assertTrue(result["handoff"]["commit_before_effect_eligible"])
        self.assertFalse(result["handoff"]["execution_authorized"])
        self.assertFalse(result["merge_performed"])
        self.assertFalse(result["side_effects_performed"])

    def test_approval_cannot_be_reused_after_head_changes(self) -> None:
        value = make_input("a" * 40)
        value["expected_head_sha"] = "b" * 40
        with self.assertRaises(core.PreflightError) as raised:
            core.validate_input(value)
        self.assertEqual("APPROVAL_BINDING_MISMATCH", raised.exception.code)

    def test_gateway_side_effect_report_blocks(self) -> None:
        value = make_input()
        validated = core.validate_input(value)
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        response = approved_response(value)
        response["side_effects_performed"] = True
        result = core.evaluate(value, response, request_id)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("GATEWAY_SIDE_EFFECT_VIOLATION", result["reason_code"])

    def test_invented_user_actor_blocks(self) -> None:
        value = make_input()
        validated = core.validate_input(value)
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        response = approved_response(value)
        response["projection"]["resolution"]["actor_type"] = "AGENT"
        result = core.evaluate(value, response, request_id)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("USER_APPROVAL_NOT_PROVEN", result["reason_code"])

    def test_claimed_execution_blocks(self) -> None:
        value = make_input()
        validated = core.validate_input(value)
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        response = approved_response(value)
        response["projection"]["execution_state"] = "CLAIMED"
        result = core.evaluate(value, response, request_id)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("EXECUTION_ALREADY_CLAIMED", result["reason_code"])

    def test_request_id_mismatch_blocks(self) -> None:
        value = make_input()
        result = core.evaluate(value, approved_response(value), "wrong-request-id")
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("GATEWAY_REQUEST_ID_MISMATCH", result["reason_code"])

    def test_gateway_version_mismatch_blocks(self) -> None:
        value = make_input()
        validated = core.validate_input(value)
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        response = approved_response(value)
        response["gateway_version"] = "future-unsafe-version"
        result = core.evaluate(value, response, request_id)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("GATEWAY_VERSION_MISMATCH", result["reason_code"])

    def test_result_is_deterministic(self) -> None:
        value = make_input()
        validated = core.validate_input(value)
        request_id = "merge-preflight-" + validated["binding_digest"][:24]
        first = core.evaluate(value, approved_response(value), request_id)
        second = core.evaluate(deepcopy(value), deepcopy(approved_response(value)), request_id)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
