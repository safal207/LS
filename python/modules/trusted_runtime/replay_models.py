from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional

from .contracts import ReplayDecision, ReplayRecord
from .persistence import DurableEvent, canonical_json, events_to_jsonl


CONFORMANCE_REPORT_VERSION = "trusted_runtime.conformance_report.v0.1"
RESUME_CHECKPOINT_VERSION = "trusted_runtime.resume_checkpoint.v0.1"


class ReplayError(RuntimeError):
    """Base error for deterministic replay and inspection."""


class ReplayDisabledError(ReplayError):
    """Raised when the optional LTP adapter is disabled."""


class ReplayUnavailableError(ReplayError):
    """Raised when a replay backend is unavailable."""


class ReplayTraceError(ReplayError):
    """Raised when no inspectable durable trace is available."""


@dataclass(frozen=True)
class ReplayFinding:
    code: str
    message: str
    severity: str
    event_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("replay finding code and message must not be empty")
        if self.severity not in {"INFO", "DRIFT", "REJECT"}:
            raise ValueError(f"unsupported replay finding severity: {self.severity}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "event_ref": self.event_ref,
        }


@dataclass(frozen=True)
class ResumeCheckpoint:
    checkpoint_id: str
    task_id: str
    trail_id: str
    created_at: str
    last_event_id: str
    last_event_ref: str
    last_event_type: str
    next_expected_event_type: Optional[str]
    durable_event_count: int
    corrupted_tail: bool
    schema_version: str = RESUME_CHECKPOINT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != RESUME_CHECKPOINT_VERSION:
            raise ValueError(
                f"unsupported resume checkpoint version: {self.schema_version}"
            )
        required = (
            self.checkpoint_id,
            self.task_id,
            self.trail_id,
            self.created_at,
            self.last_event_id,
            self.last_event_ref,
            self.last_event_type,
        )
        if not all(required):
            raise ValueError("resume checkpoint fields must not be empty")
        if self.durable_event_count < 1:
            raise ValueError("resume checkpoint requires at least one durable event")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "created_at": self.created_at,
            "last_event_id": self.last_event_id,
            "last_event_ref": self.last_event_ref,
            "last_event_type": self.last_event_type,
            "next_expected_event_type": self.next_expected_event_type,
            "durable_event_count": self.durable_event_count,
            "corrupted_tail": self.corrupted_tail,
        }


@dataclass(frozen=True)
class ConformanceReport:
    report_id: str
    replay_id: str
    task_id: str
    trail_id: str
    decision: ReplayDecision
    created_at: str
    trace_digest: str
    durable_event_count: int
    verified_event_count: int
    last_durable_event_ref: str
    findings: tuple[ReplayFinding, ...]
    redacted_field_count: int
    resume_checkpoint_ref: str
    schema_version: str = CONFORMANCE_REPORT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CONFORMANCE_REPORT_VERSION:
            raise ValueError(
                f"unsupported conformance report version: {self.schema_version}"
            )
        required = (
            self.report_id,
            self.replay_id,
            self.task_id,
            self.trail_id,
            self.created_at,
            self.trace_digest,
            self.last_durable_event_ref,
            self.resume_checkpoint_ref,
        )
        if not all(required):
            raise ValueError("conformance report fields must not be empty")
        if self.durable_event_count < 1 or self.verified_event_count < 0:
            raise ValueError("conformance report event counts are invalid")
        if self.verified_event_count > self.durable_event_count:
            raise ValueError("verified event count exceeds durable event count")
        if self.redacted_field_count < 0:
            raise ValueError("redacted field count must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "report_id": self.report_id,
            "replay_id": self.replay_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "decision": self.decision.value,
            "created_at": self.created_at,
            "trace_digest": self.trace_digest,
            "durable_event_count": self.durable_event_count,
            "verified_event_count": self.verified_event_count,
            "last_durable_event_ref": self.last_durable_event_ref,
            "findings": [finding.to_dict() for finding in self.findings],
            "redacted_field_count": self.redacted_field_count,
            "resume_checkpoint_ref": self.resume_checkpoint_ref,
        }


@dataclass(frozen=True)
class ReplayOutcome:
    record: ReplayRecord
    report: ConformanceReport
    checkpoint: ResumeCheckpoint
    events: tuple[DurableEvent, ...] = field(repr=False)

    @property
    def replay_ref(self) -> str:
        return stable_ref("replay-record", self.record.to_dict())

    @property
    def report_ref(self) -> str:
        return stable_ref("conformance-report", self.report.to_dict())

    def export_files(self) -> dict[str, str]:
        findings = "\n".join(
            f"- [{finding.severity}] {finding.code}: {finding.message}"
            for finding in self.report.findings
        ) or "- No conformance findings."
        readme = (
            "# LS Trusted Runtime replay evidence\n\n"
            f"Decision: **{self.record.decision.value}**\n\n"
            f"Replay record: `{self.replay_ref}`\n\n"
            f"Conformance report: `{self.report_ref}`\n\n"
            "## Findings\n\n"
            f"{findings}\n\n"
            "The trace contains durable redacted events only. Models and tools "
            "were not rerun to produce this bundle.\n"
        )
        return {
            "trace.jsonl": events_to_jsonl(self.events),
            "replay-record.json": pretty_json(self.record.to_dict()),
            "conformance-report.json": pretty_json(self.report.to_dict()),
            "resume-checkpoint.json": pretty_json(self.checkpoint.to_dict()),
            "README.md": readme,
        }


@dataclass(frozen=True)
class LTPConfig:
    enabled: bool = False
    actor: str = "adapter:ltp"

    def __post_init__(self) -> None:
        if not self.actor:
            raise ValueError("LTP actor must not be empty")


def stable_ref(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}:sha256:{digest}"


def pretty_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
