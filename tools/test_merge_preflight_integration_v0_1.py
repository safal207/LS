#!/usr/bin/env python3
"""In-process Gateway integration tests for merge preflight v0.1."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import github_merge_preflight_core_v0_1 as core
import run_github_merge_preflight_v0_1 as runner


def make_input(signal: str = "USER_APPROVED", head: str = "a" * 40) -> dict:
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


class MergePreflightIntegrationTests(unittest.TestCase):
    def test_explicit_approval_allows_only_downstream_claim(self) -> None:
        result = runner.run(make_input())
        self.assertEqual("ALLOW_CLAIM", result["decision"])
        self.assertTrue(result["handoff"]["commit_before_effect_eligible"])
        self.assertFalse(result["handoff"]["execution_authorized"])
        self.assertFalse(result["merge_performed"])
        self.assertFalse(result["side_effects_performed"])

    def test_requester_cancellation_preserves_pending_authority(self) -> None:
        result = runner.run(make_input("REQUESTER_CANCELLED"))
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("PENDING", result["gateway_projection"]["authority_state"])
        self.assertEqual("CANCELLED", result["gateway_projection"]["requester_state"])
        self.assertFalse(result["merge_performed"])

    def test_user_rejection_blocks(self) -> None:
        result = runner.run(make_input("USER_REJECTED"))
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("REJECTED", result["gateway_projection"]["authority_state"])
        self.assertFalse(result["side_effects_performed"])

    def test_head_change_invalidates_prior_approval(self) -> None:
        value = make_input(head="a" * 40)
        value["expected_head_sha"] = "b" * 40
        result = runner.run(value)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("APPROVAL_BINDING_MISMATCH", result["reason_code"])
        self.assertIsNone(result["binding"])


if __name__ == "__main__":
    unittest.main()
