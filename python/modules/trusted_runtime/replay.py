"""Replay integration helpers for the LS Trusted Runtime."""

from __future__ import annotations

from dataclasses import replace

from .contracts import CognitiveTrail, ReusableArtifact, TrailEvent, TrailEventType
from .replay_engine import (
    DeterministicReplayAdapter,
    LTPReplayAdapter,
    build_resume_checkpoint,
    replay_from_store,
)
from .replay_models import (
    CONFORMANCE_REPORT_VERSION,
    RESUME_CHECKPOINT_VERSION,
    ConformanceReport,
    LTPConfig,
    ReplayDisabledError,
    ReplayError,
    ReplayFinding,
    ReplayOutcome,
    ReplayTraceError,
    ReplayUnavailableError,
    ResumeCheckpoint,
)


def replay_checked_event(
    outcome: ReplayOutcome,
    *,
    parent_event_id: str,
) -> TrailEvent:
    suffix = outcome.record.replay_id.split(":")[-1][:12]
    return TrailEvent(
        event_id=f"event-replay-{suffix}",
        task_id=outcome.record.task_id,
        trail_id=outcome.record.trail_id,
        event_type=TrailEventType.REPLAY_CHECKED,
        actor=outcome.record.actor,
        created_at=outcome.record.created_at,
        parent_cause=parent_event_id,
        evidence_refs=outcome.record.source_event_refs,
        payload={
            "replay_ref": outcome.replay_ref,
            "report_ref": outcome.report_ref,
            "decision": outcome.record.decision.value,
            "trace_digest": outcome.report.trace_digest,
            "resume_checkpoint_ref": outcome.report.resume_checkpoint_ref,
            "finding_codes": [finding.code for finding in outcome.report.findings],
        },
    )


def append_replay_outcome(
    trail: CognitiveTrail,
    outcome: ReplayOutcome,
    *,
    parent_event_id: str,
) -> CognitiveTrail:
    if trail.task_id != outcome.record.task_id or trail.trail_id != outcome.record.trail_id:
        raise ReplayTraceError("replay outcome belongs to another cognitive trail")
    if parent_event_id not in {event.event_id for event in trail.events}:
        raise ReplayTraceError("replay parent event is not present in the cognitive trail")
    event = replay_checked_event(outcome, parent_event_id=parent_event_id)
    return replace(trail, events=(*trail.events, event))


def attach_replay_outcome(
    artifact: ReusableArtifact,
    outcome: ReplayOutcome,
) -> ReusableArtifact:
    if artifact.task_id != outcome.record.task_id or artifact.trail_id != outcome.record.trail_id:
        raise ReplayTraceError("replay outcome belongs to another reusable artifact")
    return replace(artifact, replay_ref=outcome.report_ref)


__all__ = [
    "CONFORMANCE_REPORT_VERSION",
    "RESUME_CHECKPOINT_VERSION",
    "ConformanceReport",
    "DeterministicReplayAdapter",
    "LTPConfig",
    "LTPReplayAdapter",
    "ReplayDisabledError",
    "ReplayError",
    "ReplayFinding",
    "ReplayOutcome",
    "ReplayTraceError",
    "ReplayUnavailableError",
    "ResumeCheckpoint",
    "append_replay_outcome",
    "attach_replay_outcome",
    "build_resume_checkpoint",
    "replay_checked_event",
    "replay_from_store",
]
