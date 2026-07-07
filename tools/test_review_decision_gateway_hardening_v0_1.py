#!/usr/bin/env python3
"""Focused hardening controls for ReviewDecision Gateway v0.1."""

from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_PATH = ROOT / "tools" / "review_decision_gateway_v0_1.py"

_spec = importlib.util.spec_from_file_location("review_decision_gateway_hardening", GATEWAY_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import gateway from {GATEWAY_PATH}")
gateway = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gateway
_spec.loader.exec_module(gateway)


class OneByteStream:
    def read1(self, _size: int) -> bytes:
        return b"x"


class ReviewDecisionGatewayHardeningTests(unittest.TestCase):
    def test_read_exact_accepts_complete_body(self) -> None:
        self.assertEqual(b"abcdef", gateway.read_exact(io.BytesIO(b"abcdef"), 6))

    def test_read_exact_rejects_truncated_body(self) -> None:
        self.assertIsNone(gateway.read_exact(io.BytesIO(b"abc"), 6))

    def test_read_exact_enforces_aggregate_deadline(self) -> None:
        applied_timeouts: list[float] = []
        with patch.object(gateway.time, "monotonic", side_effect=[0.0, 1.0, 6.0]):
            with self.assertRaises(TimeoutError):
                gateway.read_exact(
                    OneByteStream(),
                    3,
                    deadline=5.0,
                    set_timeout=applied_timeouts.append,
                )
        self.assertEqual([5.0, 4.0], applied_timeouts)

    def test_transport_rejection_does_not_pollute_ambiguous_signal_metric(self) -> None:
        metrics = gateway.GatewayMetrics()
        metrics.record(transport_rejection=True)
        values = metrics.snapshot()
        self.assertEqual(1, values["review_decision_requests_total"])
        self.assertEqual(1, values["transport_rejections_total"])
        self.assertEqual(0, values["blocked_ambiguous_signals_total"])
        self.assertEqual(0, values["invented_user_decisions_total"])

    def test_adapter_rejection_increments_only_ambiguous_signal_metric(self) -> None:
        metrics = gateway.GatewayMetrics()
        metrics.record(blocked_ambiguous=True)
        values = metrics.snapshot()
        self.assertEqual(1, values["review_decision_requests_total"])
        self.assertEqual(0, values["transport_rejections_total"])
        self.assertEqual(1, values["blocked_ambiguous_signals_total"])
        self.assertEqual(0, values["invented_user_decisions_total"])

    def test_invented_decision_fails_closed_while_sentinel_remains_zero(self) -> None:
        service = gateway.ReviewDecisionGateway()
        fabricated = {
            "valid": True,
            "errors": [],
            "projection": {
                "durable_event_type": "UserRejected",
                "authority_state": "REJECTED",
                "requester_state": "CANCELLED",
                "presentation_state": "VISIBLE",
                "execution_state": "UNUSED",
                "outward_status": "REJECTED_BY_USER",
                "user_message": "fabricated",
                "execution_blocked": True,
                "execution_claim_allowed": False,
                "resolution": None,
            },
        }
        payload = {
            "approval_id": "approval-hardening-001",
            "signal": "REQUESTER_CANCELLED",
        }
        with patch.object(gateway.adapter, "project_signal", return_value=fabricated):
            status, response = service.project(payload, "hardening-001")
        self.assertEqual(422, status)
        self.assertFalse(response["adapter"]["valid"])
        self.assertEqual("ADAPTER_ERROR", response["projection"]["outward_status"])
        values = service.metrics.snapshot()
        self.assertEqual(1, values["blocked_ambiguous_signals_total"])
        self.assertEqual(0, values["invented_user_decisions_total"])

    def test_read_timeout_is_positive_and_bounded(self) -> None:
        self.assertGreater(gateway.READ_TIMEOUT_SECONDS, 0)
        self.assertLessEqual(gateway.READ_TIMEOUT_SECONDS, 30)


if __name__ == "__main__":
    unittest.main()
