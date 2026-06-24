"""Durable commit hook and restart-safe trigger for identity catalog publication."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .identity_catalog_publisher import CatalogPublishResult, publish_identity_catalog
from .identity_timeline import replay_identity_timeline
from .persistence import JsonlEventStoreAdapter, digest_json


TIMELINE_COMMIT_RECEIPT_VERSION = (
    "trusted_runtime.identity_timeline_commit_receipt.v0.1"
)
TRIGGER_STATE_VERSION = "trusted_runtime.identity_catalog_trigger_state.v0.1"
TRIGGER_BATCH_VERSION = "trusted_runtime.identity_catalog_trigger_batch.v0.1"
TRIGGER_HEALTH_VERSION = "trusted_runtime.identity_catalog_trigger_health.v0.1"
OUTBOX_TASK_ID = "identity-catalog-publication-outbox"
OUTBOX_TRAIL_ID = "identity-catalog-publication-outbox"
OUTBOX_EVENT_TYPE = "IDENTITY_TIMELINE_COMMIT_READY"


class IdentityCatalogTriggerError(RuntimeError):
    """Base error for durable publication triggering."""


class IdentityTimelineCommitInvalidError(IdentityCatalogTriggerError):
    """Raised when a timeline cannot produce a valid commit receipt."""


@dataclass(frozen=True)
class IdentityTimelineCommitReceipt:
    request_id: str
    agent_id: str
    bundle_path: str
    task_id: str
    trail_id: str
    tail_event_ref: str
    event_count: int
    timeline_digest: str
    committed_at: str
    schema_version: str = TIMELINE_COMMIT_RECEIPT_VERSION

    def __post_init__(self) -> None:
        required = (
            self.request_id,
            self.agent_id,
            self.bundle_path,
            self.task_id,
            self.trail_id,
            self.tail_event_ref,
            self.timeline_digest,
            self.committed_at,
        )
        if not all(required):
            raise ValueError("timeline commit receipt fields must not be empty")
        path = Path(self.bundle_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("timeline commit bundle path must be safe and relative")
        if self.event_count < 1:
            raise ValueError("timeline commit receipt requires durable events")
        if len(self.timeline_digest) != 64:
            raise ValueError("timeline digest must be a SHA-256 hex digest")
        if self.request_id != self.expected_request_id():
            raise ValueError("timeline commit request ID does not match receipt content")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "agent_id": self.agent_id,
            "bundle_path": self.bundle_path,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "tail_event_ref": self.tail_event_ref,
            "event_count": self.event_count,
            "timeline_digest": self.timeline_digest,
            "committed_at": self.committed_at,
        }

    def expected_request_id(self) -> str:
        return "identity-catalog-request:sha256:" + digest_json(
            self.unsigned_dict()
        )

    def to_dict(self) -> dict[str, Any]:
        return {"request_id": self.request_id, **self.unsigned_dict()}

    @classmethod
    def build(
        cls,
        *,
        agent_id: str,
        bundle_path: str,
        task_id: str,
        trail_id: str,
        tail_event_ref: str,
        event_count: int,
        timeline_digest: str,
        committed_at: str,
    ) -> "IdentityTimelineCommitReceipt":
        unsigned = {
            "schema_version": TIMELINE_COMMIT_RECEIPT_VERSION,
            "agent_id": agent_id,
            "bundle_path": bundle_path,
            "task_id": task_id,
            "trail_id": trail_id,
            "tail_event_ref": tail_event_ref,
            "event_count": event_count,
            "timeline_digest": timeline_digest,
            "committed_at": committed_at,
        }
        return cls(
            request_id="identity-catalog-request:sha256:" + digest_json(unsigned),
            agent_id=agent_id,
            bundle_path=bundle_path,
            task_id=task_id,
            trail_id=trail_id,
            tail_event_ref=tail_event_ref,
            event_count=event_count,
            timeline_digest=timeline_digest,
            committed_at=committed_at,
        )

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, Any],
    ) -> "IdentityTimelineCommitReceipt":
        return cls(
            request_id=str(payload["request_id"]),
            agent_id=str(payload["agent_id"]),
            bundle_path=str(payload["bundle_path"]),
            task_id=str(payload["task_id"]),
            trail_id=str(payload["trail_id"]),
            tail_event_ref=str(payload["tail_event_ref"]),
            event_count=int(payload["event_count"]),
            timeline_digest=str(payload["timeline_digest"]),
            committed_at=str(payload["committed_at"]),
            schema_version=str(
                payload.get("schema_version", TIMELINE_COMMIT_RECEIPT_VERSION)
            ),
        )


@dataclass(frozen=True)
class IdentityCatalogTriggerState:
    processed_request_ids: tuple[str, ...]
    last_generation: Optional[int]
    last_publication_digest: Optional[str]
    last_successful_at: Optional[str]
    schema_version: str = TRIGGER_STATE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "processed_request_ids": list(self.processed_request_ids),
            "last_generation": self.last_generation,
            "last_publication_digest": self.last_publication_digest,
            "last_successful_at": self.last_successful_at,
        }


@dataclass(frozen=True)
class IdentityCatalogTriggerResult:
    publication: Optional[CatalogPublishResult]
    processed_request_ids: tuple[str, ...]
    pending_request_ids: tuple[str, ...]
    quarantined: tuple[Mapping[str, Any], ...]
    trigger_batch_path: Optional[Path]
    health_path: Path
    state_path: Path


def finalize_identity_timeline_commit(
    store: Any,
    *,
    agent_id: str,
    bundle_root: Path,
    data_root: Path,
    outbox_path: Path,
    committed_at: str,
) -> tuple[IdentityTimelineCommitReceipt, str]:
    """Write projection, commit marker, then the durable outbox request."""

    root = Path(data_root).resolve()
    bundle = Path(bundle_root).resolve()
    if root not in bundle.parents and bundle != root:
        raise IdentityTimelineCommitInvalidError("bundle escapes identity data root")
    projection = replay_identity_timeline(store, agent_id=agent_id).require_valid()
    payload = projection.to_dict()
    timeline_path = bundle / "identity-timeline.json"
    _atomic_write_json(timeline_path, payload)
    if _read_json_object(timeline_path) != payload:
        raise IdentityTimelineCommitInvalidError(
            "timeline projection write was not durable"
        )

    integrity = payload["integrity"]
    receipt = IdentityTimelineCommitReceipt.build(
        agent_id=agent_id,
        bundle_path=bundle.relative_to(root).as_posix() or ".",
        task_id=projection.task_id,
        trail_id=projection.trail_id,
        tail_event_ref=str(integrity["tail_event_ref"]),
        event_count=int(integrity["event_count"]),
        timeline_digest=str(integrity["timeline_digest"]),
        committed_at=committed_at,
    )
    findings = verify_timeline_commit_receipt(root, receipt)
    if findings:
        raise IdentityTimelineCommitInvalidError(
            "; ".join(str(item["message"]) for item in findings)
        )
    _atomic_write_json(
        bundle / "identity-timeline-commit.json",
        receipt.to_dict(),
    )
    return receipt, append_timeline_commit_request(outbox_path, receipt)


def append_timeline_commit_request(
    outbox_path: Path,
    receipt: IdentityTimelineCommitReceipt,
) -> str:
    store = JsonlEventStoreAdapter(outbox_path)
    existing = store.read_events(OUTBOX_TRAIL_ID)
    duplicate = next(
        (event for event in existing if event.event_id == receipt.request_id),
        None,
    )
    if duplicate is not None:
        return duplicate.event_ref
    parent = existing[-1].event_id if existing else OUTBOX_TASK_ID
    return store.append(
        {
            "event_id": receipt.request_id,
            "task_id": OUTBOX_TASK_ID,
            "trail_id": OUTBOX_TRAIL_ID,
            "event_type": OUTBOX_EVENT_TYPE,
            "actor": "runtime:identity-catalog-trigger",
            "created_at": receipt.committed_at,
            "parent_cause": parent,
            "evidence_refs": [receipt.tail_event_ref],
            "payload": {"receipt": receipt.to_dict()},
        }
    )


def reconcile_timeline_commit_receipts(
    data_root: Path,
    outbox_path: Path,
    *,
    reconciled_at: str,
) -> tuple[str, ...]:
    """Recover complete bundles that missed outbox delivery."""

    root = Path(data_root).resolve()
    refs = []
    for timeline_path in sorted(root.rglob("identity-timeline.json")):
        bundle = timeline_path.parent
        marker_path = bundle / "identity-timeline-commit.json"
        if marker_path.exists():
            receipt = IdentityTimelineCommitReceipt.from_mapping(
                _read_json_object(marker_path)
            )
        else:
            timeline = _read_json_object(timeline_path)
            integrity = timeline.get("integrity")
            if not isinstance(integrity, Mapping):
                continue
            receipt = IdentityTimelineCommitReceipt.build(
                agent_id=str(timeline.get("agent_id", "")),
                bundle_path=bundle.resolve().relative_to(root).as_posix() or ".",
                task_id=str(timeline.get("task_id", "")),
                trail_id=str(timeline.get("trail_id", "")),
                tail_event_ref=str(integrity.get("tail_event_ref", "")),
                event_count=int(integrity.get("event_count", 0)),
                timeline_digest=str(integrity.get("timeline_digest", "")),
                committed_at=reconciled_at,
            )
        if verify_timeline_commit_receipt(root, receipt):
            continue
        if not marker_path.exists():
            _atomic_write_json(marker_path, receipt.to_dict())
        refs.append(append_timeline_commit_request(outbox_path, receipt))
    return tuple(refs)


def verify_timeline_commit_receipt(
    data_root: Path,
    receipt: IdentityTimelineCommitReceipt,
) -> tuple[Mapping[str, Any], ...]:
    root = Path(data_root).resolve()
    bundle = (root / receipt.bundle_path).resolve()
    findings = []
    if root not in bundle.parents and bundle != root:
        return (_finding(receipt, "BUNDLE_PATH_ESCAPE", "bundle escapes data root"),)
    timeline_path = bundle / "identity-timeline.json"
    events_path = bundle / "identity-events.jsonl"
    if not timeline_path.exists():
        return (_finding(receipt, "TIMELINE_MISSING", "timeline is missing"),)
    try:
        timeline = _read_json_object(timeline_path)
    except Exception as error:
        return (_finding(receipt, "TIMELINE_INVALID", str(error)),)
    integrity = timeline.get("integrity")
    if not isinstance(integrity, Mapping):
        return (
            _finding(
                receipt,
                "TIMELINE_INTEGRITY_MISSING",
                "timeline integrity is missing",
            ),
        )
    checks = (
        (timeline.get("agent_id"), receipt.agent_id, "AGENT_ID_MISMATCH"),
        (timeline.get("task_id"), receipt.task_id, "TASK_ID_MISMATCH"),
        (timeline.get("trail_id"), receipt.trail_id, "TRAIL_ID_MISMATCH"),
        (
            integrity.get("tail_event_ref"),
            receipt.tail_event_ref,
            "TAIL_EVENT_REF_MISMATCH",
        ),
        (
            int(integrity.get("event_count", -1)),
            receipt.event_count,
            "EVENT_COUNT_MISMATCH",
        ),
        (
            integrity.get("timeline_digest"),
            receipt.timeline_digest,
            "TIMELINE_DIGEST_MISMATCH",
        ),
    )
    for actual, expected, code in checks:
        if actual != expected:
            findings.append(_finding(receipt, code, code.lower()))
    unsigned = dict(timeline)
    unsigned.pop("integrity", None)
    if integrity.get("timeline_digest") != digest_json(unsigned):
        findings.append(
            _finding(
                receipt,
                "TIMELINE_DIGEST_INVALID",
                "timeline digest is invalid",
            )
        )
    if not events_path.exists():
        findings.append(
            _finding(receipt, "EVENT_STORE_MISSING", "event store is missing")
        )
        return tuple(findings)
    scan = JsonlEventStoreAdapter(events_path).scan(receipt.trail_id)
    findings.extend(
        _finding(receipt, item.code, item.message) for item in scan.findings
    )
    if scan.events:
        if len(scan.events) != receipt.event_count:
            findings.append(
                _finding(
                    receipt,
                    "STORE_EVENT_COUNT_MISMATCH",
                    "event count differs from store",
                )
            )
        if scan.events[-1].event_ref != receipt.tail_event_ref:
            findings.append(
                _finding(
                    receipt,
                    "STORE_TAIL_REF_MISMATCH",
                    "tail ref differs from store",
                )
            )
    return tuple(findings)


def process_identity_catalog_triggers(
    data_root: Path,
    outbox_path: Path,
    publisher_output_root: Path,
    trigger_output_root: Path,
    *,
    keyring: Mapping[str, bytes],
    active_key_id: str,
    signing_key_ids: Sequence[str],
    audience: str,
    visibility_policy: Mapping[str, Sequence[str]],
    processed_at: str,
    stale_after_seconds: int,
) -> IdentityCatalogTriggerResult:
    """Coalesce valid unprocessed receipts into one catalog publication."""

    trigger_root = Path(trigger_output_root)
    trigger_root.mkdir(parents=True, exist_ok=True)
    state_path = trigger_root / "identity-catalog-trigger-state.json"
    health_path = trigger_root / "identity-catalog-trigger-health.json"
    state = _load_state(state_path)
    processed = set(state.processed_request_ids)

    outbox = JsonlEventStoreAdapter(outbox_path)
    scan = outbox.scan(OUTBOX_TRAIL_ID)
    if scan.findings:
        raise IdentityCatalogTriggerError("publication outbox hash chain is invalid")
    receipts, sequences = _receipts_from_events(scan.events)

    latest_by_agent = {}
    groups = {}
    for receipt in receipts:
        groups.setdefault(receipt.agent_id, []).append(receipt)
        latest_by_agent[receipt.agent_id] = receipt

    committed_latest = {}
    valid_unprocessed = []
    quarantined = []
    for agent_id, group in groups.items():
        latest = latest_by_agent[agent_id]
        findings = verify_timeline_commit_receipt(data_root, latest)
        unprocessed_group = [
            receipt for receipt in group if receipt.request_id not in processed
        ]
        if findings:
            if unprocessed_group:
                quarantined.append(
                    {
                        "request_ids": [item.request_id for item in unprocessed_group],
                        "agent_id": agent_id,
                        "latest_request_id": latest.request_id,
                        "findings": list(findings),
                    }
                )
            continue
        committed_latest[agent_id] = latest
        valid_unprocessed.extend(unprocessed_group)

    effective_visibility = _effective_visibility(
        Path(data_root),
        committed_latest,
        visibility_policy,
    )
    publication = None
    trigger_batch_path = None
    newly_processed = []
    if valid_unprocessed:
        publication = publish_identity_catalog(
            data_root,
            publisher_output_root,
            keyring=keyring,
            active_key_id=active_key_id,
            signing_key_ids=signing_key_ids,
            audience=audience,
            visibility_policy=effective_visibility,
            published_at=processed_at,
            stale_after_seconds=stale_after_seconds,
        )
        newly_processed = [item.request_id for item in valid_unprocessed]
        recovered_generation = (
            state.last_generation is None
            or state.last_generation < publication.publication.generation
        )
        if publication.changed or recovered_generation:
            trigger_batch_path = _write_trigger_batch(
                trigger_root,
                publication,
                valid_unprocessed,
                sequences,
                processed_at=processed_at,
            )
        processed.update(newly_processed)
        state = IdentityCatalogTriggerState(
            processed_request_ids=tuple(sorted(processed)),
            last_generation=publication.publication.generation,
            last_publication_digest=publication.publication.publication_digest,
            last_successful_at=processed_at,
        )
        _atomic_write_json(state_path, state.to_dict())

    pending = tuple(
        receipt.request_id
        for receipt in receipts
        if receipt.request_id not in processed
    )
    health = {
        "schema_version": TRIGGER_HEALTH_VERSION,
        "updated_at": processed_at,
        "outbox_event_count": len(scan.events),
        "processed_request_count": len(processed),
        "pending_request_count": len(pending),
        "quarantined_request_count": len(quarantined),
        "pending_request_ids": list(pending),
        "quarantined": list(quarantined),
        "last_successful_generation": state.last_generation,
        "last_publication_digest": state.last_publication_digest,
        "publisher_lag_seconds": _publisher_lag_seconds(receipts, processed_at),
        "read_only": True,
    }
    _atomic_write_json(health_path, health)
    return IdentityCatalogTriggerResult(
        publication=publication,
        processed_request_ids=tuple(newly_processed),
        pending_request_ids=pending,
        quarantined=tuple(quarantined),
        trigger_batch_path=trigger_batch_path,
        health_path=health_path,
        state_path=state_path,
    )


def _receipts_from_events(events: Sequence[Any]) -> tuple[list[Any], dict[str, int]]:
    receipts = []
    sequences = {}
    for event in events:
        receipt_payload = event.payload.get("payload", {}).get("receipt")
        if not isinstance(receipt_payload, Mapping):
            continue
        receipt = IdentityTimelineCommitReceipt.from_mapping(receipt_payload)
        receipts.append(receipt)
        sequences[receipt.request_id] = event.sequence
    return receipts, sequences


def _write_trigger_batch(
    trigger_root: Path,
    result: CatalogPublishResult,
    receipts: Sequence[IdentityTimelineCommitReceipt],
    event_sequences: Mapping[str, int],
    *,
    processed_at: str,
) -> Path:
    publication = result.publication
    ordered = sorted(receipts, key=lambda item: event_sequences[item.request_id])
    payload = {
        "schema_version": TRIGGER_BATCH_VERSION,
        "generation": publication.generation,
        "publication_digest": publication.publication_digest,
        "processed_at": processed_at,
        "changed": result.changed,
        "request_ids": [item.request_id for item in ordered],
        "trigger_tail_event_refs": [item.tail_event_ref for item in ordered],
        "agent_ids": sorted({item.agent_id for item in ordered}),
        "outbox_sequences": [event_sequences[item.request_id] for item in ordered],
        "integrity": {},
    }
    unsigned = dict(payload)
    unsigned.pop("integrity")
    payload["integrity"] = {
        "algorithm": "sha256",
        "trigger_batch_digest": digest_json(unsigned),
    }
    history = trigger_root / "history"
    history.mkdir(parents=True, exist_ok=True)
    path = history / f"generation-{publication.generation:020d}-triggers.json"
    _atomic_write_json(path, payload)
    _atomic_write_json(
        trigger_root / "identity-catalog-trigger-generation.json",
        payload,
    )
    return path


def _effective_visibility(
    data_root: Path,
    latest_receipts: Mapping[str, IdentityTimelineCommitReceipt],
    configured: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    result = {}
    for timeline_path in Path(data_root).rglob("identity-timeline.json"):
        try:
            agent_id = str(_read_json_object(timeline_path).get("agent_id", ""))
        except Exception:
            continue
        if not agent_id:
            continue
        if agent_id in latest_receipts and agent_id in configured:
            result[agent_id] = tuple(str(value) for value in configured[agent_id])
        else:
            result[agent_id] = ("__not_committed_or_not_visible__",)
    return result


def _publisher_lag_seconds(
    receipts: Sequence[IdentityTimelineCommitReceipt],
    processed_at: str,
) -> float:
    if not receipts:
        return 0.0
    latest = max(_instant(receipt.committed_at) for receipt in receipts)
    return max(0.0, (_instant(processed_at) - latest).total_seconds())


def _load_state(path: Path) -> IdentityCatalogTriggerState:
    if not path.exists():
        return IdentityCatalogTriggerState((), None, None, None)
    payload = _read_json_object(path)
    if payload.get("schema_version") != TRIGGER_STATE_VERSION:
        raise IdentityCatalogTriggerError("trigger state version is invalid")
    return IdentityCatalogTriggerState(
        processed_request_ids=tuple(
            str(value) for value in payload.get("processed_request_ids", ())
        ),
        last_generation=(
            int(payload["last_generation"])
            if payload.get("last_generation") is not None
            else None
        ),
        last_publication_digest=(
            str(payload["last_publication_digest"])
            if payload.get("last_publication_digest") is not None
            else None
        ),
        last_successful_at=(
            str(payload["last_successful_at"])
            if payload.get("last_successful_at") is not None
            else None
        ),
    )


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IdentityCatalogTriggerError(f"expected JSON object in {path}")
    return payload


def _finding(
    receipt: IdentityTimelineCommitReceipt,
    code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "request_id": receipt.request_id,
        "agent_id": receipt.agent_id,
        "code": code,
        "message": message,
    }


def _instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


__all__ = [
    "IdentityCatalogTriggerError",
    "IdentityCatalogTriggerResult",
    "IdentityTimelineCommitInvalidError",
    "IdentityTimelineCommitReceipt",
    "append_timeline_commit_request",
    "finalize_identity_timeline_commit",
    "process_identity_catalog_triggers",
    "reconcile_timeline_commit_receipts",
    "verify_timeline_commit_receipt",
]
