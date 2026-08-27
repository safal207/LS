#!/usr/bin/env python3
"""30-second product demo for LS Approval Integrity.

The demo turns the durable-approval conformance fixture into a user-facing
before/after story while keeping the proof executable and dependency-free.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_durable_approval_v0_1 import load_object, validate

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/trusted-runtime/durable-approval/pending_approval_not_missing_authority_v0.1.json"
ENVELOPE_SCHEMA = ROOT / "fixtures/trusted-runtime/durable-approval/envelope.schema.json"
EVENT_SCHEMA = ROOT / "fixtures/trusted-runtime/durable-approval/event.schema.json"


class DemoFailure(RuntimeError):
    """Raised when the product promise is no longer supported by conformance evidence."""


def case_by_id(fixture: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in fixture.get("cases", []):
        if isinstance(case, dict) and case.get("case_id") == case_id:
            return case
    raise DemoFailure(f"missing conformance case: {case_id}")


def assert_demo_contract(
    fixture: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    if not validation.get("passed"):
        raise DemoFailure("durable approval conformance failed: " + "; ".join(validation.get("errors", [])))

    cancellation_case = case_by_id(fixture, "agent_cancels_requester")
    cancellation = validation["observed_snapshots"]["agent_cancels_requester"]
    transport = validation["observed_snapshots"]["transport_disconnects"]

    cancellation_events = cancellation_case.get("events", [])
    user_rejection_recorded = any(
        isinstance(event, dict) and event.get("event_type") == "UserRejected"
        for event in cancellation_events
    )

    expected_cancellation = {
        "authority_state": "PENDING",
        "requester_state": "CANCELLED",
        "presentation_state": "VISIBLE",
        "execution_state": "UNUSED",
        "resolution": None,
    }
    if cancellation != expected_cancellation:
        raise DemoFailure(
            "requester cancellation no longer preserves pending authority: "
            + json.dumps(cancellation, sort_keys=True)
        )
    if user_rejection_recorded:
        raise DemoFailure("requester cancellation manufactured UserRejected")
    if transport.get("authority_state") != "PENDING" or transport.get("execution_state") != "UNUSED":
        raise DemoFailure("transport loss resolved authority or enabled execution")

    return {
        "product": "LS Approval Integrity",
        "scenario": "The user is still reviewing an action when the requester stops waiting.",
        "unsafe_failure_class": {
            "message": "Approval not granted",
            "problem": "The system collapses requester termination into a user authority outcome.",
        },
        "protected_result": {
            "user_message": "Your decision is still pending. The agent stopped waiting. Nothing was executed.",
            "authority_state": cancellation["authority_state"],
            "requester_state": cancellation["requester_state"],
            "presentation_state": cancellation["presentation_state"],
            "execution_state": cancellation["execution_state"],
        },
        "guarantees_proven": [
            "No UserRejected event was recorded.",
            "Requester cancellation did not resolve user-owned authority.",
            "Transport loss did not resolve user-owned authority.",
            "No execution claim was created.",
        ],
    }


def render_text(demo: dict[str, Any]) -> str:
    protected = demo["protected_result"]
    guarantees = "\n".join(f"  [PASS] {item}" for item in demo["guarantees_proven"])
    return f"""LS Approval Integrity — 30-second demo

SCENARIO
  {demo['scenario']}

WITHOUT AN INTEGRITY CONTRACT
  Message: {demo['unsafe_failure_class']['message']}
  Risk:    {demo['unsafe_failure_class']['problem']}

WITH LS APPROVAL INTEGRITY
  Message: {protected['user_message']}
  Authority:    {protected['authority_state']}
  Requester:    {protected['requester_state']}
  Presentation: {protected['presentation_state']}
  Execution:    {protected['execution_state']}

EXECUTABLE PROOF
{guarantees}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print the demo payload as JSON")
    parser.add_argument("--check", action="store_true", help="validate the product promise without extra output")
    args = parser.parse_args()

    fixture = load_object(FIXTURE)
    validation = validate(
        fixture,
        load_object(ENVELOPE_SCHEMA),
        load_object(EVENT_SCHEMA),
    )

    try:
        demo = assert_demo_contract(fixture, validation)
    except DemoFailure as exc:
        print(f"FAIL: {exc}")
        return 1

    if args.check:
        print("PASS: LS Approval Integrity product demo contract")
    elif args.json:
        print(json.dumps(demo, indent=2, sort_keys=True))
    else:
        print(render_text(demo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
