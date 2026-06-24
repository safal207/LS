"""Signed-catalog, paginated, read-only Identity Timeline viewer."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence
from urllib.parse import parse_qs, quote, unquote

from .identity_catalog import (
    IdentityCatalogIntegrityError,
    SignedIdentityCatalog,
    load_signed_identity_catalog,
    verify_catalog_entry_bundle,
)
from .identity_timeline_api import (
    DirectoryIdentityTimelineRepository,
    IdentityTimelineReadOnlyAPI,
    IdentityTimelineWSGIApplication,
    TimelineNotFoundError,
    TimelineSnapshot,
    TimelineSource,
)


IDENTITY_LIVE_VIEWER_VERSION = "trusted_runtime.identity_live_viewer.v0.1"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


class CatalogIdentityTimelineRepository:
    """Timeline repository that trusts only a verified signed catalog."""

    def __init__(
        self,
        data_root: Path,
        catalog_path: Path,
        *,
        secret: bytes,
    ) -> None:
        if not secret:
            raise ValueError("catalog verification secret must not be empty")
        self.data_root = Path(data_root).resolve()
        self.catalog_path = Path(catalog_path)
        self.secret = bytes(secret)

    def catalog(self) -> SignedIdentityCatalog:
        return load_signed_identity_catalog(self.catalog_path, secret=self.secret)

    def list_sources(self) -> tuple[TimelineSource, ...]:
        catalog = self.catalog()
        sources = []
        for entry in catalog.entries:
            bundle = (self.data_root / entry.bundle_path).resolve()
            sources.append(
                TimelineSource(
                    agent_id=entry.agent_id,
                    root=bundle,
                    timeline_path=bundle / "identity-timeline.json",
                    events_path=bundle / "identity-events.jsonl",
                )
            )
        return tuple(sources)

    def get_source(self, agent_id: str) -> TimelineSource:
        source = next(
            (item for item in self.list_sources() if item.agent_id == agent_id),
            None,
        )
        if source is None:
            raise TimelineNotFoundError(f"identity timeline not found: {agent_id}")
        return source

    def load_snapshot(self, agent_id: str) -> TimelineSnapshot:
        catalog = self.catalog()
        try:
            entry = catalog.entry_for(agent_id)
        except KeyError as error:
            raise TimelineNotFoundError(
                f"identity timeline not found: {agent_id}"
            ) from error
        source = self.get_source(agent_id)
        base = DirectoryIdentityTimelineRepository(source.root).load_snapshot(agent_id)
        _, catalog_findings = verify_catalog_entry_bundle(self.data_root, entry)
        findings = (*base.findings, *catalog_findings)
        return TimelineSnapshot(
            agent_id=base.agent_id,
            valid=base.valid and not catalog_findings,
            integrity_status=(
                "VALID" if base.valid and not catalog_findings else "INVALID"
            ),
            timeline=base.timeline,
            persisted_timeline=base.persisted_timeline,
            events=base.events,
            findings=tuple(findings),
            source=source,
        )

    def catalog_response(self) -> Mapping[str, Any]:
        catalog = self.catalog()
        entries = []
        for entry in catalog.entries:
            _, findings = verify_catalog_entry_bundle(self.data_root, entry)
            entries.append(
                {
                    "agent_id": entry.agent_id,
                    "timeline_digest": entry.timeline_digest,
                    "tail_event_ref": entry.tail_event_ref,
                    "event_count": entry.event_count,
                    "active_profile_version": entry.active_profile_version,
                    "lifecycle_status": entry.lifecycle_status,
                    "freshness_at": entry.freshness_at,
                    "health": "VALID" if not findings else "INVALID",
                    "findings": list(findings),
                }
            )
        return {
            "schema_version": IDENTITY_LIVE_VIEWER_VERSION,
            "read_only": True,
            "signature_verified": True,
            "catalog": {
                "schema_version": catalog.schema_version,
                "generated_at": catalog.generated_at,
                "key_id": catalog.key_id,
                "algorithm": catalog.algorithm,
                "policy_version": catalog.policy_version,
                "entry_count": len(catalog.entries),
                "signature": catalog.signature,
            },
            "entries": entries,
        }


class SignedCatalogIdentityTimelineAPI(IdentityTimelineReadOnlyAPI):
    """Adds signed catalog status and deterministic event pagination."""

    def __init__(self, repository: CatalogIdentityTimelineRepository) -> None:
        super().__init__(repository)  # type: ignore[arg-type]
        self.catalog_repository = repository

    def handle_live(
        self,
        method: str,
        path: str,
        *,
        query_string: str = "",
        if_none_match: Optional[str] = None,
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        normalized_method = method.upper()
        if normalized_method not in self.allowed_methods:
            return super().handle(normalized_method, path)
        segments = [unquote(segment) for segment in path.split("/") if segment]
        try:
            if segments == ["api", "v1", "catalog"]:
                response = self._json(
                    200,
                    self.catalog_repository.catalog_response(),
                )
            elif (
                len(segments) == 5
                and segments[:3] == ["api", "v1", "agents"]
                and segments[4] == "events"
            ):
                response = self._events_page(
                    segments[3],
                    query_string=query_string,
                )
            else:
                response = super().handle(normalized_method, path)
        except IdentityCatalogIntegrityError as error:
            response = self._json(
                409,
                {
                    "error": "catalog_integrity_failure",
                    "message": str(error),
                    "read_only": True,
                    "authoritative": False,
                },
            )
        response = _with_etag(response)
        if if_none_match and _header(response[3], "ETag") == if_none_match:
            return 304, "Not Modified", b"", tuple(
                header
                for header in response[3]
                if header[0].lower() in {"etag", "cache-control", "vary"}
            )
        if normalized_method == "HEAD":
            return response[0], response[1], b"", response[3]
        return response

    def _events_page(
        self,
        agent_id: str,
        *,
        query_string: str,
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        parameters = parse_qs(query_string, keep_blank_values=True)
        try:
            cursor = int(parameters.get("cursor", ["0"])[0])
            limit = int(parameters.get("limit", [str(DEFAULT_PAGE_SIZE)])[0])
        except ValueError:
            return self._json(
                400,
                {
                    "error": "invalid_pagination",
                    "message": "cursor and limit must be integers",
                },
            )
        if cursor < 0 or limit < 1 or limit > MAX_PAGE_SIZE:
            return self._json(
                400,
                {
                    "error": "invalid_pagination",
                    "message": (
                        f"cursor must be non-negative and limit must be 1-{MAX_PAGE_SIZE}"
                    ),
                },
            )
        snapshot = self.catalog_repository.load_snapshot(agent_id)
        total = len(snapshot.events)
        items = []
        for event in snapshot.events[cursor : cursor + limit]:
            item = dict(event)
            event_ref = str(item.get("event_ref", ""))
            item["source_record_url"] = (
                f"/api/v1/agents/{quote(agent_id, safe='')}/events/"
                f"{quote(event_ref, safe='')}"
            )
            items.append(item)
        next_cursor = cursor + len(items)
        return self._json(
            200,
            {
                "schema_version": IDENTITY_LIVE_VIEWER_VERSION,
                "read_only": True,
                "agent_id": agent_id,
                "integrity_status": snapshot.integrity_status,
                "authoritative": snapshot.valid,
                "cursor": cursor,
                "limit": limit,
                "next_cursor": str(next_cursor) if next_cursor < total else None,
                "total": total,
                "causal_order": "durable_sequence_ascending",
                "tail_event_ref": (
                    snapshot.events[-1].get("event_ref") if snapshot.events else None
                ),
                "items": items,
            },
        )


class SignedCatalogIdentityTimelineWSGIApplication(IdentityTimelineWSGIApplication):
    """WSGI adapter with query pagination and conditional GET support."""

    api: SignedCatalogIdentityTimelineAPI

    def __call__(self, environ: Mapping[str, Any], start_response: Any) -> Sequence[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET"))
        path = str(environ.get("PATH_INFO", "/"))
        if path.startswith("/api/"):
            status, reason, body, headers = self.api.handle_live(
                method,
                path,
                query_string=str(environ.get("QUERY_STRING", "")),
                if_none_match=(
                    str(environ["HTTP_IF_NONE_MATCH"])
                    if environ.get("HTTP_IF_NONE_MATCH")
                    else None
                ),
            )
        else:
            status, reason, body, headers = self._static(method, path)
            status, reason, body, headers = _with_etag(
                (status, reason, body, headers)
            )
            if (
                environ.get("HTTP_IF_NONE_MATCH")
                and _header(headers, "ETag") == str(environ["HTTP_IF_NONE_MATCH"])
            ):
                status, reason, body = 304, "Not Modified", b""
                headers = tuple(
                    header
                    for header in headers
                    if header[0].lower() in {"etag", "cache-control", "vary"}
                )
        response_headers = list(headers)
        response_headers.append(("Content-Length", str(len(body))))
        start_response(f"{status} {reason}", response_headers)
        return (body,)


def build_signed_catalog_identity_viewer(
    data_root: Path,
    catalog_path: Path,
    *,
    secret: bytes,
    asset_root: Optional[Path] = None,
) -> SignedCatalogIdentityTimelineWSGIApplication:
    repository = CatalogIdentityTimelineRepository(
        data_root,
        catalog_path,
        secret=secret,
    )
    return SignedCatalogIdentityTimelineWSGIApplication(
        SignedCatalogIdentityTimelineAPI(repository),
        asset_root=asset_root,
    )


def _with_etag(
    response: tuple[int, str, bytes, tuple[tuple[str, str], ...]],
) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
    status, reason, body, headers = response
    if status != 200:
        return response
    etag = '"sha256:' + hashlib.sha256(body).hexdigest() + '"'
    filtered = tuple(header for header in headers if header[0].lower() != "etag")
    return status, reason, body, (*filtered, ("ETag", etag), ("Vary", "Accept"))


def _header(headers: Sequence[tuple[str, str]], name: str) -> Optional[str]:
    lowered = name.lower()
    return next((value for key, value in headers if key.lower() == lowered), None)


__all__ = [
    "CatalogIdentityTimelineRepository",
    "SignedCatalogIdentityTimelineAPI",
    "SignedCatalogIdentityTimelineWSGIApplication",
    "build_signed_catalog_identity_viewer",
]
