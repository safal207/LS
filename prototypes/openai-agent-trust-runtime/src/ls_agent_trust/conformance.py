"""Deterministic CrossThreadEvent v0.1 conformance runner."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Callable, Sequence

from .cross_thread import (
    Authority,
    CapabilityGrant,
    CrossThreadEvent,
    CrossThreadRuntime,
    CrossThreadViolation,
    DispositionStatus,
    EventType,
    InMemoryEvidenceStore,
    VerificationStatus,
)


@dataclass(frozen=True)
class ConformanceCase:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ConformanceReport:
    protocol: str
    passed: int
    failed: int
    cases: tuple[ConformanceCase, ...]

    @property
    def ok(self) -> bool:
        return self.failed == 0

    def to_dict(self) -> dict[str, object]:
        return {
            "protocol": self.protocol,
            "ok": self.ok,
            "passed": self.passed,
            "failed": self.failed,
            "cases": [asdict(case) for case in self.cases],
        }


def _setup(*, allow_read: bool = True) -> tuple[CrossThreadRuntime, InMemoryEvidenceStore, CapabilityGrant]:
    runtime = CrossThreadRuntime()
    runtime.register_thread(thread_id="thread-a", agent_id="Agent A", role="executor")
    runtime.register_thread(thread_id="thread-b", agent_id="Agent B", role="stabilizer")
    grant = CapabilityGrant.build(
        source_thread_id="thread-a",
        target_thread_id="thread-b",
        allowed_event_types=(EventType.RESULT, EventType.STATE_UPDATE, EventType.ACTION_REQUEST),
        max_authority=Authority(may_inform=True, may_request_action=True),
        allow_read=allow_read,
    )
    runtime.grant_capability(grant)
    return runtime, InMemoryEvidenceStore(), grant


def _event(
    evidence,
    *,
    sequence: int = 1,
    event_id: str | None = None,
    event_type: EventType = EventType.RESULT,
    verification_status: VerificationStatus = VerificationStatus.VERIFIED,
    authority: Authority = Authority(),
):
    return CrossThreadEvent.build(
        trajectory_id="project:conformance",
        continuation_id=f"case-{sequence}",
        source_thread_id="thread-a",
        source_agent_id="Agent A",
        source_role="executor",
        target_thread_id="thread-b",
        event_type=event_type,
        subject="system.state",
        payload={"version": sequence},
        evidence_refs=(evidence,) if evidence else (),
        verification_status=verification_status,
        authority=authority,
        sequence=sequence,
        event_id=event_id,
    )


def _case(name: str, fn: Callable[[], str]) -> ConformanceCase:
    try:
        detail = fn()
    except Exception as exc:  # pragma: no cover - report path
        return ConformanceCase(name=name, passed=False, detail=f"{type(exc).__name__}: {exc}")
    return ConformanceCase(name=name, passed=True, detail=detail)


def run_conformance() -> ConformanceReport:
    cases: list[ConformanceCase] = []

    def permission_gated() -> str:
        runtime = CrossThreadRuntime()
        runtime.register_thread(thread_id="thread-a", agent_id="Agent A", role="executor")
        runtime.register_thread(thread_id="thread-b", agent_id="Agent B", role="stabilizer")
        store = InMemoryEvidenceStore()
        evidence = store.put("artifact:x", "x")
        decision = runtime.receive(_event(evidence), evidence_checker=store.verify)
        assert decision.status == DispositionStatus.REJECTED
        return decision.reason

    cases.append(_case("orchestration permission-gated by default", permission_gated))

    def read_denied() -> str:
        runtime, _store, _grant = _setup(allow_read=False)
        try:
            runtime.read_thread_audit(requester_thread_id="thread-a", target_thread_id="thread-b")
        except CrossThreadViolation as exc:
            return str(exc)
        raise AssertionError("audit read unexpectedly succeeded")

    cases.append(_case("cross-thread read requires explicit capability", read_denied))

    def audit_both_sides() -> str:
        runtime, store, _grant = _setup()
        evidence = store.put("artifact:x", "x")
        event = _event(evidence)
        runtime.receive(event, evidence_checker=store.verify)
        target_records = runtime.read_thread_audit(
            requester_thread_id="thread-a", target_thread_id="thread-b"
        )
        source_records = runtime.read_thread_audit(
            requester_thread_id="thread-a", target_thread_id="thread-a"
        )
        assert any(event.event_id in json.dumps(record) for record in target_records)
        assert any(event.event_id in json.dumps(record) for record in source_records)
        return "event visible in source and target audit views"

    cases.append(_case("event recorded for both source and target", audit_both_sides))

    def unverified_state_deferred() -> str:
        runtime, _store, _grant = _setup()
        event = _event(
            None,
            event_type=EventType.STATE_UPDATE,
            verification_status=VerificationStatus.UNVERIFIED,
        )
        decision = runtime.receive(event)
        assert decision.status == DispositionStatus.DEFERRED
        return decision.reason

    cases.append(_case("unverified state cannot release dependent work", unverified_state_deferred))

    def stale_rejected() -> str:
        runtime, store, _grant = _setup()
        newer = _event(store.put("artifact:new", "new"), sequence=2)
        runtime.receive(newer, evidence_checker=store.verify)
        stale = _event(store.put("artifact:old", "old"), sequence=1)
        decision = runtime.receive(stale, evidence_checker=store.verify)
        assert decision.status == DispositionStatus.REJECTED
        return decision.reason

    cases.append(_case("stale event cannot overwrite newer state", stale_rejected))

    def replay_idempotent() -> str:
        runtime, store, _grant = _setup()
        event = _event(store.put("artifact:x", "x"), event_id="evt-stable")
        first = runtime.receive(event, evidence_checker=store.verify)
        second = runtime.receive(event, evidence_checker=store.verify)
        assert first == second and len(runtime.decisions) == 1
        return "same event_id returned the original decision receipt"

    cases.append(_case("duplicate delivery is idempotent", replay_idempotent))

    def request_not_authority() -> str:
        runtime, store, _grant = _setup()
        event = _event(
            store.put("artifact:request", "request"),
            event_type=EventType.ACTION_REQUEST,
            authority=Authority(may_inform=True, may_request_action=True),
        )
        decision = runtime.receive(event, evidence_checker=store.verify)
        assert decision.status == DispositionStatus.ACCEPTED
        assert "no execution occurred" in decision.reason
        return decision.reason

    cases.append(_case("action request is not execution authority", request_not_authority))

    def archived_blocked() -> str:
        runtime, store, _grant = _setup()
        runtime.archive_thread("thread-a")
        event = _event(store.put("artifact:x", "x"))
        decision = runtime.receive(event, evidence_checker=store.verify)
        assert decision.status == DispositionStatus.REJECTED
        return decision.reason

    cases.append(_case("archived thread cannot send accepted events", archived_blocked))

    def revoked_blocked() -> str:
        runtime, store, grant = _setup()
        runtime.revoke_capability(grant.capability_id)
        event = _event(store.put("artifact:x", "x"))
        decision = runtime.receive(event, evidence_checker=store.verify)
        assert decision.status == DispositionStatus.REJECTED
        return decision.reason

    cases.append(_case("revoked capability blocks further events", revoked_blocked))

    def resume_preserves_history() -> str:
        runtime, store, _grant = _setup()
        event = _event(store.put("artifact:x", "x"))
        runtime.receive(event, evidence_checker=store.verify)
        runtime.archive_thread("thread-b")
        runtime.resume_thread("thread-b")
        state = runtime.accepted_state(trajectory_id="project:conformance", subject="system.state")
        assert state is not None and state.event_id == event.event_id
        assert runtime.verify_audit()
        return "trajectory state and audit history survived explicit resume"

    cases.append(_case("resumed thread preserves trajectory and audit history", resume_preserves_history))

    passed = sum(case.passed for case in cases)
    return ConformanceReport(
        protocol="cross-thread-event/v0.1",
        passed=passed,
        failed=len(cases) - passed,
        cases=tuple(cases),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compact", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    report = run_conformance()
    print(
        json.dumps(
            report.to_dict(),
            indent=None if args.compact else 2,
            sort_keys=True,
        )
    )
    if not report.ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
