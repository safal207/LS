from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from .contracts import ReplayDecision, TrailEventType
from .persistence import DurableEvent, StoreFinding
from .replay_models import ReplayFinding


def inspect_path(events: Sequence[DurableEvent]) -> list[ReplayFinding]:
    findings: list[ReplayFinding] = []
    if events[0].event_type != TrailEventType.TASK_RECEIVED.value:
        findings.append(
            ReplayFinding(
                "INVALID_TRACE_ROOT",
                "the first execution event is not TASK_RECEIVED",
                "REJECT",
                events[0].event_ref,
            )
        )

    seen_ids: set[str] = set()
    observed_types: set[str] = set()
    previous_rank = -1
    for event in events:
        if event.event_id in seen_ids:
            findings.append(
                ReplayFinding(
                    "DUPLICATE_EVENT_ID",
                    f"event identifier {event.event_id!r} appears more than once",
                    "REJECT",
                    event.event_ref,
                )
            )
        seen_ids.add(event.event_id)

        rank = semantic_rank(event)
        if rank < previous_rank:
            findings.append(
                ReplayFinding(
                    "SEMANTIC_REORDERING",
                    f"event type {event.event_type} regressed in the workflow lifecycle",
                    "REJECT",
                    event.event_ref,
                )
            )
        previous_rank = max(previous_rank, rank)

        requirement = required_predecessor(event)
        if requirement is not None and requirement not in observed_types:
            findings.append(
                ReplayFinding(
                    "MISSING_REQUIRED_STAGE",
                    f"{event.event_type} requires prior {requirement}",
                    "REJECT",
                    event.event_ref,
                )
            )

        if event.event_type == TrailEventType.AUTHORIZATION_ISSUED.value:
            evidence_event = last_event_of_type(
                events,
                TrailEventType.EVIDENCE_DECISION.value,
                before_sequence=event.sequence,
            )
            decision = nested_value(evidence_event, "decision")
            if decision is not None and str(decision).upper() != "ALLOW":
                findings.append(
                    ReplayFinding(
                        "AUTHORIZATION_AFTER_NON_ALLOW",
                        f"authorization follows evidence decision {decision!r}",
                        "REJECT",
                        event.event_ref,
                    )
                )

        if event.event_type == TrailEventType.EXECUTION_COMPLETED.value:
            attempted = nested_value(event, "effect_attempted")
            if attempted is False:
                findings.append(
                    ReplayFinding(
                        "EXECUTION_WITHOUT_EFFECT_ATTEMPT",
                        "EXECUTION_COMPLETED reports no effect attempt",
                        "REJECT",
                        event.event_ref,
                    )
                )

        observed_types.add(event.event_type)

    if not is_terminal(events):
        findings.append(
            ReplayFinding(
                "PARTIAL_PATH",
                "the durable path has not reached a terminal workflow state",
                "DRIFT",
                events[-1].event_ref,
            )
        )
    return findings


def compare_baseline(
    events: Sequence[DurableEvent],
    baseline: Mapping[str, str],
) -> list[ReplayFinding]:
    findings: list[ReplayFinding] = []
    if not baseline:
        return findings
    by_id = {event.event_id: event for event in events}
    for event_id, expected_digest in sorted(baseline.items()):
        event = by_id.get(event_id)
        if event is None:
            findings.append(
                ReplayFinding(
                    "BASELINE_EVENT_MISSING",
                    f"baseline event {event_id!r} is absent from the replay trace",
                    "DRIFT",
                    f"event:{event_id}",
                )
            )
        elif event.payload_digest != expected_digest:
            findings.append(
                ReplayFinding(
                    "PAYLOAD_DRIFT",
                    f"event {event_id!r} differs from the baseline payload digest",
                    "DRIFT",
                    event.event_ref,
                )
            )
    baseline_ids = set(baseline)
    for event in events:
        if event.event_id not in baseline_ids:
            findings.append(
                ReplayFinding(
                    "UNEXPECTED_EVENT",
                    f"event {event.event_id!r} is not present in the replay baseline",
                    "DRIFT",
                    event.event_ref,
                )
            )
    return findings


def decision_for(
    findings: Sequence[ReplayFinding],
    events: Sequence[DurableEvent],
) -> ReplayDecision:
    if any(finding.severity == "REJECT" for finding in findings):
        return ReplayDecision.REJECTED
    if any(finding.severity == "DRIFT" for finding in findings):
        return ReplayDecision.DRIFTED
    if not is_terminal(events):
        return ReplayDecision.DRIFTED
    return ReplayDecision.ADMISSIBLE


def reason_for(
    decision: ReplayDecision,
    findings: Sequence[ReplayFinding],
) -> str:
    if not findings:
        return "The durable execution path is ordered, grounded, and replay-admissible."
    codes = ", ".join(finding.code for finding in findings)
    if decision is ReplayDecision.REJECTED:
        return f"The execution path is inadmissible: {codes}."
    return f"The execution path requires review because drift was detected: {codes}."


def is_terminal(events: Sequence[DurableEvent]) -> bool:
    last = events[-1]
    if last.event_type in {
        TrailEventType.EXECUTION_COMPLETED.value,
        TrailEventType.ARTIFACT_CREATED.value,
        TrailEventType.REPLAY_CHECKED.value,
    }:
        return True
    if last.event_type == TrailEventType.EVIDENCE_DECISION.value:
        decision = str(nested_value(last, "decision") or "").upper()
        return decision == "BLOCK"
    state = str(nested_value(last, "state") or "").upper()
    attempted = nested_value(last, "effect_attempted")
    return state in {"REJECTED", "EXPIRED"} and attempted is not True


def next_expected_type(events: Sequence[DurableEvent]) -> Optional[str]:
    last = events[-1]
    if is_terminal(events):
        if last.event_type == TrailEventType.EXECUTION_COMPLETED.value:
            return TrailEventType.REPLAY_CHECKED.value
        if last.event_type == TrailEventType.REPLAY_CHECKED.value:
            return TrailEventType.ARTIFACT_CREATED.value
        return None
    event_type = last.event_type
    if event_type == TrailEventType.TASK_RECEIVED.value:
        return TrailEventType.PLAN_CREATED.value
    if event_type in {TrailEventType.PLAN_CREATED.value, TrailEventType.PLAN_REVISED.value}:
        return TrailEventType.ROUTE_SELECTED.value
    if event_type == TrailEventType.ROUTE_SELECTED.value:
        return TrailEventType.WORK_COMPLETED.value
    if event_type == TrailEventType.WORK_COMPLETED.value:
        if nested_value(last, "execution_id") is not None:
            return TrailEventType.EXECUTION_COMMITTED.value
        return TrailEventType.CAUSAL_AUDIT.value
    if event_type == TrailEventType.CAUSAL_AUDIT.value:
        return TrailEventType.EVIDENCE_DECISION.value
    if event_type == TrailEventType.EVIDENCE_DECISION.value:
        decision = str(nested_value(last, "decision") or "").upper()
        if decision == "ALLOW":
            return TrailEventType.AUTHORIZATION_ISSUED.value
        return TrailEventType.EVIDENCE_DECISION.value
    if event_type == TrailEventType.AUTHORIZATION_ISSUED.value:
        return TrailEventType.EXECUTION_COMMITTED.value
    if event_type == TrailEventType.EXECUTION_COMMITTED.value:
        return TrailEventType.EXECUTION_COMPLETED.value
    return None


def semantic_rank(event: DurableEvent) -> int:
    ranks = {
        TrailEventType.TASK_RECEIVED.value: 0,
        TrailEventType.PLAN_CREATED.value: 1,
        TrailEventType.PLAN_REVISED.value: 1,
        TrailEventType.ROUTE_SELECTED.value: 2,
        TrailEventType.WORK_COMPLETED.value: 3,
        TrailEventType.CAUSAL_AUDIT.value: 4,
        TrailEventType.EVIDENCE_DECISION.value: 5,
        TrailEventType.AUTHORIZATION_ISSUED.value: 6,
        TrailEventType.EXECUTION_COMMITTED.value: 7,
        TrailEventType.EXECUTION_COMPLETED.value: 8,
        TrailEventType.REPLAY_CHECKED.value: 9,
        TrailEventType.ARTIFACT_CREATED.value: 10,
    }
    if (
        event.event_type == TrailEventType.WORK_COMPLETED.value
        and nested_value(event, "execution_id") is not None
    ):
        return 6
    return ranks.get(event.event_type, 3)


def required_predecessor(event: DurableEvent) -> Optional[str]:
    requirements = {
        TrailEventType.ROUTE_SELECTED.value: TrailEventType.PLAN_CREATED.value,
        TrailEventType.CAUSAL_AUDIT.value: TrailEventType.WORK_COMPLETED.value,
        TrailEventType.EVIDENCE_DECISION.value: TrailEventType.CAUSAL_AUDIT.value,
        TrailEventType.AUTHORIZATION_ISSUED.value: TrailEventType.EVIDENCE_DECISION.value,
        TrailEventType.EXECUTION_COMMITTED.value: TrailEventType.AUTHORIZATION_ISSUED.value,
        TrailEventType.EXECUTION_COMPLETED.value: TrailEventType.EXECUTION_COMMITTED.value,
    }
    return requirements.get(event.event_type)


def nested_value(event: Optional[DurableEvent], key: str) -> Any:
    if event is None:
        return None
    payload = event.payload
    inner = payload.get("payload") if isinstance(payload, Mapping) else None
    if isinstance(inner, Mapping) and key in inner:
        return inner.get(key)
    return payload.get(key) if isinstance(payload, Mapping) else None


def store_findings(findings: Sequence[StoreFinding]) -> list[ReplayFinding]:
    return [
        ReplayFinding(
            finding.code,
            finding.message,
            "REJECT",
            finding.event_ref,
        )
        for finding in findings
    ]


def verified_prefix(
    findings: Sequence[StoreFinding],
    events: Sequence[DurableEvent],
) -> int:
    refs = {finding.event_ref for finding in findings if finding.event_ref}
    for index, event in enumerate(events):
        if event.event_ref in refs:
            return index
    return 0


def last_event_of_type(
    events: Sequence[DurableEvent],
    event_type: str,
    *,
    before_sequence: int,
) -> Optional[DurableEvent]:
    matches = [
        event
        for event in events
        if event.event_type == event_type and event.sequence < before_sequence
    ]
    return matches[-1] if matches else None
