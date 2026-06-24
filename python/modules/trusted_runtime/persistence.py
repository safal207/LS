from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence

from .contracts import CognitiveTrail, ReusableArtifact, TrailEvent


DURABLE_EVENT_VERSION = "trusted_runtime.durable_event.v0.1"
GENESIS_HASH = "0" * 64


class EventStoreError(RuntimeError):
    """Base error for Trusted Runtime event persistence."""


class EventStoreCorruptionError(EventStoreError):
    """Raised when an append-only event stream fails integrity validation."""

    def __init__(self, message: str, findings: Sequence["StoreFinding"]) -> None:
        super().__init__(message)
        self.findings = tuple(findings)


class EventStoreConflictError(EventStoreError):
    """Raised when a stable event identifier is rebound to different content."""


class EventStoreDisabledError(EventStoreError):
    """Raised when an optional persistence adapter is disabled."""


class EventStoreUnavailableError(EventStoreError):
    """Raised when an optional persistence backend is unavailable."""


@dataclass(frozen=True)
class RedactionPolicy:
    sensitive_keys: tuple[str, ...] = (
        "access_token",
        "authorization",
        "cookie",
        "credential",
        "credentials",
        "password",
        "payment_data",
        "private_key",
        "prompt",
        "raw_model_output",
        "raw_output",
        "secret",
        "token",
    )
    replacement: str = "[REDACTED]"

    def __post_init__(self) -> None:
        if not self.sensitive_keys:
            raise ValueError("redaction policy requires sensitive keys")
        if not self.replacement:
            raise ValueError("redaction replacement must not be empty")

    def redact(self, value: Any) -> tuple[Any, tuple[str, ...]]:
        redacted_paths: list[str] = []
        sensitive = {key.lower() for key in self.sensitive_keys}

        def visit(item: Any, path: str) -> Any:
            if isinstance(item, Mapping):
                result: dict[str, Any] = {}
                for key, child in item.items():
                    key_text = str(key)
                    child_path = f"{path}.{key_text}" if path else key_text
                    if key_text.lower() in sensitive:
                        redacted_paths.append(child_path)
                        result[key_text] = {
                            "$redacted": self.replacement,
                            "digest": digest_json(child),
                        }
                    else:
                        result[key_text] = visit(child, child_path)
                return result
            if isinstance(item, tuple):
                return [visit(child, f"{path}[{index}]") for index, child in enumerate(item)]
            if isinstance(item, list):
                return [visit(child, f"{path}[{index}]") for index, child in enumerate(item)]
            return item

        return visit(value, ""), tuple(redacted_paths)


@dataclass(frozen=True)
class StoreFinding:
    code: str
    message: str
    line_number: Optional[int] = None
    event_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.code or not self.message:
            raise ValueError("store finding code and message must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "line_number": self.line_number,
            "event_ref": self.event_ref,
        }


@dataclass(frozen=True)
class DurableEvent:
    event_id: str
    task_id: str
    trail_id: str
    sequence: int
    event_type: str
    actor: str
    created_at: str
    parent_event_id: str
    payload_digest: str
    payload: Mapping[str, Any]
    redacted_fields: tuple[str, ...]
    previous_hash: str
    event_hash: str
    event_ref: str
    schema_version: str = DURABLE_EVENT_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != DURABLE_EVENT_VERSION:
            raise ValueError(f"unsupported durable event version: {self.schema_version}")
        required = (
            self.event_id,
            self.task_id,
            self.trail_id,
            self.event_type,
            self.actor,
            self.created_at,
            self.parent_event_id,
            self.payload_digest,
            self.previous_hash,
            self.event_hash,
            self.event_ref,
        )
        if not all(required):
            raise ValueError("durable event fields must not be empty")
        if self.sequence < 0:
            raise ValueError("durable event sequence must be non-negative")
        if len(self.payload_digest) != 64:
            raise ValueError("payload_digest must be a SHA-256 hex digest")
        if len(self.previous_hash) != 64 or len(self.event_hash) != 64:
            raise ValueError("event hashes must be SHA-256 hex digests")
        expected_ref = f"liminal-event:sha256:{self.event_hash}"
        if self.event_ref != expected_ref:
            raise ValueError("event_ref does not match event_hash")

    @classmethod
    def build(
        cls,
        event: Mapping[str, Any],
        *,
        sequence: int,
        previous_hash: str,
        redaction_policy: Optional[RedactionPolicy] = None,
    ) -> "DurableEvent":
        policy = redaction_policy or RedactionPolicy()
        normalized = normalize_event_mapping(event)
        original_digest = digest_json(normalized)
        redacted_payload, redacted_fields = policy.redact(normalized)
        unsigned = {
            "schema_version": DURABLE_EVENT_VERSION,
            "event_id": normalized["event_id"],
            "task_id": normalized["task_id"],
            "trail_id": normalized["trail_id"],
            "sequence": sequence,
            "event_type": normalized["event_type"],
            "actor": normalized["actor"],
            "created_at": normalized["created_at"],
            "parent_event_id": normalized["parent_cause"],
            "payload_digest": original_digest,
            "payload": redacted_payload,
            "redacted_fields": list(redacted_fields),
            "previous_hash": previous_hash,
        }
        event_hash = digest_json(unsigned)
        return cls(
            event_id=normalized["event_id"],
            task_id=normalized["task_id"],
            trail_id=normalized["trail_id"],
            sequence=sequence,
            event_type=normalized["event_type"],
            actor=normalized["actor"],
            created_at=normalized["created_at"],
            parent_event_id=normalized["parent_cause"],
            payload_digest=original_digest,
            payload=redacted_payload,
            redacted_fields=redacted_fields,
            previous_hash=previous_hash,
            event_hash=event_hash,
            event_ref=f"liminal-event:sha256:{event_hash}",
        )

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "DurableEvent":
        return cls(
            event_id=str(payload["event_id"]),
            task_id=str(payload["task_id"]),
            trail_id=str(payload["trail_id"]),
            sequence=int(payload["sequence"]),
            event_type=str(payload["event_type"]),
            actor=str(payload["actor"]),
            created_at=str(payload["created_at"]),
            parent_event_id=str(payload["parent_event_id"]),
            payload_digest=str(payload["payload_digest"]),
            payload=dict(payload["payload"]),
            redacted_fields=tuple(str(item) for item in payload.get("redacted_fields", ())),
            previous_hash=str(payload["previous_hash"]),
            event_hash=str(payload["event_hash"]),
            event_ref=str(payload["event_ref"]),
            schema_version=str(payload.get("schema_version", DURABLE_EVENT_VERSION)),
        )

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "sequence": self.sequence,
            "event_type": self.event_type,
            "actor": self.actor,
            "created_at": self.created_at,
            "parent_event_id": self.parent_event_id,
            "payload_digest": self.payload_digest,
            "payload": dict(self.payload),
            "redacted_fields": list(self.redacted_fields),
            "previous_hash": self.previous_hash,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.unsigned_dict(),
            "event_hash": self.event_hash,
            "event_ref": self.event_ref,
        }

    def verify_hash(self) -> bool:
        return digest_json(self.unsigned_dict()) == self.event_hash


@dataclass(frozen=True)
class EventStoreScan:
    trail_id: str
    events: tuple[DurableEvent, ...]
    findings: tuple[StoreFinding, ...]
    stopped_at_line: Optional[int]

    @property
    def is_valid(self) -> bool:
        return not self.findings

    @property
    def last_valid_event(self) -> Optional[DurableEvent]:
        return self.events[-1] if self.events else None

    def require_valid(self) -> tuple[DurableEvent, ...]:
        if self.findings:
            raise EventStoreCorruptionError(
                f"event stream {self.trail_id!r} failed integrity validation",
                self.findings,
            )
        return self.events


class InMemoryEventStoreAdapter:
    """Append-only per-trail hash chain used by deterministic tests."""

    def __init__(self, redaction_policy: Optional[RedactionPolicy] = None) -> None:
        self.redaction_policy = redaction_policy or RedactionPolicy()
        self._events: MutableMapping[str, list[DurableEvent]] = {}
        self._lock = threading.RLock()

    @property
    def adapter_name(self) -> str:
        return "memory-jsonl"

    def append(self, event: Mapping[str, Any]) -> str:
        normalized = normalize_event_mapping(event)
        trail_id = normalized["trail_id"]
        with self._lock:
            stream = self._events.setdefault(trail_id, [])
            duplicate = _find_event(stream, normalized["event_id"])
            if duplicate is not None:
                if duplicate.payload_digest != digest_json(normalized):
                    raise EventStoreConflictError(
                        f"event {normalized['event_id']!r} already exists with different content"
                    )
                return duplicate.event_ref
            durable = DurableEvent.build(
                normalized,
                sequence=len(stream),
                previous_hash=stream[-1].event_hash if stream else GENESIS_HASH,
                redaction_policy=self.redaction_policy,
            )
            _validate_parent(durable, stream)
            stream.append(durable)
            return durable.event_ref

    def read(self, trail_id: str) -> Sequence[Mapping[str, Any]]:
        return tuple(event.to_dict() for event in self.read_events(trail_id))

    def read_events(self, trail_id: str) -> tuple[DurableEvent, ...]:
        with self._lock:
            events = tuple(self._events.get(trail_id, ()))
        findings = validate_event_chain(trail_id, events)
        if findings:
            raise EventStoreCorruptionError(
                f"event stream {trail_id!r} failed integrity validation",
                findings,
            )
        return events

    def scan(self, trail_id: str) -> EventStoreScan:
        with self._lock:
            events = tuple(self._events.get(trail_id, ()))
        findings = validate_event_chain(trail_id, events)
        valid_count = _valid_prefix_length(events, findings)
        return EventStoreScan(
            trail_id=trail_id,
            events=events[:valid_count],
            findings=findings,
            stopped_at_line=None,
        )

    def export_trace(self, trail_id: str) -> str:
        return events_to_jsonl(self.read_events(trail_id))


class JsonlEventStoreAdapter:
    """Local append-only JSONL event store with fsync and per-trail hash chains."""

    def __init__(
        self,
        path: Path,
        redaction_policy: Optional[RedactionPolicy] = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.redaction_policy = redaction_policy or RedactionPolicy()
        self._lock = threading.RLock()

    @property
    def adapter_name(self) -> str:
        return "local-jsonl"

    def append(self, event: Mapping[str, Any]) -> str:
        normalized = normalize_event_mapping(event)
        trail_id = normalized["trail_id"]
        with self._lock:
            events = self.read_events(trail_id)
            duplicate = _find_event(events, normalized["event_id"])
            if duplicate is not None:
                if duplicate.payload_digest != digest_json(normalized):
                    raise EventStoreConflictError(
                        f"event {normalized['event_id']!r} already exists with different content"
                    )
                return duplicate.event_ref
            durable = DurableEvent.build(
                normalized,
                sequence=len(events),
                previous_hash=events[-1].event_hash if events else GENESIS_HASH,
                redaction_policy=self.redaction_policy,
            )
            _validate_parent(durable, events)
            line = canonical_json(durable.to_dict()) + "\n"
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
            return durable.event_ref

    def read(self, trail_id: str) -> Sequence[Mapping[str, Any]]:
        return tuple(event.to_dict() for event in self.read_events(trail_id))

    def read_events(self, trail_id: str) -> tuple[DurableEvent, ...]:
        return self.scan(trail_id).require_valid()

    def scan(self, trail_id: str) -> EventStoreScan:
        if not self.path.exists():
            return EventStoreScan(trail_id, (), (), None)
        events: list[DurableEvent] = []
        findings: list[StoreFinding] = []
        stopped_at: Optional[int] = None
        expected_sequence = 0
        previous_hash = GENESIS_HASH
        known_causes: set[str] = set()
        task_id: Optional[str] = None

        with self.path.open("r", encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as error:
                    findings.append(
                        StoreFinding(
                            "CORRUPTED_JSON",
                            f"line is not valid JSON: {error.msg}",
                            line_number=line_number,
                        )
                    )
                    stopped_at = line_number
                    break
                if payload.get("trail_id") != trail_id:
                    continue
                try:
                    event = DurableEvent.from_mapping(payload)
                except Exception as error:
                    findings.append(
                        StoreFinding(
                            "INVALID_EVENT",
                            str(error),
                            line_number=line_number,
                        )
                    )
                    stopped_at = line_number
                    break
                event_findings = _validate_event(
                    event,
                    expected_sequence=expected_sequence,
                    previous_hash=previous_hash,
                    known_causes=known_causes,
                    expected_task_id=task_id,
                    line_number=line_number,
                )
                if event_findings:
                    findings.extend(event_findings)
                    stopped_at = line_number
                    break
                events.append(event)
                expected_sequence += 1
                previous_hash = event.event_hash
                task_id = task_id or event.task_id
                known_causes.add(event.event_id)

        return EventStoreScan(
            trail_id=trail_id,
            events=tuple(events),
            findings=tuple(findings),
            stopped_at_line=stopped_at,
        )

    def export_trace(self, trail_id: str) -> str:
        return events_to_jsonl(self.read_events(trail_id))


@dataclass(frozen=True)
class LiminalDBConfig:
    enabled: bool = False


class LiminalDBEventStoreAdapter:
    """Feature-flagged port for a LiminalDB append-only event client."""

    def __init__(self, config: Optional[LiminalDBConfig] = None, client: Any = None) -> None:
        self.config = config or LiminalDBConfig()
        self.client = client

    @property
    def adapter_name(self) -> str:
        return "liminaldb"

    def append(self, event: Mapping[str, Any]) -> str:
        self._require_client()
        result = self.client.append_event(dict(event))
        if not isinstance(result, str) or not result:
            raise EventStoreUnavailableError("LiminalDB client returned an invalid event reference")
        return result

    def read(self, trail_id: str) -> Sequence[Mapping[str, Any]]:
        self._require_client()
        payloads = self.client.read_events(trail_id)
        events = tuple(DurableEvent.from_mapping(item) for item in payloads)
        findings = validate_event_chain(trail_id, events)
        if findings:
            raise EventStoreCorruptionError(
                f"LiminalDB stream {trail_id!r} failed integrity validation",
                findings,
            )
        return tuple(event.to_dict() for event in events)

    def _require_client(self) -> None:
        if not self.config.enabled:
            raise EventStoreDisabledError("LiminalDB event-store adapter is disabled")
        if self.client is None:
            raise EventStoreUnavailableError("LiminalDB event-store client is unavailable")


def persist_cognitive_trail(
    store: Any,
    trail: CognitiveTrail,
) -> tuple[str, ...]:
    references: list[str] = []
    for event in trail.events:
        references.append(store.append(trail_event_to_mapping(event)))
    return tuple(references)


def persist_artifact_metadata(
    store: Any,
    artifact: ReusableArtifact,
    *,
    actor: str,
    parent_event_id: str,
) -> str:
    event = {
        "event_id": f"event-artifact-{artifact.artifact_id}",
        "task_id": artifact.task_id,
        "trail_id": artifact.trail_id,
        "event_type": "ARTIFACT_CREATED",
        "actor": actor,
        "created_at": artifact.created_at,
        "parent_cause": parent_event_id,
        "evidence_refs": list(artifact.evidence_refs),
        "payload": artifact.to_dict(),
    }
    return store.append(event)


def trail_event_to_mapping(event: TrailEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "task_id": event.task_id,
        "trail_id": event.trail_id,
        "event_type": event.event_type.value,
        "actor": event.actor,
        "created_at": event.created_at,
        "parent_cause": event.parent_cause,
        "evidence_refs": list(event.evidence_refs),
        "payload": dict(event.payload),
    }


def normalize_event_mapping(event: Mapping[str, Any]) -> dict[str, Any]:
    required = (
        "event_id",
        "task_id",
        "trail_id",
        "event_type",
        "actor",
        "created_at",
        "parent_cause",
    )
    missing = [key for key in required if not event.get(key)]
    if missing:
        raise ValueError(f"event is missing required fields: {', '.join(missing)}")
    return {
        "event_id": str(event["event_id"]),
        "task_id": str(event["task_id"]),
        "trail_id": str(event["trail_id"]),
        "event_type": str(event["event_type"]),
        "actor": str(event["actor"]),
        "created_at": str(event["created_at"]),
        "parent_cause": str(event["parent_cause"]),
        "evidence_refs": [str(item) for item in event.get("evidence_refs", ())],
        "payload": _json_primitive(event.get("payload", {})),
    }


def validate_event_chain(
    trail_id: str,
    events: Sequence[DurableEvent],
) -> tuple[StoreFinding, ...]:
    findings: list[StoreFinding] = []
    previous_hash = GENESIS_HASH
    known_causes: set[str] = set()
    task_id: Optional[str] = None
    for index, event in enumerate(events):
        findings.extend(
            _validate_event(
                event,
                expected_sequence=index,
                previous_hash=previous_hash,
                known_causes=known_causes,
                expected_task_id=task_id,
                line_number=None,
            )
        )
        if findings:
            break
        previous_hash = event.event_hash
        task_id = task_id or event.task_id
        known_causes.add(event.event_id)
    return tuple(findings)


def events_to_jsonl(events: Iterable[DurableEvent]) -> str:
    lines = [canonical_json(event.to_dict()) for event in events]
    return "\n".join(lines) + ("\n" if lines else "")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _json_primitive(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_primitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_primitive(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [_json_primitive(child) for child in value]
    if isinstance(value, list):
        return [_json_primitive(child) for child in value]
    return value


def _validate_event(
    event: DurableEvent,
    *,
    expected_sequence: int,
    previous_hash: str,
    known_causes: set[str],
    expected_task_id: Optional[str],
    line_number: Optional[int],
) -> tuple[StoreFinding, ...]:
    findings: list[StoreFinding] = []
    if event.sequence != expected_sequence:
        findings.append(
            StoreFinding(
                "REORDERED_EVENT",
                f"expected sequence {expected_sequence}, got {event.sequence}",
                line_number,
                event.event_ref,
            )
        )
    if event.previous_hash != previous_hash:
        findings.append(
            StoreFinding(
                "BROKEN_HASH_CHAIN",
                "previous_hash does not match the prior durable event",
                line_number,
                event.event_ref,
            )
        )
    if not event.verify_hash():
        findings.append(
            StoreFinding(
                "EVENT_HASH_MISMATCH",
                "event_hash does not match the serialized durable event",
                line_number,
                event.event_ref,
            )
        )
    if expected_task_id is not None and event.task_id != expected_task_id:
        findings.append(
            StoreFinding(
                "TASK_MISMATCH",
                "event belongs to another task",
                line_number,
                event.event_ref,
            )
        )
    if event.sequence == 0:
        if event.parent_event_id != event.task_id:
            findings.append(
                StoreFinding(
                    "INVALID_ROOT_PARENT",
                    "first durable event must descend from the task identifier",
                    line_number,
                    event.event_ref,
                )
            )
    elif event.parent_event_id not in known_causes:
        findings.append(
            StoreFinding(
                "MISSING_PARENT",
                f"parent event {event.parent_event_id!r} is not in the durable prefix",
                line_number,
                event.event_ref,
            )
        )
    return tuple(findings)


def _validate_parent(event: DurableEvent, existing: Sequence[DurableEvent]) -> None:
    known = {item.event_id for item in existing}
    if event.sequence == 0 and event.parent_event_id != event.task_id:
        raise EventStoreConflictError("first event must descend from the task identifier")
    if event.sequence > 0 and event.parent_event_id not in known:
        raise EventStoreConflictError(
            f"parent event {event.parent_event_id!r} is not durable"
        )


def _find_event(
    events: Sequence[DurableEvent],
    event_id: str,
) -> Optional[DurableEvent]:
    return next((event for event in events if event.event_id == event_id), None)


def _valid_prefix_length(
    events: Sequence[DurableEvent],
    findings: Sequence[StoreFinding],
) -> int:
    if not findings:
        return len(events)
    finding = findings[0]
    if finding.event_ref is None:
        return 0
    for index, event in enumerate(events):
        if event.event_ref == finding.event_ref:
            return index
    return 0
