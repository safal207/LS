#!/usr/bin/env python3
"""HTTP and concurrency tests for ReviewDecision Gateway v0.1."""

from __future__ import annotations

import http.client
import importlib.util
import json
import sys
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_PATH = ROOT / "tools" / "review_decision_gateway_v0_1.py"

_spec = importlib.util.spec_from_file_location("review_decision_gateway_v0_1", GATEWAY_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import gateway from {GATEWAY_PATH}")
gateway_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = gateway_module
_spec.loader.exec_module(gateway_module)


@contextmanager
def live_gateway() -> Iterator[tuple[str, int, object]]:
    service = gateway_module.ReviewDecisionGateway()
    server = gateway_module.create_server("127.0.0.1", 0, service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "127.0.0.1", server.server_port, service
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def requester_cancelled_payload() -> dict:
    return {
        "approval_id": "approval-gateway-test-001",
        "signal": "REQUESTER_CANCELLED",
        "actor": {"type": "AGENT", "id": "agent-root"},
        "reason": "requesting future cancelled",
        "evidence_ref": None,
        "exact_bindings_match": True,
        "expiry_policy_configured": False,
    }


def approved_payload() -> dict:
    return {
        "approval_id": "approval-gateway-test-002",
        "signal": "USER_APPROVED",
        "actor": {"type": "USER", "id": "local-operator"},
        "reason": "user explicitly approved exact action",
        "evidence_ref": None,
        "exact_bindings_match": True,
        "expiry_policy_configured": False,
    }


def request(
    host: str,
    port: int,
    method: str,
    path: str,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    connection = http.client.HTTPConnection(host, port, timeout=3)
    try:
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


class ReviewDecisionGatewayTests(unittest.TestCase):
    def test_requester_cancellation_preserves_authority(self) -> None:
        with live_gateway() as (host, port, _service):
            body = json.dumps(requester_cancelled_payload()).encode()
            status, headers, raw = request(
                host,
                port,
                "POST",
                gateway_module.PROJECT_PATH,
                body,
                {"Content-Type": "application/json", "X-Request-ID": "cancel-test-001"},
            )
        response = json.loads(raw)
        projection = response["projection"]
        self.assertEqual(200, status)
        self.assertEqual("application/json; charset=utf-8", headers["Content-Type"])
        self.assertEqual("cancel-test-001", response["request_id"])
        self.assertEqual("PENDING", projection["authority_state"])
        self.assertEqual("CANCELLED", projection["requester_state"])
        self.assertEqual("UNUSED", projection["execution_state"])
        self.assertTrue(projection["execution_blocked"])
        self.assertFalse(response["side_effects_performed"])

    def test_explicit_approval_performs_no_side_effect(self) -> None:
        with live_gateway() as (host, port, _service):
            body = json.dumps(approved_payload()).encode()
            status, _headers, raw = request(
                host,
                port,
                "POST",
                gateway_module.PROJECT_PATH,
                body,
                {"Content-Type": "application/json"},
            )
        response = json.loads(raw)
        self.assertEqual(200, status)
        self.assertEqual("APPROVED", response["projection"]["authority_state"])
        self.assertTrue(response["projection"]["execution_claim_allowed"])
        self.assertFalse(response["side_effects_performed"])

    def test_unsupported_signal_fails_closed(self) -> None:
        payload = requester_cancelled_payload()
        payload["signal"] = "DENIED"
        with live_gateway() as (host, port, _service):
            status, _headers, raw = request(
                host,
                port,
                "POST",
                gateway_module.PROJECT_PATH,
                json.dumps(payload).encode(),
                {"Content-Type": "application/json"},
            )
        response = json.loads(raw)
        self.assertEqual(422, status)
        self.assertFalse(response["adapter"]["valid"])
        self.assertEqual("ADAPTER_ERROR", response["projection"]["outward_status"])
        self.assertEqual("PENDING", response["projection"]["authority_state"])
        self.assertEqual("UNUSED", response["projection"]["execution_state"])
        self.assertTrue(response["projection"]["execution_blocked"])

    def test_malformed_json_fails_closed(self) -> None:
        with live_gateway() as (host, port, _service):
            status, _headers, raw = request(
                host,
                port,
                "POST",
                gateway_module.PROJECT_PATH,
                b"{not-json",
                {"Content-Type": "application/json"},
            )
        response = json.loads(raw)
        self.assertEqual(400, status)
        self.assertEqual("PENDING", response["projection"]["authority_state"])
        self.assertEqual("UNUSED", response["projection"]["execution_state"])
        self.assertFalse(response["side_effects_performed"])

    def test_wrong_content_type_is_rejected(self) -> None:
        with live_gateway() as (host, port, _service):
            status, _headers, raw = request(
                host,
                port,
                "POST",
                gateway_module.PROJECT_PATH,
                b"{}",
                {"Content-Type": "text/plain"},
            )
        response = json.loads(raw)
        self.assertEqual(415, status)
        self.assertTrue(response["projection"]["execution_blocked"])

    def test_oversized_body_is_rejected_before_read(self) -> None:
        with live_gateway() as (host, port, _service):
            connection = http.client.HTTPConnection(host, port, timeout=3)
            try:
                connection.putrequest("POST", gateway_module.PROJECT_PATH)
                connection.putheader("Content-Type", "application/json")
                connection.putheader("Content-Length", str(gateway_module.MAX_BODY_BYTES + 1))
                connection.endheaders()
                response = connection.getresponse()
                raw = response.read()
                status = response.status
            finally:
                connection.close()
        parsed = json.loads(raw)
        self.assertEqual(413, status)
        self.assertTrue(parsed["projection"]["execution_blocked"])

    def test_health_and_unknown_route(self) -> None:
        with live_gateway() as (host, port, _service):
            health_status, _headers, health_raw = request(host, port, "GET", "/healthz")
            missing_status, _headers, missing_raw = request(host, port, "GET", "/missing")
        self.assertEqual(200, health_status)
        self.assertEqual("ok", json.loads(health_raw)["status"])
        self.assertEqual(404, missing_status)
        self.assertEqual("not found", json.loads(missing_raw)["error"])

    def test_metrics_are_exposed_and_invention_stays_zero(self) -> None:
        with live_gateway() as (host, port, _service):
            valid_body = json.dumps(requester_cancelled_payload()).encode()
            request(host, port, "POST", gateway_module.PROJECT_PATH, valid_body, {"Content-Type": "application/json"})
            invalid = requester_cancelled_payload()
            invalid["signal"] = "DENIED"
            request(host, port, "POST", gateway_module.PROJECT_PATH, json.dumps(invalid).encode(), {"Content-Type": "application/json"})
            status, _headers, raw = request(host, port, "GET", "/metrics")
        text = raw.decode()
        self.assertEqual(200, status)
        self.assertIn("review_decision_requests_total 2", text)
        self.assertIn("blocked_ambiguous_signals_total 1", text)
        self.assertIn("invented_user_decisions_total 0", text)

    def test_projection_is_deterministic_for_same_request_id(self) -> None:
        service = gateway_module.ReviewDecisionGateway()
        first = service.project(requester_cancelled_payload(), "stable-id")[1]
        second = service.project(requester_cancelled_payload(), "stable-id")[1]
        self.assertEqual(first, second)

    def test_metrics_updates_are_thread_safe(self) -> None:
        service = gateway_module.ReviewDecisionGateway()
        threads = [
            threading.Thread(
                target=service.project,
                args=(requester_cancelled_payload(), f"request-{index}"),
            )
            for index in range(100)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)
        values = service.metrics.snapshot()
        self.assertEqual(100, values["review_decision_requests_total"])
        self.assertEqual(0, values["blocked_ambiguous_signals_total"])
        self.assertEqual(0, values["invented_user_decisions_total"])

    def test_request_id_falls_back_to_body_digest(self) -> None:
        body = b'{"signal":"REQUESTER_CANCELLED"}'
        first = gateway_module.ReviewDecisionGateway.request_id(body)
        second = gateway_module.ReviewDecisionGateway.request_id(body, "")
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("req-"))


if __name__ == "__main__":
    unittest.main()
