"""Atomic publisher for signed, monotonic identity catalog generations.

The publisher observes append-only identity timeline bundles. It never mutates
agent identity data. Each successful publication is immutable, chained to the
previous generation, signed by one or more rotation keys, and written through
atomic file replacement.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Mapping, Optional, Sequence

from .identity_catalog import (
    IDENTITY_CATALOG_ALGORITHM,
    IDENTITY_CATALOG_POLICY_VERSION,
    IDENTITY_CATALOG_VERSION,
    IdentityCatalogEntry,
    SignedIdentityCatalog,
    sign_catalog_payload,
)
from .persistence import JsonlEventStoreAdapter, digest_json


CATALOG_PUBLICATION_VERSION = "trusted_runtime.identity_catalog_publication.v0.1"
CATALOG_PUBLISHER_STATE_VERSION = (
    "trusted_runtime.identity_catalog_publisher_state.v0.1"
)
CATALOG_PUBLISHER_POLICY_VERSION = "identity_catalog.publisher.v0.1"


class CatalogPublisherError(RuntimeError):
    """Base error for catalog publishing."""


class CatalogPublisherBusyError(CatalogPublisherError):
    """Raised when another publisher owns the publication lock."""


class CatalogGenerationRollbackError(CatalogPublisherError):
    """Raised when publication would move to an older generation."""


class CatalogPublicationIntegrityError(CatalogPublisherError):
    """Raised when a published snapshot cannot be verified."""


@dataclass(frozen=True)
class PublishedAgentEntry:
    agent_id: str
    bundle_path: str
    timeline_digest: Optional[str]
    tail_event_ref: Optional[str]
    event_count: int
    active_profile_version: Optional[int]
    lifecycle_status: str
    freshness_at: Optional[str]
    visibility: tuple[str, ...]
    health: str
    authoritative: bool
    findings: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if not self.agent_id or not self.bundle_path or not self.lifecycle_status:
            raise ValueError("published agent entry identifiers must not be empty")
        path = Path(self.bundle_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("published bundle path must be safe and relative")
        if self.event_count < 0:
            raise ValueError("event count must be non-negative")
        if self.active_profile_version is not None:
            if self.active_profile_version < 1:
                raise ValueError("active profile version must be positive")
        if self.health not in {"VALID", "STALE", "INVALID"}:
            raise ValueError(f"unsupported catalog health: {self.health}")
        if self.authoritative != (self.health == "VALID"):
            raise ValueError("only VALID entries may be authoritative")
        if not self.visibility:
            raise ValueError("published agent entry requires visibility metadata")
        if len(self.visibility) != len(set(self.visibility)):
            raise ValueError("visibility audiences must be unique")

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "bundle_path": self.bundle_path,
            "timeline_digest": self.timeline_digest,
            "tail_event_ref": self.tail_event_ref,
            "event_count": self.event_count,
            "active_profile_version": self.active_profile_version,
            "lifecycle_status": self.lifecycle_status,
            "freshness_at": self.freshness_at,
            "visibility": list(self.visibility),
            "health": self.health,
            "authoritative": self.authoritative,
            "findings": [dict(item) for item in self.findings],
        }


@dataclass(frozen=True)
class PublishedIdentityCatalog:
    generation: int
    published_at: str
    audience: str
    active_key_id: str
    accepted_key_ids: tuple[str, ...]
    previous_publication_digest: Optional[str]
    source_fingerprint: str
    entries: tuple[PublishedAgentEntry, ...]
    legacy_catalog: Mapping[str, Any]
    signatures: Mapping[str, str]
    policy_version: str = CATALOG_PUBLISHER_POLICY_VERSION
    schema_version: str = CATALOG_PUBLICATION_VERSION

    def __post_init__(self) -> None:
        required = (
            self.published_at,
            self.audience,
            self.active_key_id,
            self.source_fingerprint,
            self.policy_version,
        )
        if self.generation < 1 or not all(required):
            raise ValueError("catalog publication fields are invalid")
        if self.schema_version != CATALOG_PUBLICATION_VERSION:
            raise ValueError(
                f"unsupported catalog publication version: {self.schema_version}"
            )
        if self.active_key_id not in self.accepted_key_ids:
            raise ValueError("active key must appear in accepted key IDs")
        if set(self.signatures) != set(self.accepted_key_ids):
            raise ValueError("publication signatures must match accepted key IDs")
        if any(len(value) != 64 for value in self.signatures.values()):
            raise ValueError("publication signatures must be SHA-256 hex digests")
        agent_ids = tuple(entry.agent_id for entry in self.entries)
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("publication agent IDs must be unique")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generation": self.generation,
            "published_at": self.published_at,
            "audience": self.audience,
            "active_key_id": self.active_key_id,
            "accepted_key_ids": list(self.accepted_key_ids),
            "previous_publication_digest": self.previous_publication_digest,
            "source_fingerprint": self.source_fingerprint,
            "entries": [entry.to_dict() for entry in self.entries],
            "legacy_catalog": dict(self.legacy_catalog),
            "policy_version": self.policy_version,
        }

    @property
    def publication_digest(self) -> str:
        return digest_json(
            {**self.unsigned_dict(), "signatures": dict(self.signatures)}
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.unsigned_dict(),
            "signatures": dict(self.signatures),
            "integrity": {
                "algorithm": "sha256",
                "publication_digest": self.publication_digest,
            },
        }

    def verify(
        self,
        keyring: Mapping[str, bytes],
        *,
        minimum_generation: Optional[int] = None,
    ) -> "PublishedIdentityCatalog":
        if minimum_generation is not None:
            if self.generation < minimum_generation:
                raise CatalogGenerationRollbackError(
                    f"catalog generation {self.generation} is older than "
                    f"{minimum_generation}"
                )
        unsigned = self.unsigned_dict()
        verified = []
        for key_id, signature in self.signatures.items():
            key_material = keyring.get(key_id)
            if key_material is None:
                continue
            expected = _sign_publication(unsigned, key_material)
            if hmac.compare_digest(expected, signature):
                verified.append(key_id)
        if not verified:
            raise CatalogPublicationIntegrityError(
                "catalog publication has no valid signature for the supplied keyring"
            )
        return self

    def entry_for(self, agent_id: str) -> PublishedAgentEntry:
        entry = next((item for item in self.entries if item.agent_id == agent_id), None)
        if entry is None:
            raise KeyError(agent_id)
        return entry


@dataclass(frozen=True)
class CatalogPublisherState:
    highest_generation: int
    publication_digest: str
    source_fingerprint: str
    updated_at: str
    schema_version: str = CATALOG_PUBLISHER_STATE_VERSION

    def __post_init__(self) -> None:
        if self.highest_generation < 1:
            raise ValueError("publisher state generation must be positive")
        if not all(
            (self.publication_digest, self.source_fingerprint, self.updated_at)
        ):
            raise ValueError("publisher state fields must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "highest_generation": self.highest_generation,
            "publication_digest": self.publication_digest,
            "source_fingerprint": self.source_fingerprint,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class CatalogPublishResult:
    publication: PublishedIdentityCatalog
    changed: bool
    publication_path: Path
    legacy_catalog_path: Path
    history_path: Path
    state_path: Path


def publish_identity_catalog(
    data_root: Path,
    output_root: Path,
    *,
    keyring: Mapping[str, bytes],
    active_key_id: str,
    signing_key_ids: Sequence[str],
    audience: str,
    visibility_policy: Mapping[str, Sequence[str]],
    published_at: str,
    stale_after_seconds: int,
    lock_timeout_seconds: int = 0,
) -> CatalogPublishResult:
    """Atomically publish the next generation, or reuse an identical one."""

    del lock_timeout_seconds
    accepted_key_ids = tuple(dict.fromkeys(signing_key_ids))
    _validate_publish_inputs(
        keyring,
        active_key_id=active_key_id,
        accepted_key_ids=accepted_key_ids,
        stale_after_seconds=stale_after_seconds,
    )

    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    publication_path = root / "identity-catalog-publication.json"
    legacy_catalog_path = root / "identity-catalog.json"
    state_path = root / "identity-catalog-publisher-state.json"
    history_root = root / "history"
    history_root.mkdir(parents=True, exist_ok=True)

    with _publisher_lock(root / ".identity-catalog-publisher.lock"):
        state = _load_state(state_path)
        current = _load_current(publication_path, state, keyring)
        entries = _discover_entries(
            Path(data_root),
            audience=audience,
            visibility_policy=visibility_policy,
            published_at=published_at,
            stale_after_seconds=stale_after_seconds,
        )
        authoritative_entries = tuple(
            entry for entry in entries if entry.authoritative
        )

        source_fingerprint = digest_json(
            {
                "audience": audience,
                "active_key_id": active_key_id,
                "accepted_key_ids": list(accepted_key_ids),
                "entries": [entry.to_dict() for entry in entries],
            }
        )
        if current is not None:
            if current.source_fingerprint == source_fingerprint:
                return CatalogPublishResult(
                    publication=current,
                    changed=False,
                    publication_path=publication_path,
                    legacy_catalog_path=legacy_catalog_path,
                    history_path=(
                        history_root
                        / f"generation-{current.generation:020d}.json"
                    ),
                    state_path=state_path,
                )

        generation = state.highest_generation + 1 if state else 1
        legacy_catalog = _build_legacy_catalog(
            authoritative_entries,
            key_id=active_key_id,
            key_material=keyring[active_key_id],
            generated_at=published_at,
        )
        unsigned = {
            "schema_version": CATALOG_PUBLICATION_VERSION,
            "generation": generation,
            "published_at": published_at,
            "audience": audience,
            "active_key_id": active_key_id,
            "accepted_key_ids": list(accepted_key_ids),
            "previous_publication_digest": (
                current.publication_digest if current is not None else None
            ),
            "source_fingerprint": source_fingerprint,
            "entries": [entry.to_dict() for entry in entries],
            "legacy_catalog": legacy_catalog,
            "policy_version": CATALOG_PUBLISHER_POLICY_VERSION,
        }
        publication = PublishedIdentityCatalog(
            generation=generation,
            published_at=published_at,
            audience=audience,
            active_key_id=active_key_id,
            accepted_key_ids=accepted_key_ids,
            previous_publication_digest=unsigned["previous_publication_digest"],
            source_fingerprint=source_fingerprint,
            entries=entries,
            legacy_catalog=legacy_catalog,
            signatures={
                key_id: _sign_publication(unsigned, keyring[key_id])
                for key_id in accepted_key_ids
            },
        )
        history_path = history_root / f"generation-{generation:020d}.json"
        next_state = CatalogPublisherState(
            highest_generation=generation,
            publication_digest=publication.publication_digest,
            source_fingerprint=source_fingerprint,
            updated_at=published_at,
        )

        _atomic_write_json(history_path, publication.to_dict())
        _atomic_write_json(publication_path, publication.to_dict())
        _atomic_write_json(legacy_catalog_path, legacy_catalog)
        _atomic_write_json(state_path, next_state.to_dict())
        return CatalogPublishResult(
            publication=publication,
            changed=True,
            publication_path=publication_path,
            legacy_catalog_path=legacy_catalog_path,
            history_path=history_path,
            state_path=state_path,
        )


def load_published_identity_catalog(
    path: Path,
    *,
    keyring: Mapping[str, bytes],
    minimum_generation: Optional[int] = None,
) -> PublishedIdentityCatalog:
    payload = _read_json_object(path)
    publication = PublishedIdentityCatalog(
        generation=int(payload["generation"]),
        published_at=str(payload["published_at"]),
        audience=str(payload["audience"]),
        active_key_id=str(payload["active_key_id"]),
        accepted_key_ids=tuple(
            str(value) for value in payload["accepted_key_ids"]
        ),
        previous_publication_digest=_optional_string(
            payload.get("previous_publication_digest")
        ),
        source_fingerprint=str(payload["source_fingerprint"]),
        entries=tuple(_entry_from_mapping(item) for item in payload["entries"]),
        legacy_catalog=dict(payload["legacy_catalog"]),
        signatures={
            str(key): str(value)
            for key, value in payload["signatures"].items()
        },
        policy_version=str(payload["policy_version"]),
        schema_version=str(payload["schema_version"]),
    )
    expected_digest = payload.get("integrity", {}).get("publication_digest")
    if expected_digest != publication.publication_digest:
        raise CatalogPublicationIntegrityError("publication digest is invalid")
    return publication.verify(keyring, minimum_generation=minimum_generation)


def _entry_from_mapping(item: Mapping[str, Any]) -> PublishedAgentEntry:
    return PublishedAgentEntry(
        agent_id=str(item["agent_id"]),
        bundle_path=str(item["bundle_path"]),
        timeline_digest=_optional_string(item.get("timeline_digest")),
        tail_event_ref=_optional_string(item.get("tail_event_ref")),
        event_count=int(item["event_count"]),
        active_profile_version=(
            int(item["active_profile_version"])
            if item.get("active_profile_version") is not None
            else None
        ),
        lifecycle_status=str(item["lifecycle_status"]),
        freshness_at=_optional_string(item.get("freshness_at")),
        visibility=tuple(str(value) for value in item["visibility"]),
        health=str(item["health"]),
        authoritative=bool(item["authoritative"]),
        findings=tuple(dict(value) for value in item.get("findings", ())),
    )


def _validate_publish_inputs(
    keyring: Mapping[str, bytes],
    *,
    active_key_id: str,
    accepted_key_ids: Sequence[str],
    stale_after_seconds: int,
) -> None:
    if active_key_id not in keyring:
        raise ValueError("active catalog signing key is missing from keyring")
    if active_key_id not in accepted_key_ids:
        raise ValueError("active key must be included in signing key IDs")
    for key_id in accepted_key_ids:
        if not keyring.get(key_id):
            raise ValueError(f"catalog signing key is missing: {key_id}")
    if stale_after_seconds < 0:
        raise ValueError("stale_after_seconds must be non-negative")


def _load_current(
    publication_path: Path,
    state: Optional[CatalogPublisherState],
    keyring: Mapping[str, bytes],
) -> Optional[PublishedIdentityCatalog]:
    if not publication_path.exists():
        if state is not None:
            raise CatalogGenerationRollbackError(
                "publisher state exists but current publication is missing"
            )
        return None
    current = load_published_identity_catalog(
        publication_path,
        keyring=keyring,
        minimum_generation=(state.highest_generation if state else None),
    )
    if state is not None:
        if current.publication_digest != state.publication_digest:
            raise CatalogGenerationRollbackError(
                "current publication does not match publisher state"
            )
    return current


def _discover_entries(
    data_root: Path,
    *,
    audience: str,
    visibility_policy: Mapping[str, Sequence[str]],
    published_at: str,
    stale_after_seconds: int,
) -> tuple[PublishedAgentEntry, ...]:
    root = data_root.resolve()
    if not root.exists():
        return ()
    discovered = []
    for timeline_path in sorted(root.rglob("identity-timeline.json")):
        try:
            timeline = _read_json_object(timeline_path)
        except Exception:
            continue
        agent_id = str(timeline.get("agent_id", ""))
        if not agent_id:
            continue
        visibility = tuple(
            dict.fromkeys(
                str(value)
                for value in visibility_policy.get(agent_id, ("internal",))
            )
        )
        if audience not in visibility and "*" not in visibility:
            continue
        discovered.append(
            _inspect_agent_bundle(
                root,
                timeline_path,
                timeline,
                visibility=visibility,
                published_at=published_at,
                stale_after_seconds=stale_after_seconds,
            )
        )
    return tuple(sorted(discovered, key=lambda entry: entry.agent_id))


def _inspect_agent_bundle(
    root: Path,
    timeline_path: Path,
    timeline: Mapping[str, Any],
    *,
    visibility: tuple[str, ...],
    published_at: str,
    stale_after_seconds: int,
) -> PublishedAgentEntry:
    bundle = timeline_path.parent.resolve()
    findings = []
    integrity = timeline.get("integrity")
    timeline_digest = None
    tail_event_ref = None
    event_count = 0
    if not isinstance(integrity, Mapping):
        findings.append(
            _finding(
                "TIMELINE_INTEGRITY_MISSING",
                "timeline integrity block is missing",
            )
        )
    else:
        timeline_digest = _optional_string(integrity.get("timeline_digest"))
        tail_event_ref = _optional_string(integrity.get("tail_event_ref"))
        event_count = int(integrity.get("event_count", 0))
        unsigned = dict(timeline)
        unsigned.pop("integrity", None)
        if timeline_digest != digest_json(unsigned):
            findings.append(
                _finding(
                    "TIMELINE_DIGEST_INVALID",
                    "timeline digest does not match payload",
                )
            )

    freshness_at = None
    events_path = bundle / "identity-events.jsonl"
    if not events_path.exists():
        findings.append(_finding("EVENT_STORE_MISSING", "event store is missing"))
    else:
        scan = JsonlEventStoreAdapter(events_path).scan(
            str(timeline.get("trail_id", ""))
        )
        findings.extend(_finding(item.code, item.message) for item in scan.findings)
        if scan.events:
            freshness_at = str(scan.events[-1].created_at)
            if event_count != len(scan.events):
                findings.append(
                    _finding(
                        "EVENT_COUNT_MISMATCH",
                        "timeline event count differs from store",
                    )
                )
            if tail_event_ref != scan.events[-1].event_ref:
                findings.append(
                    _finding(
                        "TAIL_EVENT_REF_MISMATCH",
                        "timeline tail ref differs from store",
                    )
                )

    active_profile = timeline.get("active_profile")
    active_version = None
    if isinstance(active_profile, Mapping):
        if active_profile.get("version") is not None:
            active_version = int(active_profile["version"])
    if active_version is None:
        findings.append(
            _finding("ACTIVE_PROFILE_MISSING", "active profile is missing")
        )

    stale = freshness_at is None
    if freshness_at is not None:
        stale = _age_seconds(published_at, freshness_at) > stale_after_seconds
    health = "INVALID" if findings else ("STALE" if stale else "VALID")
    return PublishedAgentEntry(
        agent_id=str(timeline["agent_id"]),
        bundle_path=bundle.relative_to(root).as_posix() or ".",
        timeline_digest=timeline_digest,
        tail_event_ref=tail_event_ref,
        event_count=event_count,
        active_profile_version=active_version,
        lifecycle_status=str(timeline.get("status", "UNKNOWN")),
        freshness_at=freshness_at,
        visibility=visibility,
        health=health,
        authoritative=health == "VALID",
        findings=tuple(findings),
    )


def _build_legacy_catalog(
    entries: Sequence[PublishedAgentEntry],
    *,
    key_id: str,
    key_material: bytes,
    generated_at: str,
) -> dict[str, Any]:
    catalog_entries = tuple(
        IdentityCatalogEntry(
            agent_id=entry.agent_id,
            bundle_path=entry.bundle_path,
            timeline_digest=str(entry.timeline_digest),
            tail_event_ref=str(entry.tail_event_ref),
            event_count=entry.event_count,
            active_profile_version=int(entry.active_profile_version),
            lifecycle_status=entry.lifecycle_status,
            freshness_at=str(entry.freshness_at),
        )
        for entry in entries
    )
    unsigned = {
        "schema_version": IDENTITY_CATALOG_VERSION,
        "generated_at": generated_at,
        "key_id": key_id,
        "algorithm": IDENTITY_CATALOG_ALGORITHM,
        "policy_version": IDENTITY_CATALOG_POLICY_VERSION,
        "entries": [entry.to_dict() for entry in catalog_entries],
    }
    return SignedIdentityCatalog(
        generated_at=generated_at,
        key_id=key_id,
        entries=catalog_entries,
        signature=sign_catalog_payload(unsigned, key_material),
    ).to_dict()


def _sign_publication(payload: Mapping[str, Any], key_material: bytes) -> str:
    if not key_material:
        raise ValueError("publication signing key material must not be empty")
    message = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hmac.new(key_material, message, hashlib.sha256).hexdigest()


def _load_state(path: Path) -> Optional[CatalogPublisherState]:
    if not path.exists():
        return None
    payload = _read_json_object(path)
    if payload.get("schema_version") != CATALOG_PUBLISHER_STATE_VERSION:
        raise CatalogPublicationIntegrityError("publisher state version is invalid")
    return CatalogPublisherState(
        highest_generation=int(payload["highest_generation"]),
        publication_digest=str(payload["publication_digest"]),
        source_fingerprint=str(payload["source_fingerprint"]),
        updated_at=str(payload["updated_at"]),
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
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


@contextmanager
def _publisher_lock(path: Path) -> Iterator[None]:
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise CatalogPublisherBusyError(
            "identity catalog publisher is already running"
        ) from error
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii"))
        os.close(descriptor)
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _age_seconds(now: str, earlier: str) -> float:
    return max(0.0, (_instant(now) - _instant(earlier)).total_seconds())


def _instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_string(value: Any) -> Optional[str]:
    return str(value) if value is not None else None


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CatalogPublicationIntegrityError(f"expected JSON object in {path}")
    return payload


def _finding(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "source": "identity_catalog_publisher",
    }


__all__ = [
    "CatalogGenerationRollbackError",
    "CatalogPublicationIntegrityError",
    "CatalogPublishResult",
    "CatalogPublisherBusyError",
    "PublishedAgentEntry",
    "PublishedIdentityCatalog",
    "load_published_identity_catalog",
    "publish_identity_catalog",
]
