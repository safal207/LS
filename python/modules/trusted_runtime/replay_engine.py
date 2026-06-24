from __future__ import annotations

import hashlib
from typing import Any, Mapping, Optional, Sequence

from .contracts import ReplayRecord
from .persistence import (
    DurableEvent,
    EventStoreCorruptionError,
    canonical_json,
    validate_event_chain,
)
from .replay_inspection import (
    compare_baseline,
    decision_for,
    inspect_path,
    next_expected_type,
    reason_for,
    store_findings,
    verified_prefix,
)
from .replay_models import (
    ConformanceReport,
    LTPConfig,
    ReplayDisabledError,
    ReplayFinding,
    ReplayOutcome,
    ReplayTraceError,
    ReplayUnavailableError,
    ResumeCheckpoint,
    stable_ref,
)


class DeterministicReplayAdapter:
    """Replay durable events without rerunning a model, tool, or side effect."""

    def __init__(self, actor: str = "replay:deterministic-ltp") -> None:
        if not actor:
            raise ValueError("replay actor must not be empty")
        self.actor = actor

    @property
    def adapter_name(self) -> str:
        return "deterministic-ltp"

    def replay(
        self,
        events: Sequence[Any],
        *,
        now: str,
        baseline_payload_digests: Optional[Mapping[str, str]] = None,
        corrupted_tail: bool = False,
    ) -> ReplayOutcome:
        durable_events = tuple(_coerce_event(item) for item in events)
        if not durable_events:
            raise ReplayTraceError("replay requires at least one durable event")

        chain_findings = validate_event_chain(
            durable_events[0].trail_id,
            durable_events,
        )
        findings: list[ReplayFinding] = []
        findings.extend(store_findings(chain_findings))
        findings.extend(inspect_path(durable_events))
        findings.extend(
            compare_baseline(
                durable_events,
                baseline_payload_digests or {},
            )
        )
        if corrupted_tail:
            findings.append(
                ReplayFinding(
                    "CORRUPTED_TAIL",
                    "the durable prefix is valid but later storage content is corrupted",
                    "REJECT",
                    durable_events[-1].event_ref,
                )
            )

        decision = decision_for(findings, durable_events)
        trace_digest = _trace_digest(durable_events)
        replay_id = stable_ref(
            "replay",
            {
                "trace_digest": trace_digest,
                "baseline_payload_digests": dict(
                    sorted((baseline_payload_digests or {}).items())
                ),
                "decision": decision.value,
            },
        )
        checkpoint = build_resume_checkpoint(
            durable_events,
            now=now,
            corrupted_tail=corrupted_tail,
        )
        finding_refs = tuple(
            finding.event_ref or f"finding:{finding.code}"
            for finding in findings
            if finding.severity in {"DRIFT", "REJECT"}
        )
        record = ReplayRecord(
            replay_id=replay_id,
            task_id=durable_events[0].task_id,
            trail_id=durable_events[0].trail_id,
            actor=self.actor,
            created_at=now,
            source_event_refs=tuple(event.event_ref for event in durable_events),
            decision=decision,
            reason=reason_for(decision, findings),
            drift_refs=finding_refs,
            parent_cause=durable_events[-1].event_id,
        )
        checkpoint_ref = stable_ref("checkpoint", checkpoint.to_dict())
        report_id = stable_ref(
            "conformance",
            {
                "replay_id": replay_id,
                "trace_digest": trace_digest,
                "decision": decision.value,
                "findings": [finding.to_dict() for finding in findings],
            },
        )
        report = ConformanceReport(
            report_id=report_id,
            replay_id=replay_id,
            task_id=record.task_id,
            trail_id=record.trail_id,
            decision=decision,
            created_at=now,
            trace_digest=trace_digest,
            durable_event_count=len(durable_events),
            verified_event_count=(
                len(durable_events)
                if not chain_findings
                else verified_prefix(chain_findings, durable_events)
            ),
            last_durable_event_ref=durable_events[-1].event_ref,
            findings=tuple(findings),
            redacted_field_count=sum(
                len(event.redacted_fields) for event in durable_events
            ),
            resume_checkpoint_ref=checkpoint_ref,
        )
        return ReplayOutcome(record, report, checkpoint, durable_events)


class LTPReplayAdapter:
    """Feature-flagged LTP port using the deterministic local profile."""

    def __init__(
        self,
        config: Optional[LTPConfig] = None,
        engine: Optional[DeterministicReplayAdapter] = None,
    ) -> None:
        self.config = config or LTPConfig()
        self.engine = engine or DeterministicReplayAdapter(actor=self.config.actor)

    @property
    def adapter_name(self) -> str:
        return "ltp"

    def replay(
        self,
        events: Sequence[Any],
        *,
        now: str,
        baseline_payload_digests: Optional[Mapping[str, str]] = None,
        corrupted_tail: bool = False,
    ) -> ReplayOutcome:
        if not self.config.enabled:
            raise ReplayDisabledError("LTP replay adapter is disabled")
        if self.engine is None:
            raise ReplayUnavailableError("LTP replay engine is unavailable")
        return self.engine.replay(
            events,
            now=now,
            baseline_payload_digests=baseline_payload_digests,
            corrupted_tail=corrupted_tail,
        )


def replay_from_store(
    store: Any,
    trail_id: str,
    *,
    now: str,
    adapter: Optional[DeterministicReplayAdapter] = None,
    baseline_payload_digests: Optional[Mapping[str, str]] = None,
) -> ReplayOutcome:
    engine = adapter or DeterministicReplayAdapter()
    if hasattr(store, "scan"):
        scan = store.scan(trail_id)
        if not scan.events:
            if scan.findings:
                raise EventStoreCorruptionError(
                    f"no valid durable prefix for {trail_id!r}",
                    scan.findings,
                )
            raise ReplayTraceError(f"event stream {trail_id!r} is empty")
        return engine.replay(
            scan.events,
            now=now,
            baseline_payload_digests=baseline_payload_digests,
            corrupted_tail=bool(scan.findings),
        )
    return engine.replay(
        store.read(trail_id),
        now=now,
        baseline_payload_digests=baseline_payload_digests,
    )


def build_resume_checkpoint(
    events: Sequence[DurableEvent],
    *,
    now: str,
    corrupted_tail: bool = False,
) -> ResumeCheckpoint:
    if not events:
        raise ReplayTraceError("resume checkpoint requires a durable prefix")
    last = events[-1]
    next_type = next_expected_type(events)
    checkpoint_id = stable_ref(
        "resume",
        {
            "last_event_ref": last.event_ref,
            "next_expected_event_type": next_type,
            "corrupted_tail": corrupted_tail,
        },
    )
    return ResumeCheckpoint(
        checkpoint_id=checkpoint_id,
        task_id=last.task_id,
        trail_id=last.trail_id,
        created_at=now,
        last_event_id=last.event_id,
        last_event_ref=last.event_ref,
        last_event_type=last.event_type,
        next_expected_event_type=next_type,
        durable_event_count=len(events),
        corrupted_tail=corrupted_tail,
    )


def _coerce_event(value: Any) -> DurableEvent:
    if isinstance(value, DurableEvent):
        return value
    if isinstance(value, Mapping):
        return DurableEvent.from_mapping(value)
    raise TypeError(f"unsupported replay event type: {type(value).__name__}")


def _trace_digest(events: Sequence[DurableEvent]) -> str:
    return hashlib.sha256(
        canonical_json([event.event_hash for event in events]).encode("utf-8")
    ).hexdigest()
