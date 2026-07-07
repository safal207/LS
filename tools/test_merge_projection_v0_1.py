#!/usr/bin/env python3
"""Fail-closed merge projection controls."""

from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_merge_projection_v0_1 as subject


def approval() -> dict:
    return {
        "signal": "USER_APPROVED",
        "actor": {"type": "USER", "id": "operator-1"},
        "reason": "exact approval",
        "evidence_ref": "exact-head-evidence:" + "e" * 64,
    }


def response() -> dict:
    return {
        "gateway_version": subject.GATEWAY_VERSION,
        "request_id": "request-1",
        "adapter": {"valid": True, "errors": []},
        "projection": {
            "durable_event_type": "UserApproved",
            "authority_state": "APPROVED",
            "execution_state": "UNUSED",
            "execution_blocked": False,
            "execution_claim_allowed": True,
            "resolution": {
                "event_type": "UserApproved",
                "actor_type": "USER",
                "actor_id": "operator-1",
                "reason": "exact approval",
                "evidence_ref": "exact-head-evidence:" + "e" * 64,
            },
        },
        "side_effects_performed": False,
    }


class ProjectionTests(unittest.TestCase):
    def test_approved_projection_allows_claim_handoff(self) -> None:
        validated = subject.validate_response(response(), "request-1")
        self.assertEqual(
            ("ALLOW_CLAIM", "EXACT_EVIDENCE_BOUND_APPROVAL_PROJECTED"),
            subject.classify(validated, approval()),
        )

    def test_resolution_mismatch_blocks(self) -> None:
        changed = deepcopy(response())
        changed["projection"]["resolution"]["actor_id"] = "other-user"
        self.assertEqual("APPROVAL_RESOLUTION_MISMATCH", subject.classify(changed, approval())[1])

    def test_replay_and_side_effects_block(self) -> None:
        changed = deepcopy(response())
        changed["projection"]["execution_state"] = "CLAIMED"
        self.assertEqual("EXECUTION_ALREADY_CLAIMED", subject.classify(changed, approval())[1])
        changed = deepcopy(response())
        changed["side_effects_performed"] = True
        with self.assertRaises(subject.ProjectionError):
            subject.validate_response(changed, "request-1")


if __name__ == "__main__":
    unittest.main()
