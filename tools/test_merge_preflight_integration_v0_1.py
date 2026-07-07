#!/usr/bin/env python3
"""Integration of exact merge binding with the local ReviewDecision Gateway."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import github_merge_binding_v0_1 as binding
import merge_preflight_adapter_v0_1 as adapter
import review_decision_gateway_v0_1 as gateway


def value(signal: str = "USER_APPROVED") -> dict:
    exact = binding.make_binding("safal207/LS", 813, "b" * 40, "a" * 40, "e" * 64)
    actor_type = "USER" if signal.startswith("USER_") else "AGENT"
    return {
        "repository": "safal207/LS",
        "pull_request_number": 813,
        "expected_base_sha": "b" * 40,
        "expected_head_sha": "a" * 40,
        "expected_evidence_sha256": "e" * 64,
        "gateway_mode": binding.GATEWAY_MODE,
        "approval": {
            "approval_id": binding.approval_id(exact),
            "signal": signal,
            "actor": {"type": actor_type, "id": "operator-1"},
            "reason": "exact approval",
            "evidence_ref": binding.evidence_ref("e" * 64),
            "exact_bindings_match": True,
            "expiry_policy_configured": False,
        },
    }


class FailingService:
    def project(self, _approval: dict, _request_id: str) -> tuple[int, dict]:
        raise RuntimeError("sensitive internal detail")


class MalformedService:
    def project(self, _approval: dict, _request_id: str) -> object:
        return object()


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = gateway.ReviewDecisionGateway()

    def test_explicit_approval_allows_only_claim_handoff(self) -> None:
        result = adapter.evaluate(value(), self.service)
        self.assertEqual("ALLOW_CLAIM", result["decision"])
        self.assertTrue(result["handoff"]["commit_before_effect_eligible"])
        self.assertFalse(result["handoff"]["live_evidence_verified"])
        self.assertFalse(result["handoff"]["authorization_bundle_verified"])
        self.assertFalse(result["handoff"]["execution_authorized"])
        self.assertFalse(result["merge_performed"])

    def test_requester_cancellation_preserves_pending_authority(self) -> None:
        result = adapter.evaluate(value("REQUESTER_CANCELLED"), self.service)
        self.assertEqual("BLOCK", result["decision"])
        self.assertEqual("PENDING", result["gateway_projection"]["authority_state"])

    def test_user_rejection_and_agent_approval_block(self) -> None:
        self.assertEqual("BLOCK", adapter.evaluate(value("USER_REJECTED"), self.service)["decision"])
        candidate = value()
        candidate["approval"]["actor"] = {"type": "AGENT", "id": "agent-root"}
        self.assertEqual("ADAPTER_REJECTED", adapter.evaluate(candidate, self.service)["reason_code"])

    def test_service_exceptions_and_bad_return_shapes_block(self) -> None:
        for service in (FailingService(), MalformedService()):
            with self.subTest(service=type(service).__name__):
                result = adapter.evaluate(value(), service)
                self.assertEqual("BLOCK", result["decision"])
                self.assertEqual("GATEWAY_INTERNAL_FAILURE", result["reason_code"])
                self.assertNotIn("sensitive internal detail", result["detail"])
                self.assertFalse(result["side_effects_performed"])


if __name__ == "__main__":
    unittest.main()
