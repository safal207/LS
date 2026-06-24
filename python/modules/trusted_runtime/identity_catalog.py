"""Signed read-only catalog for governed LS identity timelines."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .persistence import JsonlEventStoreAdapter, digest_json


IDENTITY_CATALOG_VERSION = "trusted_runtime.identity_catalog.v0.1"
IDENTITY_CATALOG_POLICY_VERSION = "identity_catalog.read_only.v0.1"
IDENTITY_CATALOG_ALGORITHM = "hmac-sha256"


class IdentityCatalogError(RuntimeError):
    """Base error for signed identity catalog operations."""


class IdentityCatalogIntegrityError(IdentityCatalogError):
    """Raised when a catalog signature or entry is invalid."""


@dataclass(frozen=True)
class IdentityCatalogEntry:
    agent_id: str
    bundle_path: str
    timeline_digest: str
    tail_event_ref: str
    event_count: int
    active_profile_version: int
    lifecycle_status: str
    freshness_at: str

    def __post_init__(self) -> None:
        required = (
            self.agent_id,
            self.bundle_path,
            self.timeline_digest,
            self.tail_event_ref,
            self.lifecycle_status,
            self.freshness_at,
        )
        if not all(required):
            raise ValueError("identity catalog entry fields must not be empty")
        path = Path(self.bundle_path)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("catalog bundle path must be safe and relative")
        if len(self.timeline_digest) != 64:
            raise ValueError("timeline digest must be a SHA-256 hex digest")
        if self.event_count < 1:
            raise ValueError("catalog entry must contain at least one event")
        if self.active_profile_version < 1:
            raise ValueError("active profile version must be positive")

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
        }


@dataclass(frozen=True)
class SignedIdentityCatalog:
    generated_at: str
    key_id: str
    entries: tuple[IdentityCatalogEntry, ...]
    signature: str
    algorithm: str = IDENTITY_CATALOG_ALGORITHM
    policy_version: str = IDENTITY_CATALOG_POLICY_VERSION
    schema_version: str = IDENTITY_CATALOG_VERSION

    def __post_init__(self) -> None:
        if not all((self.generated_at, self.key_id, self.signature, self.policy_version)):
            raise ValueError("identity catalog fields must not be empty")
        if self.schema_version != IDENTITY_CATALOG_VERSION:
            raise ValueError(f"unsupported catalog version: {self.schema_version}")
        if self.algorithm != IDENTITY_CATALOG_ALGORITHM:
            raise ValueError(f"unsupported catalog algorithm: {self.algorithm}")
        if len(self.signature) != 64:
            raise ValueError("catalog signature must be a SHA-256 hex digest")
        agent_ids = tuple(entry.agent_id for entry in self.entries)
        if len(agent_ids) != len(set(agent_ids)):
            raise ValueError("catalog agent IDs must be unique")
        bundle_paths = tuple(entry.bundle_path for entry in self.entries)
        if len(bundle_paths) != len(set(bundle_paths)):
            raise ValueError("catalog bundle paths must be unique")

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "key_id": self.key_id,
            "algorithm": self.algorithm,
            "policy_version": self.policy_version,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def to_dict(self) -> dict[str, Any]:
        payload = self.unsigned_dict()
        payload["signature"] = self.signature
        return payload

    def verify(self, secret: bytes) -> "SignedIdentityCatalog":
        expected = sign_catalog_payload(self.unsigned_dict(), secret)
        if not hmac.compare_digest(expected, self.signature):
            raise IdentityCatalogIntegrityError("identity catalog signature is invalid")
        return self

    def entry_for(self, agent_id: str) -> IdentityCatalogEntry:
        entry = next((item for item in self.entries if item.agent_id == agent_id), None)
        if entry is None:
            raise KeyError(agent_id)
        return entry


def build_signed_identity_catalog(
    data_root: Path,
    *,
    secret: bytes,
    key_id: str,
    generated_at: str,
) -> SignedIdentityCatalog:
    """Build a signed catalog from verified timeline bundles below data_root."""

    if not secret:
        raise ValueError("catalog signing secret must not be empty")
    if not key_id or not generated_at:
        raise ValueError("catalog key ID and generated_at must not be empty")
    root = Path(data_root).resolve()
    entries: list[IdentityCatalogEntry] = []
    for timeline_path in sorted(root.rglob("identity-timeline.json")):
        timeline = _read_json_object(timeline_path)
        bundle = timeline_path.parent.resolve()
        if root not in bundle.parents and bundle != root:
            raise IdentityCatalogIntegrityError("timeline bundle escapes catalog root")
        _verify_timeline_payload(timeline)
        events_path = bundle / "identity-events.jsonl"
        if not events_path.exists():
            raise IdentityCatalogIntegrityError(
                f"event store missing for agent {timeline.get('agent_id')!r}"
            )
        trail_id = str(timeline["trail_id"])
        scan = JsonlEventStoreAdapter(events_path).scan(trail_id)
        if scan.findings:
            codes = ", ".join(item.code for item in scan.findings)
            raise IdentityCatalogIntegrityError(
                f"event store invalid for agent {timeline.get('agent_id')!r}: {codes}"
            )
        integrity = timeline["integrity"]
        if len(scan.events) != int(integrity["event_count"]):
            raise IdentityCatalogIntegrityError("catalog event count does not match store")
        if scan.events[-1].event_ref != integrity["tail_event_ref"]:
            raise IdentityCatalogIntegrityError("catalog tail event ref does not match store")
        active_profile = timeline.get("active_profile")
        if not isinstance(active_profile, Mapping):
            raise IdentityCatalogIntegrityError("timeline has no active profile")
        entries.append(
            IdentityCatalogEntry(
                agent_id=str(timeline["agent_id"]),
                bundle_path=bundle.relative_to(root).as_posix() or ".",
                timeline_digest=str(integrity["timeline_digest"]),
                tail_event_ref=str(integrity["tail_event_ref"]),
                event_count=int(integrity["event_count"]),
                active_profile_version=int(active_profile["version"]),
                lifecycle_status=str(timeline["status"]),
                freshness_at=str(scan.events[-1].created_at),
            )
        )

    unsigned = {
        "schema_version": IDENTITY_CATALOG_VERSION,
        "generated_at": generated_at,
        "key_id": key_id,
        "algorithm": IDENTITY_CATALOG_ALGORITHM,
        "policy_version": IDENTITY_CATALOG_POLICY_VERSION,
        "entries": [entry.to_dict() for entry in entries],
    }
    return SignedIdentityCatalog(
        generated_at=generated_at,
        key_id=key_id,
        entries=tuple(entries),
        signature=sign_catalog_payload(unsigned, secret),
    )


def sign_catalog_payload(payload: Mapping[str, Any], secret: bytes) -> str:
    if not secret:
        raise ValueError("catalog signing secret must not be empty")
    message = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def write_signed_identity_catalog(path: Path, catalog: SignedIdentityCatalog) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(catalog.to_dict(), sort_keys=True, indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )


def load_signed_identity_catalog(
    path: Path,
    *,
    secret: bytes,
) -> SignedIdentityCatalog:
    payload = _read_json_object(path)
    entries_payload = payload.get("entries")
    if not isinstance(entries_payload, Sequence) or isinstance(
        entries_payload,
        (str, bytes),
    ):
        raise IdentityCatalogIntegrityError("catalog entries must be an array")
    catalog = SignedIdentityCatalog(
        generated_at=str(payload["generated_at"]),
        key_id=str(payload["key_id"]),
        algorithm=str(payload["algorithm"]),
        policy_version=str(payload["policy_version"]),
        schema_version=str(payload["schema_version"]),
        entries=tuple(
            IdentityCatalogEntry(
                agent_id=str(item["agent_id"]),
                bundle_path=str(item["bundle_path"]),
                timeline_digest=str(item["timeline_digest"]),
                tail_event_ref=str(item["tail_event_ref"]),
                event_count=int(item["event_count"]),
                active_profile_version=int(item["active_profile_version"]),
                lifecycle_status=str(item["lifecycle_status"]),
                freshness_at=str(item["freshness_at"]),
            )
            for item in entries_payload
        ),
        signature=str(payload["signature"]),
    )
    return catalog.verify(secret)


def verify_catalog_entry_bundle(
    data_root: Path,
    entry: IdentityCatalogEntry,
) -> tuple[Path, tuple[dict[str, Any], ...]]:
    """Verify an entry against its current bundle and return findings."""

    root = Path(data_root).resolve()
    bundle = (root / entry.bundle_path).resolve()
    findings: list[dict[str, Any]] = []
    if root not in bundle.parents and bundle != root:
        return bundle, (
            _finding("CATALOG_PATH_ESCAPE", "catalog bundle path escapes data root"),
        )
    timeline_path = bundle / "identity-timeline.json"
    events_path = bundle / "identity-events.jsonl"
    if not timeline_path.exists():
        findings.append(_finding("CATALOG_TIMELINE_MISSING", "timeline file is missing"))
        return bundle, tuple(findings)
    try:
        timeline = _read_json_object(timeline_path)
    except Exception as error:
        findings.append(_finding("CATALOG_TIMELINE_INVALID", str(error)))
        return bundle, tuple(findings)
    integrity = timeline.get("integrity")
    if not isinstance(integrity, Mapping):
        findings.append(_finding("CATALOG_TIMELINE_INTEGRITY_MISSING", "timeline integrity is missing"))
    else:
        if timeline.get("agent_id") != entry.agent_id:
            findings.append(_finding("CATALOG_AGENT_MISMATCH", "catalog agent ID does not match timeline"))
        if integrity.get("timeline_digest") != entry.timeline_digest:
            findings.append(_finding("CATALOG_TIMELINE_DIGEST_MISMATCH", "catalog timeline digest does not match bundle"))
        if integrity.get("tail_event_ref") != entry.tail_event_ref:
            findings.append(_finding("CATALOG_TAIL_REF_MISMATCH", "catalog tail event ref does not match bundle"))
        if int(integrity.get("event_count", -1)) != entry.event_count:
            findings.append(_finding("CATALOG_EVENT_COUNT_MISMATCH", "catalog event count does not match bundle"))
    active_profile = timeline.get("active_profile")
    if not isinstance(active_profile, Mapping) or int(active_profile.get("version", -1)) != entry.active_profile_version:
        findings.append(_finding("CATALOG_PROFILE_VERSION_MISMATCH", "catalog profile version does not match bundle"))
    if not events_path.exists():
        findings.append(_finding("CATALOG_EVENT_STORE_MISSING", "event store is missing"))
    return bundle, tuple(findings)


def _verify_timeline_payload(timeline: Mapping[str, Any]) -> None:
    integrity = timeline.get("integrity")
    if not isinstance(integrity, Mapping):
        raise IdentityCatalogIntegrityError("timeline integrity block is missing")
    expected = integrity.get("timeline_digest")
    unsigned = dict(timeline)
    unsigned.pop("integrity", None)
    if expected != digest_json(unsigned):
        raise IdentityCatalogIntegrityError("timeline digest is invalid")


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise IdentityCatalogIntegrityError(f"expected JSON object in {path}")
    return payload


def _finding(code: str, message: str) -> dict[str, Any]:
    return {"code": code, "message": message, "source": "identity_catalog"}


__all__ = [
    "IdentityCatalogEntry",
    "IdentityCatalogError",
    "IdentityCatalogIntegrityError",
    "SignedIdentityCatalog",
    "build_signed_identity_catalog",
    "load_signed_identity_catalog",
    "verify_catalog_entry_bundle",
    "write_signed_identity_catalog",
]
