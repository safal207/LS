"""Typed, evidence-aware cross-thread coordination primitives.

This module deliberately separates transport success from verification, state
acceptance, and execution authority. It does not execute external effects.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable, Iterable, Mapping, Sequence


class CrossThreadViolation(ValueError):
    """Raised when an event, capability, or audit invariant is violated."""


class EventType(StrEnum):
    QUESTION = "QUESTION"
    PROPOSAL = "PROPOSAL"
    OBSERVATION = "OBSERVATION"
    STATE_UPDATE = "STATE_UPDATE"
    RESULT = "RESULT"
    ACTION_REQUEST = "ACTION_REQUEST"
    BLOCKER = "BLOCKER"
    COMPLETION = "COMPLETION"


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    CLAIMED = "CLAIMED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class DispositionStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    DEFERRED = "DEFERRED"


@dataclass(frozen=True)
class Authority:
    may_inform: bool = True
    may_request_action: bool = False
    may_authorize_execution: bool = False

    def is_subset_of(self, other: "Authority") -> bool:
        return (
            (not self.may_inform or other.may_inform)
            and (not self.may_request_action or other.may_request_action)
            and (
                not self.may_authorize_execution
                or other.may_authorize_execution
            )
        )


@dataclass(frozen=True)
class EvidenceRef:
    ref: str
    sha256: str | None = None
    media_type: str = "application/octet-stream"


@dataclass(frozen=True)
class EvidenceVerdict:
    ref: str
    verified: bool
    reason: str


@dataclass(frozen=True)
class CrossThreadEvent:
    schema_version: str
    event_id: str
    trajectory_id: str
    continuation_id: str
    source_thread_id: str
    source_agent_id: str
    source_role: str
    target_thread_id: str
    event_type: EventType
    subject: str
    payload: Mapping[str, Any]
    evidence_refs: tuple[EvidenceRef, ...]
    verification_status: VerificationStatus
    authority: Authority
    sequence: int
    created_at: str
    supersedes_event_id: str | None = None

    @staticmethod
    def _clean(value: str, field_name: str) -> str:
        if not isinstance(value, str):
            raise CrossThreadViolation(f"{field_name} must be a string")
        cleaned = value.strip()
        if not cleaned:
            raise CrossThreadViolation(f"{field_name} must not be empty")
        return cleaned

    @staticmethod
    def _canonical(value: Mapping[str, Any]) -> bytes:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")

    @classmethod
    def build(
        cls,
        *,
        trajectory_id: str,
        continuation_id: str,
        source_thread_id: str,
        source_agent_id: str,
        source_role: str,
        target_thread_id: str,
        event_type: EventType | str,
        subject: str,
        payload: Mapping[str, Any],
        evidence_refs: Sequence[EvidenceRef] = (),
        verification_status: VerificationStatus | str = VerificationStatus.UNVERIFIED,
        authority: Authority = Authority(),
        sequence: int,
        created_at: str | None = None,
        supersedes_event_id: str | None = None,
        event_id: str | None = None,
    ) -> "CrossThreadEvent":
        normalized_type = EventType(str(event_type))
        normalized_verification = VerificationStatus(str(verification_status))
        if not isinstance(sequence, int) or sequence < 1:
            raise CrossThreadViolation("sequence must be a positive integer")
        if not isinstance(payload, Mapping):
            raise CrossThreadViolation("payload must be an object")

        timestamp = created_at or datetime.now(timezone.utc).isoformat()
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise CrossThreadViolation("created_at must be ISO-8601") from exc

        unsigned = {
            "schema_version": "cross-thread-event/v0.1",
            "trajectory_id": cls._clean(trajectory_id, "trajectory_id"),
            "continuation_id": cls._clean(continuation_id, "continuation_id"),
            "source_thread_id": cls._clean(source_thread_id, "source_thread_id"),
            "source_agent_id": cls._clean(source_agent_id, "source_agent_id"),
            "source_role": cls._clean(source_role, "source_role"),
            "target_thread_id": cls._clean(target_thread_id, "target_thread_id"),
            "event_type": normalized_type.value,
            "subject": cls._clean(subject, "subject"),
            "payload": dict(payload),
            "evidence_refs": [asdict(ref) for ref in evidence_refs],
            "verification_status": normalized_verification.value,
            "authority": asdict(authority),
            "sequence": sequence,
            "created_at": timestamp,
            "supersedes_event_id": supersedes_event_id,
        }
        derived_id = hashlib.sha256(cls._canonical(unsigned)).hexdigest()
        normalized_event_id = event_id or derived_id
        cls._clean(normalized_event_id, "event_id")
        return cls(
            schema_version="cross-thread-event/v0.1",
            event_id=normalized_event_id,
            trajectory_id=unsigned["trajectory_id"],
            continuation_id=unsigned["continuation_id"],
            source_thread_id=unsigned["source_thread_id"],
            source_agent_id=unsigned["source_agent_id"],
            source_role=unsigned["source_role"],
            target_thread_id=unsigned["target_thread_id"],
            event_type=normalized_type,
            subject=unsigned["subject"],
            payload=dict(payload),
            evidence_refs=tuple(evidence_refs),
            verification_status=normalized_verification,
            authority=authority,
            sequence=sequence,
            created_at=timestamp,
            supersedes_event_id=supersedes_event_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "trajectory_id": self.trajectory_id,
            "continuation_id": self.continuation_id,
            "source": {
                "thread_id": self.source_thread_id,
                "agent_id": self.source_agent_id,
                "role": self.source_role,
            },
            "target": {"thread_id": self.target_thread_id},
            "event_type": self.event_type.value,
            "subject": self.subject,
            "payload": dict(self.payload),
            "evidence_refs": [asdict(ref) for ref in self.evidence_refs],
            "verification_status": self.verification_status.value,
            "authority": asdict(self.authority),
            "sequence": self.sequence,
            "created_at": self.created_at,
            "supersedes_event_id": self.supersedes_event_id,
        }

    @classmethod
    def from_dict(cls, document: Mapping[str, Any]) -> "CrossThreadEvent":
        source = document.get("source")
        target = document.get("target")
        if not isinstance(source, Mapping) or not isinstance(target, Mapping):
            raise CrossThreadViolation("source and target must be objects")
        evidence_items = document.get("evidence_refs", ())
        if not isinstance(evidence_items, Sequence) or isinstance(evidence_items, (str, bytes)):
            raise CrossThreadViolation("evidence_refs must be an array")
        evidence_refs = tuple(
            EvidenceRef(
                ref=str(item.get("ref", "")),
                sha256=item.get("sha256"),
                media_type=str(item.get("media_type", "application/octet-stream")),
            )
            for item in evidence_items
            if isinstance(item, Mapping)
        )
        authority_doc = document.get("authority", {})
        if not isinstance(authority_doc, Mapping):
            raise CrossThreadViolation("authority must be an object")
        authority = Authority(
            may_inform=bool(authority_doc.get("may_inform", True)),
            may_request_action=bool(authority_doc.get("may_request_action", False)),
            may_authorize_execution=bool(
                authority_doc.get("may_authorize_execution", False)
            ),
        )
        event = cls.build(
            trajectory_id=str(document.get("trajectory_id", "")),
            continuation_id=str(document.get("continuation_id", "")),
            source_thread_id=str(source.get("thread_id", "")),
            source_agent_id=str(source.get("agent_id", "")),
            source_role=str(source.get("role", "")),
            target_thread_id=str(target.get("thread_id", "")),
            event_type=str(document.get("event_type", "")),
            subject=str(document.get("subject", "")),
            payload=document.get("payload", {}),
            evidence_refs=evidence_refs,
            verification_status=str(document.get("verification_status", "UNVERIFIED")),
            authority=authority,
            sequence=document.get("sequence", 0),
            created_at=str(document.get("created_at", "")),
            supersedes_event_id=document.get("supersedes_event_id"),
            event_id=str(document.get("event_id", "")),
        )
        if document.get("schema_version") != "cross-thread-event/v0.1":
            raise CrossThreadViolation("unsupported schema_version")
        return event


@dataclass(frozen=True)
class CapabilityGrant:
    capability_id: str
    source_thread_id: str
    target_thread_id: str
    allowed_event_types: tuple[EventType, ...]
    max_authority: Authority = Authority()
    allow_read: bool = False
    requires_target_consent: bool = True
    expires_at: str | None = None

    @classmethod
    def build(
        cls,
        *,
        source_thread_id: str,
        target_thread_id: str,
        allowed_event_types: Iterable[EventType | str],
        max_authority: Authority = Authority(),
        allow_read: bool = False,
        requires_target_consent: bool = True,
        expires_at: str | None = None,
    ) -> "CapabilityGrant":
        normalized_types = tuple(
            sorted(
                {EventType(str(item)) for item in allowed_event_types},
                key=lambda item: item.value,
            )
        )
        if not normalized_types:
            raise CrossThreadViolation("allowed_event_types must not be empty")
        payload = {
            "source_thread_id": source_thread_id.strip(),
            "target_thread_id": target_thread_id.strip(),
            "allowed_event_types": [item.value for item in normalized_types],
            "max_authority": asdict(max_authority),
            "allow_read": allow_read,
            "requires_target_consent": requires_target_consent,
            "expires_at": expires_at,
        }
        if not payload["source_thread_id"] or not payload["target_thread_id"]:
            raise CrossThreadViolation("capability thread ids must not be empty")
        if expires_at is not None:
            try:
                datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise CrossThreadViolation("expires_at must be ISO-8601") from exc
        capability_id = hashlib.sha256(
            CrossThreadEvent._canonical(payload)
        ).hexdigest()
        return cls(
            capability_id=capability_id,
            source_thread_id=payload["source_thread_id"],
            target_thread_id=payload["target_thread_id"],
            allowed_event_types=normalized_types,
            max_authority=max_authority,
            allow_read=allow_read,
            requires_target_consent=requires_target_consent,
            expires_at=expires_at,
        )


@dataclass(frozen=True)
class DecisionReceipt:
    decision_id: str
    event_id: str
    target_thread_id: str
    status: DispositionStatus
    reason: str
    evidence_verdicts: tuple[EvidenceVerdict, ...]
    accepted_state_version: int | None
    recorded_at: str


@dataclass(frozen=True)
class ThreadIdentity:
    thread_id: str
    agent_id: str
    role: str
    accepts_messages: bool = True
    archived: bool = False


@dataclass(frozen=True)
class AcceptedState:
    trajectory_id: str
    subject: str
    event_id: str
    sequence: int
    payload: Mapping[str, Any]
    source_thread_id: str
    accepted_at: str


EvidenceChecker = Callable[[EvidenceRef], EvidenceVerdict]


class InMemoryEvidenceStore:
    """Small deterministic evidence registry for demos and conformance tests."""

    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}

    def put(
        self,
        ref: str,
        content: str | bytes,
        *,
        media_type: str = "text/plain",
    ) -> EvidenceRef:
        data = content.encode("utf-8") if isinstance(content, str) else content
        self._content[ref] = data
        return EvidenceRef(
            ref=ref,
            sha256=hashlib.sha256(data).hexdigest(),
            media_type=media_type,
        )

    def verify(self, evidence: EvidenceRef) -> EvidenceVerdict:
        data = self._content.get(evidence.ref)
        if data is None:
            return EvidenceVerdict(evidence.ref, False, "evidence reference not found")
        if evidence.sha256 is None:
            return EvidenceVerdict(evidence.ref, False, "evidence digest missing")
        actual = hashlib.sha256(data).hexdigest()
        if actual != evidence.sha256:
            return EvidenceVerdict(evidence.ref, False, "evidence digest mismatch")
        return EvidenceVerdict(evidence.ref, True, "digest matched registered evidence")


class CrossThreadRuntime:
    """Fail-closed receiver for typed messages between durable peer threads."""

    EVIDENCE_REQUIRED_TYPES = frozenset(
        {
            EventType.STATE_UPDATE,
            EventType.RESULT,
            EventType.COMPLETION,
        }
    )

    def __init__(self) -> None:
        self._threads: dict[str, ThreadIdentity] = {}
        self._capabilities: dict[str, CapabilityGrant] = {}
        self._revoked_capabilities: set[str] = set()
        self._decisions: dict[str, DecisionReceipt] = {}
        self._events: dict[str, CrossThreadEvent] = {}
        self._state: dict[tuple[str, str], AcceptedState] = {}
        self._audit: list[dict[str, Any]] = []

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        return hashlib.sha256(CrossThreadEvent._canonical(value)).hexdigest()

    def _append_audit(self, event_type: str, payload: Mapping[str, Any]) -> None:
        previous_hash = self._audit[-1]["record_hash"] if self._audit else "GENESIS"
        unsigned = {
            "offset": len(self._audit) + 1,
            "event_type": event_type,
            "payload": dict(payload),
            "previous_hash": previous_hash,
        }
        self._audit.append({**unsigned, "record_hash": self._digest(unsigned)})

    def register_thread(
        self,
        *,
        thread_id: str,
        agent_id: str,
        role: str,
        accepts_messages: bool = True,
    ) -> ThreadIdentity:
        identity = ThreadIdentity(
            thread_id=thread_id.strip(),
            agent_id=agent_id.strip(),
            role=role.strip(),
            accepts_messages=accepts_messages,
        )
        if not identity.thread_id or not identity.agent_id or not identity.role:
            raise CrossThreadViolation("thread identity fields must not be empty")
        if identity.thread_id in self._threads:
            raise CrossThreadViolation("thread is already registered")
        self._threads[identity.thread_id] = identity
        self._append_audit("THREAD_REGISTERED", asdict(identity))
        return identity

    def set_target_consent(self, thread_id: str, accepts_messages: bool) -> None:
        current = self._threads.get(thread_id)
        if current is None:
            raise CrossThreadViolation("thread is not registered")
        updated = ThreadIdentity(
            thread_id=current.thread_id,
            agent_id=current.agent_id,
            role=current.role,
            accepts_messages=accepts_messages,
            archived=current.archived,
        )
        self._threads[thread_id] = updated
        self._append_audit("THREAD_CONSENT_UPDATED", asdict(updated))

    def archive_thread(self, thread_id: str) -> None:
        current = self._threads.get(thread_id)
        if current is None:
            raise CrossThreadViolation("thread is not registered")
        updated = ThreadIdentity(
            thread_id=current.thread_id,
            agent_id=current.agent_id,
            role=current.role,
            accepts_messages=False,
            archived=True,
        )
        self._threads[thread_id] = updated
        self._append_audit("THREAD_ARCHIVED", asdict(updated))

    def resume_thread(self, thread_id: str) -> ThreadIdentity:
        current = self._threads.get(thread_id)
        if current is None:
            raise CrossThreadViolation("thread is not registered")
        if not current.archived:
            raise CrossThreadViolation("thread is not archived")
        updated = ThreadIdentity(
            thread_id=current.thread_id,
            agent_id=current.agent_id,
            role=current.role,
            accepts_messages=True,
            archived=False,
        )
        self._threads[thread_id] = updated
        self._append_audit("THREAD_RESUMED", asdict(updated))
        return updated

    def grant_capability(self, grant: CapabilityGrant) -> CapabilityGrant:
        if grant.source_thread_id not in self._threads:
            raise CrossThreadViolation("source thread is not registered")
        if grant.target_thread_id not in self._threads:
            raise CrossThreadViolation("target thread is not registered")
        self._capabilities[grant.capability_id] = grant
        self._append_audit("CAPABILITY_GRANTED", asdict(grant))
        return grant

    def revoke_capability(self, capability_id: str) -> None:
        if capability_id not in self._capabilities:
            raise CrossThreadViolation("capability does not exist")
        self._revoked_capabilities.add(capability_id)
        self._append_audit(
            "CAPABILITY_REVOKED", {"capability_id": capability_id}
        )

    def _matching_capability(self, event: CrossThreadEvent) -> CapabilityGrant | None:
        for grant in self._capabilities.values():
            if (
                grant.source_thread_id == event.source_thread_id
                and grant.target_thread_id == event.target_thread_id
                and grant.capability_id not in self._revoked_capabilities
            ):
                return grant
        return None

    @staticmethod
    def _is_expired(grant: CapabilityGrant, now: datetime) -> bool:
        if grant.expires_at is None:
            return False
        expiry = datetime.fromisoformat(grant.expires_at.replace("Z", "+00:00"))
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry <= now

    def _record_decision(
        self,
        *,
        event: CrossThreadEvent,
        status: DispositionStatus,
        reason: str,
        evidence_verdicts: Sequence[EvidenceVerdict] = (),
        accepted_state_version: int | None = None,
    ) -> DecisionReceipt:
        payload = {
            "event_id": event.event_id,
            "target_thread_id": event.target_thread_id,
            "status": status.value,
            "reason": reason,
            "evidence_verdicts": [asdict(item) for item in evidence_verdicts],
            "accepted_state_version": accepted_state_version,
            "recorded_at": self._now(),
        }
        receipt = DecisionReceipt(
            decision_id=self._digest(payload),
            event_id=event.event_id,
            target_thread_id=event.target_thread_id,
            status=status,
            reason=reason,
            evidence_verdicts=tuple(evidence_verdicts),
            accepted_state_version=accepted_state_version,
            recorded_at=payload["recorded_at"],
        )
        self._events[event.event_id] = event
        self._decisions[event.event_id] = receipt
        self._append_audit(
            "CROSS_THREAD_EVENT_DISPOSITION",
            {
                "source_thread_id": event.source_thread_id,
                "target_thread_id": event.target_thread_id,
                "event": event.to_dict(),
                "decision": asdict(receipt),
            },
        )
        return receipt

    def receive(
        self,
        event: CrossThreadEvent,
        *,
        evidence_checker: EvidenceChecker | None = None,
        now: datetime | None = None,
    ) -> DecisionReceipt:
        existing = self._decisions.get(event.event_id)
        if existing is not None:
            return existing

        current_time = now or datetime.now(timezone.utc)
        source = self._threads.get(event.source_thread_id)
        target = self._threads.get(event.target_thread_id)
        if source is None or target is None:
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="source or target thread is not registered",
            )
        if source.archived or target.archived:
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="archived threads cannot send or accept events",
            )
        if source.agent_id != event.source_agent_id or source.role != event.source_role:
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="event source identity does not match registered thread",
            )

        capability = self._matching_capability(event)
        if capability is None:
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="no active capability for this source-target pair",
            )
        if self._is_expired(capability, current_time):
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="capability has expired",
            )
        if event.event_type not in capability.allowed_event_types:
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="event type is outside the granted capability",
            )
        if capability.requires_target_consent and not target.accepts_messages:
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="target thread has not consented to cross-thread messages",
            )
        if not event.authority.is_subset_of(capability.max_authority):
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="event authority exceeds the capability grant",
            )
        if event.event_type == EventType.ACTION_REQUEST and not event.authority.may_request_action:
            return self._record_decision(
                event=event,
                status=DispositionStatus.REJECTED,
                reason="action request lacks may_request_action authority",
            )

        verdicts: tuple[EvidenceVerdict, ...] = ()
        requires_verified = event.event_type in self.EVIDENCE_REQUIRED_TYPES
        if requires_verified and event.verification_status != VerificationStatus.VERIFIED:
            return self._record_decision(
                event=event,
                status=DispositionStatus.DEFERRED,
                reason="state-bearing event is not marked VERIFIED",
            )
        if event.verification_status == VerificationStatus.VERIFIED:
            if not event.evidence_refs:
                return self._record_decision(
                    event=event,
                    status=DispositionStatus.REJECTED,
                    reason="VERIFIED event has no evidence references",
                )
            if evidence_checker is None:
                return self._record_decision(
                    event=event,
                    status=DispositionStatus.DEFERRED,
                    reason="verification claimed but no evidence checker was provided",
                )
            verdicts = tuple(evidence_checker(item) for item in event.evidence_refs)
            if not all(item.verified for item in verdicts):
                return self._record_decision(
                    event=event,
                    status=DispositionStatus.REJECTED,
                    reason="one or more evidence references failed verification",
                    evidence_verdicts=verdicts,
                )

        state_key = (event.trajectory_id, event.subject)
        previous = self._state.get(state_key)
        if previous is not None:
            if event.sequence <= previous.sequence:
                return self._record_decision(
                    event=event,
                    status=DispositionStatus.REJECTED,
                    reason="stale event cannot overwrite newer accepted state",
                    evidence_verdicts=verdicts,
                    accepted_state_version=previous.sequence,
                )
            if (
                event.supersedes_event_id is not None
                and event.supersedes_event_id != previous.event_id
            ):
                return self._record_decision(
                    event=event,
                    status=DispositionStatus.REJECTED,
                    reason="supersedes_event_id does not match current accepted state",
                    evidence_verdicts=verdicts,
                    accepted_state_version=previous.sequence,
                )

        if event.event_type in self.EVIDENCE_REQUIRED_TYPES:
            accepted = AcceptedState(
                trajectory_id=event.trajectory_id,
                subject=event.subject,
                event_id=event.event_id,
                sequence=event.sequence,
                payload=dict(event.payload),
                source_thread_id=event.source_thread_id,
                accepted_at=self._now(),
            )
            self._state[state_key] = accepted

        reason = "event accepted as advisory input"
        if event.event_type == EventType.ACTION_REQUEST:
            reason = "action request accepted for local policy evaluation; no execution occurred"
        elif event.event_type in self.EVIDENCE_REQUIRED_TYPES:
            reason = "verified state accepted"

        return self._record_decision(
            event=event,
            status=DispositionStatus.ACCEPTED,
            reason=reason,
            evidence_verdicts=verdicts,
            accepted_state_version=(
                event.sequence if event.event_type in self.EVIDENCE_REQUIRED_TYPES else None
            ),
        )

    def read_thread_audit(
        self,
        *,
        requester_thread_id: str,
        target_thread_id: str,
    ) -> tuple[dict[str, Any], ...]:
        if requester_thread_id == target_thread_id:
            return self._audit_for_thread(target_thread_id)
        allowed = any(
            grant.source_thread_id == requester_thread_id
            and grant.target_thread_id == target_thread_id
            and grant.allow_read
            and grant.capability_id not in self._revoked_capabilities
            for grant in self._capabilities.values()
        )
        if not allowed:
            raise CrossThreadViolation("requester lacks read capability for target thread")
        return self._audit_for_thread(target_thread_id)

    def _audit_for_thread(self, thread_id: str) -> tuple[dict[str, Any], ...]:
        visible: list[dict[str, Any]] = []
        for record in self._audit:
            payload = record.get("payload", {})
            serialized = json.dumps(payload, sort_keys=True, default=str)
            if thread_id in serialized:
                visible.append(json.loads(json.dumps(record, default=str)))
        return tuple(visible)

    def accepted_state(
        self,
        *,
        trajectory_id: str,
        subject: str,
    ) -> AcceptedState | None:
        return self._state.get((trajectory_id, subject))

    @property
    def decisions(self) -> tuple[DecisionReceipt, ...]:
        return tuple(self._decisions.values())

    @property
    def audit_records(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(json.dumps(item, default=str)) for item in self._audit)

    @classmethod
    def verify_records(cls, records: Sequence[Mapping[str, Any]]) -> bool:
        previous_hash = "GENESIS"
        for offset, record in enumerate(records, start=1):
            unsigned = {
                "offset": record.get("offset"),
                "event_type": record.get("event_type"),
                "payload": record.get("payload"),
                "previous_hash": record.get("previous_hash"),
            }
            if unsigned["offset"] != offset:
                return False
            if unsigned["previous_hash"] != previous_hash:
                return False
            if record.get("record_hash") != cls._digest(unsigned):
                return False
            previous_hash = str(record["record_hash"])
        return True

    def verify_audit(self) -> bool:
        return self.verify_records(self._audit)
