from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping, Optional, Sequence

from .contracts import (
    CognitiveTrail,
    ReusableArtifact,
    TrailEvent,
    TrailEventType,
)


CAUSAL_AUDIT_REPORT_VERSION = "trusted_runtime.causal_audit_report.v0.1"


class CausalSeverity(str, Enum):
    OK = "OK"
    WARN = "WARN"
    FAIL = "FAIL"


class CausalAuditError(RuntimeError):
    """Base error for causal-audit integrations and authorization guards."""


class CausalAuditDisabledError(CausalAuditError):
    """Raised when an optional CML integration is not enabled."""


class CausalAuditTimeoutError(CausalAuditError):
    """Raised when a CML subprocess exceeds its configured timeout."""


class CausalAuditUnavailableError(CausalAuditError):
    """Raised when CML cannot be invoked."""


class MalformedCausalAuditResponseError(CausalAuditError):
    """Raised when CML returns an unusable response."""


class CausalAuthorizationBlocked(CausalAuditError):
    """Raised when downstream authorization lacks valid causal ancestry."""


@dataclass(frozen=True)
class CausalRecord:
    """Provider-neutral LS record that serializes to the CML JSONL shape."""

    record_id: str
    timestamp_ns: int
    actor: str
    action: str
    object_ref: Mapping[str, Any]
    permitted_by: str
    parent_cause: Optional[str]
    evidence_refs: tuple[str, ...] = ()
    delegation_ref: Optional[str] = None
    approval_ref: Optional[str] = None
    high_impact: bool = False

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must not be empty")
        if not isinstance(self.timestamp_ns, int) or isinstance(self.timestamp_ns, bool):
            raise TypeError("timestamp_ns must be a strict integer")
        if self.timestamp_ns < 0:
            raise ValueError("timestamp_ns must be non-negative")
        if not self.actor or not self.action or not self.permitted_by:
            raise ValueError("actor, action, and permitted_by must not be empty")
        if self.parent_cause == self.record_id:
            raise ValueError("a causal record cannot be its own parent")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique")

    def to_cml_dict(self) -> dict[str, Any]:
        object_payload = dict(self.object_ref)
        if self.evidence_refs:
            object_payload["evidence_refs"] = list(self.evidence_refs)
        if self.delegation_ref:
            object_payload["delegation_ref"] = self.delegation_ref
        if self.approval_ref:
            object_payload["approval_ref"] = self.approval_ref
        object_payload["high_impact"] = self.high_impact
        return {
            "id": self.record_id,
            "timestamp": self.timestamp_ns,
            "actor": {"pid": 0, "uid": 0, "comm": self.actor},
            "action": self.action,
            "object": object_payload,
            "permitted_by": self.permitted_by,
            "parent_cause": self.parent_cause,
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "CausalRecord":
        actor = payload.get("actor", "unknown")
        if isinstance(actor, Mapping):
            actor = actor.get("comm", f"uid:{actor.get('uid', 0)}")
        object_ref = payload.get("object_ref", payload.get("object", {}))
        if not isinstance(object_ref, Mapping):
            object_ref = {"value": object_ref}
        return cls(
            record_id=str(payload.get("record_id", payload.get("id", ""))),
            timestamp_ns=int(payload.get("timestamp_ns", payload.get("timestamp", 0))),
            actor=str(actor),
            action=str(payload.get("action", "")),
            object_ref=dict(object_ref),
            permitted_by=str(payload.get("permitted_by", "")),
            parent_cause=payload.get("parent_cause"),
            evidence_refs=tuple(payload.get("evidence_refs", ())),
            delegation_ref=payload.get("delegation_ref"),
            approval_ref=payload.get("approval_ref"),
            high_impact=bool(payload.get("high_impact", False)),
        )


@dataclass(frozen=True)
class CausalFinding:
    code: str
    severity: CausalSeverity
    record_id: str
    message: str
    blocking: bool
    parent_cause: Optional[str] = None
    chain_ids: tuple[str, ...] = ()
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.code or not self.record_id or not self.message:
            raise ValueError("finding code, record_id, and message must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "record_id": self.record_id,
            "message": self.message,
            "blocking": self.blocking,
            "parent_cause": self.parent_cause,
            "chain_ids": list(self.chain_ids),
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class CausalAuditReport:
    audit_id: str
    task_id: str
    trail_id: str
    adapter: str
    actor: str
    created_at: str
    records_checked: int
    root_ids: tuple[str, ...]
    findings: tuple[CausalFinding, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = CAUSAL_AUDIT_REPORT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CAUSAL_AUDIT_REPORT_VERSION:
            raise ValueError(
                f"unsupported causal audit report version: {self.schema_version}"
            )
        if not all(
            (self.audit_id, self.task_id, self.trail_id, self.adapter, self.actor, self.created_at)
        ):
            raise ValueError("causal audit identifiers and timestamps must not be empty")
        if self.records_checked < 1:
            raise ValueError("causal audit requires at least one checked record")
        if len(self.root_ids) != len(set(self.root_ids)):
            raise ValueError("root_ids must be unique")

    @property
    def passed(self) -> bool:
        return not any(
            finding.severity is CausalSeverity.FAIL for finding in self.findings
        )

    @property
    def authorization_allowed(self) -> bool:
        return not any(finding.blocking for finding in self.findings)

    @property
    def blocking_codes(self) -> tuple[str, ...]:
        return tuple(
            finding.code for finding in self.findings if finding.blocking
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "audit_id": self.audit_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "adapter": self.adapter,
            "actor": self.actor,
            "created_at": self.created_at,
            "records_checked": self.records_checked,
            "root_ids": list(self.root_ids),
            "passed": self.passed,
            "authorization_allowed": self.authorization_allowed,
            "blocking_codes": list(self.blocking_codes),
            "findings": [finding.to_dict() for finding in self.findings],
            "metadata": dict(self.metadata),
        }


EVENT_ACTIONS: Mapping[TrailEventType, str] = {
    TrailEventType.TASK_RECEIVED: "open",
    TrailEventType.PLAN_CREATED: "write",
    TrailEventType.PLAN_REVISED: "write",
    TrailEventType.ROUTE_SELECTED: "connect",
    TrailEventType.WORK_COMPLETED: "write",
    TrailEventType.CAUSAL_AUDIT: "read",
    TrailEventType.EVIDENCE_DECISION: "read",
    TrailEventType.AUTHORIZATION_ISSUED: "exec",
    TrailEventType.EXECUTION_COMMITTED: "exec",
    TrailEventType.EXECUTION_COMPLETED: "exec",
    TrailEventType.REPLAY_CHECKED: "read",
    TrailEventType.ARTIFACT_CREATED: "write",
}

HIGH_IMPACT_EVENTS = {
    TrailEventType.AUTHORIZATION_ISSUED,
    TrailEventType.EXECUTION_COMMITTED,
    TrailEventType.EXECUTION_COMPLETED,
}


def trail_to_causal_records(trail: CognitiveTrail) -> tuple[CausalRecord, ...]:
    """Map an LS Cognitive Trail to deterministic CML-compatible records."""

    root = CausalRecord(
        record_id=trail.task_id,
        timestamp_ns=0,
        actor=trail.actor,
        action="open",
        object_ref={
            "kind": "task_root",
            "task_id": trail.task_id,
            "trail_id": trail.trail_id,
        },
        permitted_by=f"root_event:{trail.task_id}",
        parent_cause=None,
    )
    records = [root]
    for index, event in enumerate(trail.events, start=1):
        payload = event.payload
        delegation_ref = _optional_string(payload.get("delegation_ref"))
        approval_ref = _optional_string(payload.get("approval_ref"))
        high_impact = bool(payload.get("high_impact", False)) or (
            event.event_type in HIGH_IMPACT_EVENTS
        )
        permitted_by = (
            f"approval:{approval_ref}"
            if approval_ref
            else f"delegation:{delegation_ref}"
            if delegation_ref
            else f"parent_cause:{event.parent_cause}"
        )
        object_ref = {
            "kind": "ls_trail_event",
            "event_type": event.event_type.value,
            "task_id": event.task_id,
            "trail_id": event.trail_id,
        }
        for key in ("role_id", "route_id", "decision", "scope"):
            if key in payload:
                object_ref[key] = payload[key]
        records.append(
            CausalRecord(
                record_id=event.event_id,
                timestamp_ns=index,
                actor=event.actor,
                action=EVENT_ACTIONS[event.event_type],
                object_ref=object_ref,
                permitted_by=permitted_by,
                parent_cause=event.parent_cause,
                evidence_refs=event.evidence_refs,
                delegation_ref=delegation_ref,
                approval_ref=approval_ref,
                high_impact=high_impact,
            )
        )
    return tuple(records)


class DeterministicCausalAuditAdapter:
    """Dependency-free structural validator used for fixtures and local tests."""

    @property
    def adapter_name(self) -> str:
        return "deterministic-causal-audit"

    def audit(self, trail: CognitiveTrail) -> CausalAuditReport:
        return self.audit_records(
            trail_to_causal_records(trail),
            task_id=trail.task_id,
            trail_id=trail.trail_id,
            actor=f"adapter:{self.adapter_name}",
            created_at=trail.created_at,
        )

    def audit_records(
        self,
        records: Sequence[CausalRecord],
        *,
        task_id: str,
        trail_id: str,
        actor: str,
        created_at: str,
    ) -> CausalAuditReport:
        if not records:
            raise ValueError("causal audit requires records")
        index: dict[str, CausalRecord] = {}
        findings: list[CausalFinding] = []
        duplicate_ids: set[str] = set()
        for record in records:
            if record.record_id in index:
                duplicate_ids.add(record.record_id)
            index[record.record_id] = record
        for record_id in sorted(duplicate_ids):
            findings.append(
                CausalFinding(
                    code="LS-CML-R0-DUPLICATE_RECORD",
                    severity=CausalSeverity.FAIL,
                    record_id=record_id,
                    message="Causal record identifier appears more than once.",
                    blocking=True,
                )
            )

        roots = tuple(
            record.record_id
            for record in records
            if record.parent_cause is None
            and record.permitted_by.startswith("root_event:")
        )
        for record in records:
            if record.parent_cause is not None and record.parent_cause not in index:
                findings.append(
                    CausalFinding(
                        code="CML-AUDIT-R1-MISSING_PARENT",
                        severity=CausalSeverity.FAIL,
                        record_id=record.record_id,
                        message=(
                            f"parent_cause {record.parent_cause!r} does not exist "
                            "in the causal record set."
                        ),
                        blocking=True,
                        parent_cause=record.parent_cause,
                    )
                )
            if record.parent_cause is None and not record.permitted_by.startswith(
                "root_event:"
            ):
                if record.permitted_by.startswith("root_event"):
                    findings.append(
                        CausalFinding(
                            code="CML-AUDIT-R4-AMBIGUOUS_ROOT",
                            severity=CausalSeverity.WARN,
                            record_id=record.record_id,
                            message=(
                                "Root authority label resembles root_event: but "
                                "does not use the explicit separator."
                            ),
                            blocking=True,
                        )
                    )
                elif record.permitted_by != "unobserved_parent":
                    findings.append(
                        CausalFinding(
                            code="CML-AUDIT-R2-GAP_NOT_MARKED",
                            severity=CausalSeverity.FAIL,
                            record_id=record.record_id,
                            message=(
                                "Record has no parent and is not an explicit root "
                                "or marked causal gap."
                            ),
                            blocking=True,
                        )
                    )

        for record in records:
            chain, state = _trace_chain(record, index)
            if state == "cycle":
                findings.append(
                    CausalFinding(
                        code="LS-CML-R5-BROKEN_LINEAGE",
                        severity=CausalSeverity.FAIL,
                        record_id=record.record_id,
                        message="Causal ancestry contains a cycle.",
                        blocking=True,
                        parent_cause=record.parent_cause,
                        chain_ids=chain,
                    )
                )
            elif record.high_impact and state != "valid_root" and not _has_approval(
                chain, index
            ):
                findings.append(
                    CausalFinding(
                        code="LS-CML-R6-ORPHAN_HIGH_IMPACT_ACTION",
                        severity=CausalSeverity.FAIL,
                        record_id=record.record_id,
                        message=(
                            "High-impact action has no traceable task root or "
                            "explicit approval ancestor."
                        ),
                        blocking=True,
                        parent_cause=record.parent_cause,
                        chain_ids=chain,
                    )
                )

        finding_records = {finding.record_id for finding in findings}
        for record in records:
            if record.record_id not in finding_records:
                chain, state = _trace_chain(record, index)
                findings.append(
                    CausalFinding(
                        code="CML-AUDIT-OK-VALID_LINEAGE",
                        severity=CausalSeverity.OK,
                        record_id=record.record_id,
                        message="Record has inspectable causal ancestry.",
                        blocking=False,
                        parent_cause=record.parent_cause,
                        chain_ids=chain if state == "valid_root" else (),
                    )
                )

        return CausalAuditReport(
            audit_id=f"causal-audit-{trail_id}",
            task_id=task_id,
            trail_id=trail_id,
            adapter=self.adapter_name,
            actor=actor,
            created_at=created_at,
            records_checked=len(records),
            root_ids=roots,
            findings=tuple(findings),
            metadata={
                "rules": ["R1", "R2", "R4", "LS-R0", "LS-R5", "LS-R6"],
                "format": "cml-jsonl-compatible",
            },
        )


def require_valid_causal_ancestry(report: CausalAuditReport) -> CausalAuditReport:
    """Fail closed before evidence or execution authorization is issued."""

    if not report.authorization_allowed:
        codes = ", ".join(report.blocking_codes) or "unknown causal failure"
        raise CausalAuthorizationBlocked(
            f"downstream authorization blocked by causal findings: {codes}"
        )
    return report


def causal_audit_event(
    report: CausalAuditReport,
    *,
    parent_cause: str,
    event_id: Optional[str] = None,
) -> TrailEvent:
    return TrailEvent(
        event_id=event_id or f"event-{report.audit_id}",
        task_id=report.task_id,
        trail_id=report.trail_id,
        event_type=TrailEventType.CAUSAL_AUDIT,
        actor=report.actor,
        created_at=report.created_at,
        parent_cause=parent_cause,
        payload=report.to_dict(),
    )


def attach_causal_audit(
    artifact: ReusableArtifact,
    reports: Sequence[CausalAuditReport],
) -> ReusableArtifact:
    """Embed causal report references and inspectable findings in an artifact."""

    audit_refs = tuple(dict.fromkeys(
        (*artifact.causal_audit_refs, *(report.audit_id for report in reports))
    ))
    finding_payloads = tuple(
        finding.to_dict()
        for report in reports
        for finding in report.findings
        if finding.severity is not CausalSeverity.OK
    )
    return replace(
        artifact,
        causal_audit_refs=audit_refs,
        causal_findings=(*artifact.causal_findings, *finding_payloads),
    )


def _trace_chain(
    record: CausalRecord,
    index: Mapping[str, CausalRecord],
) -> tuple[tuple[str, ...], str]:
    chain: list[str] = []
    seen: set[str] = set()
    current: Optional[CausalRecord] = record
    while current is not None:
        if current.record_id in seen:
            chain.append(current.record_id)
            return tuple(chain), "cycle"
        seen.add(current.record_id)
        chain.append(current.record_id)
        if current.parent_cause is None:
            if current.permitted_by.startswith("root_event:"):
                return tuple(chain), "valid_root"
            return tuple(chain), "unrooted"
        current = index.get(current.parent_cause)
        if current is None:
            return tuple(chain), "missing_parent"
    return tuple(chain), "unrooted"


def _has_approval(
    chain: Sequence[str],
    index: Mapping[str, CausalRecord],
) -> bool:
    return any(
        index[record_id].approval_ref
        or index[record_id].permitted_by.startswith("approval:")
        for record_id in chain
        if record_id in index
    )


def _optional_string(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None
