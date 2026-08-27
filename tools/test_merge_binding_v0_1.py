#!/usr/bin/env python3
"""Exact merge-binding drift controls."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import github_merge_binding_v0_1 as subject


def value() -> dict:
    binding = subject.make_binding("safal207/LS", 813, "b" * 40, "a" * 40, "e" * 64)
    return {
        "repository": "safal207/LS",
        "pull_request_number": 813,
        "expected_base_sha": "b" * 40,
        "expected_head_sha": "a" * 40,
        "expected_evidence_sha256": "e" * 64,
        "gateway_mode": subject.GATEWAY_MODE,
        "approval": {
            "approval_id": subject.approval_id(binding),
            "signal": "USER_APPROVED",
            "actor": {"type": "USER", "id": "operator-1"},
            "reason": "exact approval",
            "evidence_ref": subject.evidence_ref("e" * 64),
            "exact_bindings_match": True,
            "expiry_policy_configured": False,
        },
    }


class BindingTests(unittest.TestCase):
    def test_valid_binding(self) -> None:
        self.assertEqual(64, len(subject.validate(value())["binding_digest"]))

    def test_base_head_and_evidence_drift_block(self) -> None:
        for field, changed in (
            ("expected_base_sha", "c" * 40),
            ("expected_head_sha", "d" * 40),
            ("expected_evidence_sha256", "f" * 64),
        ):
            candidate = value()
            candidate[field] = changed
            with self.assertRaises(subject.BindingError):
                subject.validate(candidate)

    def test_evidence_reference_mismatch_blocks(self) -> None:
        candidate = value()
        candidate["approval"]["evidence_ref"] = subject.evidence_ref("0" * 64)
        with self.assertRaises(subject.BindingError) as raised:
            subject.validate(candidate)
        self.assertEqual("EVIDENCE_BINDING_MISMATCH", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
