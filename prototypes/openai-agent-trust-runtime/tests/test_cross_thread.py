from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from ls_agent_trust.cross_thread import (
    Authority,
    CapabilityGrant,
    CrossThreadEvent,
    CrossThreadRuntime,
    CrossThreadViolation,
    DispositionStatus,
    EventType,
    EvidenceRef,
    InMemoryEvidenceStore,
    VerificationStatus,
)


def runtime_pair(
    *,
    allowed=(EventType.RESULT, EventType.STATE_UPDATE, EventType.ACTION_REQUEST),
    max_authority=Authority(may_inform=True, may_request_action=True),
    allow_read=True,
):
    runtime = CrossThreadRuntime()
    runtime.register_thread(thread_id="thread-a", agent_id="Agent A", role="executor")
    runtime.register_thread(thread_id="thread-b", agent_id="Agent B", role="stabilizer")
    grant = CapabilityGrant.build(
        source_thread_id="thread-a",
        target_thread_id="thread-b",
        allowed_event_types=allowed,
        max_authority=max_authority,
        allow_read=allow_read,
    )
    runtime.grant_capability(grant)
    return runtime, grant


def verified_event(
    evidence: EvidenceRef,
    *,
    sequence: int = 1,
    event_id: str | None = None,
    event_type: EventType = EventType.RESULT,
    authority: Authority = Authority(),
    supersedes_event_id: str | None = None,
):
    return CrossThreadEvent.build(
        trajectory_id="project:demo",
        continuation_id=f"run-{sequence}",
        source_thread_id="thread-a",
        source_agent_id="Agent A",
        source_role="executor",
        target_thread_id="thread-b",
        event_type=event_type,
        subject="deployment.endpoint",
        payload={"value": f"https://example.test/{sequence}"},
        evidence_refs=(evidence,),
        verification_status=VerificationStatus.VERIFIED,
        authority=authority,
        sequence=sequence,
        event_id=event_id,
        supersedes_event_id=supersedes_event_id,
    )


def test_verified_state_is_accepted_after_evidence_check() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")

    decision = runtime.receive(verified_event(evidence), evidence_checker=store.verify)

    assert decision.status == DispositionStatus.ACCEPTED
    assert decision.reason == "verified state accepted"
    state = runtime.accepted_state(
        trajectory_id="project:demo", subject="deployment.endpoint"
    )
    assert state is not None
    assert state.sequence == 1
    assert runtime.verify_audit() is True


def test_verified_claim_without_checker_is_deferred() -> None:
    runtime, _grant = runtime_pair()
    evidence = EvidenceRef(ref="artifact:health", sha256="0" * 64)

    decision = runtime.receive(verified_event(evidence))

    assert decision.status == DispositionStatus.DEFERRED
    assert "no evidence checker" in decision.reason


def test_forged_evidence_is_rejected() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    store.put("artifact:health", "real")
    forged = EvidenceRef(ref="artifact:health", sha256="f" * 64)

    decision = runtime.receive(verified_event(forged), evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert decision.evidence_verdicts[0].verified is False
    assert decision.evidence_verdicts[0].reason == "evidence digest mismatch"


def test_replayed_event_id_is_idempotent() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")
    event = verified_event(evidence, event_id="evt-fixed")

    first = runtime.receive(event, evidence_checker=store.verify)
    second = runtime.receive(event, evidence_checker=store.verify)

    assert first == second
    assert len(runtime.decisions) == 1


def test_stale_event_cannot_overwrite_newer_state() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    first_evidence = store.put("artifact:first", "v2")
    first = verified_event(first_evidence, sequence=2)
    assert runtime.receive(first, evidence_checker=store.verify).status == DispositionStatus.ACCEPTED

    stale_evidence = store.put("artifact:stale", "v1")
    stale = verified_event(stale_evidence, sequence=1)
    decision = runtime.receive(stale, evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert "stale event" in decision.reason


def test_supersedes_must_match_current_state() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    ev1 = verified_event(store.put("artifact:one", "one"), sequence=1)
    runtime.receive(ev1, evidence_checker=store.verify)
    ev2 = verified_event(
        store.put("artifact:two", "two"),
        sequence=2,
        supersedes_event_id="wrong-event",
    )

    decision = runtime.receive(ev2, evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert "supersedes_event_id" in decision.reason


def test_event_type_outside_capability_is_rejected() -> None:
    runtime, _grant = runtime_pair(allowed=(EventType.RESULT,))
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")
    event = verified_event(evidence, event_type=EventType.STATE_UPDATE)

    decision = runtime.receive(event, evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert "event type" in decision.reason


def test_authority_escalation_is_rejected() -> None:
    runtime, _grant = runtime_pair(
        max_authority=Authority(may_inform=True, may_request_action=False)
    )
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:request", "request")
    event = verified_event(
        evidence,
        event_type=EventType.ACTION_REQUEST,
        authority=Authority(may_inform=True, may_request_action=True),
    )

    decision = runtime.receive(event, evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert "authority exceeds" in decision.reason


def test_action_request_is_advisory_not_execution() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:request", "request")
    event = verified_event(
        evidence,
        event_type=EventType.ACTION_REQUEST,
        authority=Authority(may_inform=True, may_request_action=True),
    )

    decision = runtime.receive(event, evidence_checker=store.verify)

    assert decision.status == DispositionStatus.ACCEPTED
    assert "no execution occurred" in decision.reason


def test_archived_sender_cannot_send() -> None:
    runtime, _grant = runtime_pair()
    runtime.archive_thread("thread-a")
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")

    decision = runtime.receive(verified_event(evidence), evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert "archived" in decision.reason


def test_revoked_capability_cannot_be_used() -> None:
    runtime, grant = runtime_pair()
    runtime.revoke_capability(grant.capability_id)
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")

    decision = runtime.receive(verified_event(evidence), evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert "no active capability" in decision.reason


def test_expired_capability_is_rejected() -> None:
    runtime = CrossThreadRuntime()
    runtime.register_thread(thread_id="thread-a", agent_id="Agent A", role="executor")
    runtime.register_thread(thread_id="thread-b", agent_id="Agent B", role="stabilizer")
    expires = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    runtime.grant_capability(
        CapabilityGrant.build(
            source_thread_id="thread-a",
            target_thread_id="thread-b",
            allowed_event_types=(EventType.RESULT,),
            expires_at=expires,
        )
    )
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")

    decision = runtime.receive(verified_event(evidence), evidence_checker=store.verify)

    assert decision.status == DispositionStatus.REJECTED
    assert "expired" in decision.reason


def test_thread_audit_read_requires_capability() -> None:
    runtime, _grant = runtime_pair(allow_read=False)

    with pytest.raises(CrossThreadViolation, match="lacks read capability"):
        runtime.read_thread_audit(
            requester_thread_id="thread-a", target_thread_id="thread-b"
        )


def test_thread_audit_read_is_visible_to_both_sides_when_granted() -> None:
    runtime, _grant = runtime_pair(allow_read=True)
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")
    runtime.receive(verified_event(evidence), evidence_checker=store.verify)

    records = runtime.read_thread_audit(
        requester_thread_id="thread-a", target_thread_id="thread-b"
    )

    assert records
    assert any(
        record["event_type"] == "CROSS_THREAD_EVENT_DISPOSITION"
        for record in records
    )


def test_audit_chain_detects_tampering() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")
    runtime.receive(verified_event(evidence), evidence_checker=store.verify)
    assert runtime.verify_audit() is True

    tampered = copy.deepcopy(list(runtime.audit_records))
    tampered[-1]["payload"]["decision"]["reason"] = "silently changed"
    assert CrossThreadRuntime.verify_records(tampered) is False


def test_resumed_thread_preserves_state_and_audit_history() -> None:
    runtime, _grant = runtime_pair()
    store = InMemoryEvidenceStore()
    evidence = store.put("artifact:health", "ok")
    event = verified_event(evidence)
    runtime.receive(event, evidence_checker=store.verify)
    before_count = len(runtime.audit_records)

    runtime.archive_thread("thread-b")
    runtime.resume_thread("thread-b")

    state = runtime.accepted_state(
        trajectory_id="project:demo", subject="deployment.endpoint"
    )
    assert state is not None
    assert state.event_id == event.event_id
    assert len(runtime.audit_records) == before_count + 2
    assert runtime.verify_audit() is True
