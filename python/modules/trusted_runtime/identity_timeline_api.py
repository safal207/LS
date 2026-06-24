"""Read-only API surface for governed identity timelines.

The API rebuilds the projection from the append-only event stream and compares
it with the persisted identity-timeline.json. Invalid or mismatched timelines
remain inspectable, but their active profile is never presented as authoritative.
"""

from __future__ import annotations

import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence
from urllib.parse import quote, unquote

from .identity_timeline import scan_identity_timeline
from .persistence import (
    EventStoreCorruptionError,
    JsonlEventStoreAdapter,
    StoreFinding,
    digest_json,
)


IDENTITY_TIMELINE_API_VERSION = "trusted_runtime.identity_timeline_api.v0.1"
JSON_CONTENT_TYPE = "application/json; charset=utf-8"
TEXT_CONTENT_TYPE = "text/plain; charset=utf-8"


class IdentityTimelineAPIError(RuntimeError):
    """Base error for the read-only timeline API."""


class TimelineNotFoundError(IdentityTimelineAPIError):
    """Raised when an agent timeline cannot be found."""


class DuplicateAgentTimelineError(IdentityTimelineAPIError):
    """Raised when two directories claim the same agent ID."""


@dataclass(frozen=True)
class TimelineSource:
    agent_id: str
    root: Path
    timeline_path: Path
    events_path: Path


@dataclass(frozen=True)
class TimelineSnapshot:
    agent_id: str
    valid: bool
    integrity_status: str
    timeline: Mapping[str, Any]
    persisted_timeline: Mapping[str, Any]
    events: tuple[Mapping[str, Any], ...]
    findings: tuple[Mapping[str, Any], ...]
    source: TimelineSource

    def event_by_ref(self, event_ref: str) -> Optional[Mapping[str, Any]]:
        return next(
            (event for event in self.events if event.get("event_ref") == event_ref),
            None,
        )


class DirectoryIdentityTimelineRepository:
    """Discovers read-only identity timeline bundles below a directory."""

    def __init__(self, data_root: Path) -> None:
        self.data_root = Path(data_root)

    def list_sources(self) -> tuple[TimelineSource, ...]:
        if not self.data_root.exists():
            return ()
        candidates = sorted(self.data_root.rglob("identity-timeline.json"))
        sources: dict[str, TimelineSource] = {}
        for timeline_path in candidates:
            try:
                payload = _read_json_object(timeline_path)
                agent_id = str(payload["agent_id"])
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
            source = TimelineSource(
                agent_id=agent_id,
                root=timeline_path.parent,
                timeline_path=timeline_path,
                events_path=timeline_path.parent / "identity-events.jsonl",
            )
            if agent_id in sources and sources[agent_id].timeline_path != timeline_path:
                raise DuplicateAgentTimelineError(
                    f"multiple timeline bundles claim agent {agent_id!r}"
                )
            sources[agent_id] = source
        return tuple(sources[key] for key in sorted(sources))

    def get_source(self, agent_id: str) -> TimelineSource:
        source = next(
            (item for item in self.list_sources() if item.agent_id == agent_id),
            None,
        )
        if source is None:
            raise TimelineNotFoundError(f"identity timeline not found: {agent_id}")
        return source

    def load_snapshot(self, agent_id: str) -> TimelineSnapshot:
        source = self.get_source(agent_id)
        persisted = _read_json_object(source.timeline_path)
        findings: list[Mapping[str, Any]] = []
        events: tuple[Mapping[str, Any], ...] = ()
        replayed: Mapping[str, Any] = {}

        persisted_digest_valid = _verify_persisted_timeline_digest(persisted)
        if not persisted_digest_valid:
            findings.append(
                _api_finding(
                    "TIMELINE_DIGEST_MISMATCH",
                    "persisted identity-timeline.json digest is invalid",
                )
            )

        if not source.events_path.exists():
            findings.append(
                _api_finding(
                    "EVENT_STORE_MISSING",
                    "identity-events.jsonl is missing",
                )
            )
        else:
            store = JsonlEventStoreAdapter(source.events_path)
            trail_id = str(persisted.get("trail_id", ""))
            scan = store.scan(trail_id)
            if scan.findings:
                findings.extend(_store_finding(item) for item in scan.findings)
                events = tuple(event.to_dict() for event in scan.events)
            else:
                events = tuple(event.to_dict() for event in scan.events)
                try:
                    projection = scan_identity_timeline(store, agent_id=agent_id)
                    replayed = projection.to_dict()
                    findings.extend(item.to_dict() for item in projection.findings)
                except EventStoreCorruptionError as error:
                    findings.extend(_store_finding(item) for item in error.findings)
                except Exception as error:  # fail closed at the product boundary
                    findings.append(
                        _api_finding(
                            "REPLAY_FAILED",
                            f"identity timeline replay failed: {error}",
                        )
                    )

        if replayed and replayed != persisted:
            findings.append(
                _api_finding(
                    "PERSISTED_PROJECTION_MISMATCH",
                    "persisted timeline differs from deterministic replay",
                )
            )

        valid = not findings and bool(replayed)
        timeline = replayed or persisted
        return TimelineSnapshot(
            agent_id=agent_id,
            valid=valid,
            integrity_status="VALID" if valid else "INVALID",
            timeline=timeline,
            persisted_timeline=persisted,
            events=events,
            findings=tuple(findings),
            source=source,
        )


class IdentityTimelineReadOnlyAPI:
    """Pure request router with no mutation operations."""

    allowed_methods = ("GET", "HEAD")

    def __init__(self, repository: DirectoryIdentityTimelineRepository) -> None:
        self.repository = repository

    def handle(
        self,
        method: str,
        path: str,
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        normalized_method = method.upper()
        if normalized_method not in self.allowed_methods:
            return self._json(
                405,
                {
                    "error": "method_not_allowed",
                    "message": "Identity Timeline API is read-only.",
                    "allowed_methods": list(self.allowed_methods),
                },
                extra_headers=(("Allow", "GET, HEAD"),),
            )

        segments = [unquote(segment) for segment in path.split("/") if segment]
        try:
            if segments == ["api", "v1", "health"]:
                response = self._health()
            elif segments == ["api", "v1", "agents"]:
                response = self._agents()
            elif len(segments) >= 4 and segments[:3] == ["api", "v1", "agents"]:
                response = self._agent_route(segments[3], segments[4:])
            else:
                response = self._json(
                    404,
                    {"error": "not_found", "message": "Route not found."},
                )
        except TimelineNotFoundError as error:
            response = self._json(
                404,
                {"error": "timeline_not_found", "message": str(error)},
            )
        except DuplicateAgentTimelineError as error:
            response = self._json(
                409,
                {"error": "duplicate_agent_timeline", "message": str(error)},
            )
        except Exception as error:  # stable fail-closed JSON response
            response = self._json(
                500,
                {"error": "timeline_api_failure", "message": str(error)},
            )

        if normalized_method == "HEAD":
            return response[0], response[1], b"", response[3]
        return response

    def _health(self) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        sources = self.repository.list_sources()
        invalid = 0
        for source in sources:
            if not self.repository.load_snapshot(source.agent_id).valid:
                invalid += 1
        return self._json(
            200,
            {
                "schema_version": IDENTITY_TIMELINE_API_VERSION,
                "status": "ok" if invalid == 0 else "degraded",
                "read_only": True,
                "agent_count": len(sources),
                "invalid_timeline_count": invalid,
            },
        )

    def _agents(self) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        agents = []
        for source in self.repository.list_sources():
            snapshot = self.repository.load_snapshot(source.agent_id)
            timeline = snapshot.timeline
            agents.append(
                {
                    "agent_id": source.agent_id,
                    "status": timeline.get("status"),
                    "integrity_status": snapshot.integrity_status,
                    "active_profile_version": (
                        timeline.get("active_profile", {}).get("version")
                        if snapshot.valid
                        else None
                    ),
                    "timeline_url": _agent_url(source.agent_id, "timeline"),
                }
            )
        return self._json(
            200,
            {
                "schema_version": IDENTITY_TIMELINE_API_VERSION,
                "read_only": True,
                "agents": agents,
            },
        )

    def _agent_route(
        self,
        agent_id: str,
        remainder: Sequence[str],
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        snapshot = self.repository.load_snapshot(agent_id)
        if not remainder:
            return self._json(200, self._agent_summary(snapshot))
        if remainder == ["timeline"]:
            return self._json(200, self._timeline_response(snapshot))
        if remainder == ["profiles"]:
            return self._json(200, self._profiles_response(snapshot))
        if remainder == ["findings"]:
            return self._json(
                200,
                {
                    "schema_version": IDENTITY_TIMELINE_API_VERSION,
                    "agent_id": agent_id,
                    "integrity_status": snapshot.integrity_status,
                    "findings": list(snapshot.findings),
                },
            )
        if len(remainder) == 2 and remainder[0] == "events":
            event_ref = remainder[1]
            event = snapshot.event_by_ref(event_ref)
            if event is None:
                return self._json(
                    404,
                    {"error": "event_not_found", "message": event_ref},
                )
            return self._json(
                200,
                {
                    "schema_version": IDENTITY_TIMELINE_API_VERSION,
                    "agent_id": agent_id,
                    "read_only": True,
                    "event": event,
                },
            )
        if remainder == ["evidence", "identity-timeline.json"]:
            return self._file(
                snapshot.source.timeline_path,
                "application/json",
                attachment_name="identity-timeline.json",
            )
        if remainder == ["evidence", "identity-events.jsonl"]:
            if not snapshot.source.events_path.exists():
                return self._json(
                    404,
                    {"error": "evidence_not_found", "message": "events file missing"},
                )
            return self._file(
                snapshot.source.events_path,
                "application/x-ndjson",
                attachment_name="identity-events.jsonl",
            )
        return self._json(
            404,
            {"error": "not_found", "message": "Agent route not found."},
        )

    def _agent_summary(self, snapshot: TimelineSnapshot) -> Mapping[str, Any]:
        timeline = snapshot.timeline
        authoritative_profile = timeline.get("active_profile") if snapshot.valid else None
        return {
            "schema_version": IDENTITY_TIMELINE_API_VERSION,
            "read_only": True,
            "agent_id": snapshot.agent_id,
            "integrity_status": snapshot.integrity_status,
            "authoritative": snapshot.valid,
            "status": timeline.get("status"),
            "active_profile": authoritative_profile,
            "observed_active_profile": timeline.get("active_profile"),
            "profile_version_count": len(timeline.get("profile_versions", ())),
            "event_count": len(snapshot.events),
            "finding_count": len(snapshot.findings),
            "links": _links(snapshot.agent_id),
        }

    def _timeline_response(self, snapshot: TimelineSnapshot) -> Mapping[str, Any]:
        timeline = dict(snapshot.timeline)
        enriched_events = []
        for event in timeline.get("events", ()):
            item = dict(event)
            event_ref = str(item.get("event_ref", ""))
            item["source_record_url"] = _agent_url(
                snapshot.agent_id,
                "events",
                event_ref,
            )
            enriched_events.append(item)
        timeline["events"] = enriched_events
        return {
            "schema_version": IDENTITY_TIMELINE_API_VERSION,
            "read_only": True,
            "agent_id": snapshot.agent_id,
            "integrity_status": snapshot.integrity_status,
            "authoritative": snapshot.valid,
            "active_profile": (
                timeline.get("active_profile") if snapshot.valid else None
            ),
            "observed_active_profile": timeline.get("active_profile"),
            "timeline": timeline,
            "findings": list(snapshot.findings),
            "links": _links(snapshot.agent_id),
        }

    def _profiles_response(self, snapshot: TimelineSnapshot) -> Mapping[str, Any]:
        versions = [dict(item) for item in snapshot.timeline.get("profile_versions", ())]
        previous: Optional[Mapping[str, Any]] = None
        enriched = []
        for profile in versions:
            item = dict(profile)
            item["trait_changes"] = _trait_changes(previous, profile)
            item["authoritative"] = snapshot.valid and profile is versions[-1]
            enriched.append(item)
            previous = profile
        return {
            "schema_version": IDENTITY_TIMELINE_API_VERSION,
            "read_only": True,
            "agent_id": snapshot.agent_id,
            "integrity_status": snapshot.integrity_status,
            "profiles": enriched,
        }

    @staticmethod
    def _json(
        status: int,
        payload: Mapping[str, Any],
        *,
        extra_headers: Sequence[tuple[str, str]] = (),
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        body = (
            json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        headers = (
            ("Content-Type", JSON_CONTENT_TYPE),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"),
            *extra_headers,
        )
        return status, _status_text(status), body, tuple(headers)

    @staticmethod
    def _file(
        path: Path,
        content_type: str,
        *,
        attachment_name: str,
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        body = path.read_bytes()
        return (
            200,
            "OK",
            body,
            (
                ("Content-Type", content_type),
                ("Content-Disposition", f'attachment; filename="{attachment_name}"'),
                ("Cache-Control", "no-store"),
                ("X-Content-Type-Options", "nosniff"),
            ),
        )


class IdentityTimelineWSGIApplication:
    """WSGI app serving the read-only API and static dashboard assets."""

    def __init__(
        self,
        api: IdentityTimelineReadOnlyAPI,
        *,
        asset_root: Optional[Path] = None,
    ) -> None:
        self.api = api
        self.asset_root = asset_root or Path(__file__).with_name("identity_dashboard")

    def __call__(self, environ: Mapping[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET"))
        path = str(environ.get("PATH_INFO", "/"))
        if path.startswith("/api/"):
            status, reason, body, headers = self.api.handle(method, path)
        else:
            status, reason, body, headers = self._static(method, path)
        response_headers = list(headers)
        response_headers.append(("Content-Length", str(len(body))))
        start_response(f"{status} {reason}", response_headers)
        return (body,)

    def _static(
        self,
        method: str,
        path: str,
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        if method.upper() not in ("GET", "HEAD"):
            return self.api._json(
                405,
                {
                    "error": "method_not_allowed",
                    "message": "Dashboard is read-only.",
                },
                extra_headers=(("Allow", "GET, HEAD"),),
            )
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        candidate = (self.asset_root / relative).resolve()
        root = self.asset_root.resolve()
        if root not in candidate.parents and candidate != root:
            return self.api._json(404, {"error": "not_found"})
        if not candidate.exists() or not candidate.is_file():
            return self.api._json(404, {"error": "not_found"})
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        body = b"" if method.upper() == "HEAD" else candidate.read_bytes()
        csp = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        return (
            200,
            "OK",
            body,
            (
                ("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else "")),
                ("Cache-Control", "no-store"),
                ("Content-Security-Policy", csp),
                ("X-Content-Type-Options", "nosniff"),
                ("Referrer-Policy", "no-referrer"),
            ),
        )


def build_identity_timeline_wsgi_app(
    data_root: Path,
    *,
    asset_root: Optional[Path] = None,
) -> IdentityTimelineWSGIApplication:
    repository = DirectoryIdentityTimelineRepository(data_root)
    return IdentityTimelineWSGIApplication(
        IdentityTimelineReadOnlyAPI(repository),
        asset_root=asset_root,
    )


def _verify_persisted_timeline_digest(payload: Mapping[str, Any]) -> bool:
    integrity = payload.get("integrity")
    if not isinstance(integrity, Mapping):
        return False
    expected = integrity.get("timeline_digest")
    unsigned = dict(payload)
    unsigned.pop("integrity", None)
    return expected == digest_json(unsigned)


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _store_finding(finding: StoreFinding) -> Mapping[str, Any]:
    return {
        "code": finding.code,
        "message": finding.message,
        "line_number": finding.line_number,
        "event_ref": finding.event_ref,
        "source": "durable_event_store",
    }


def _api_finding(code: str, message: str) -> Mapping[str, Any]:
    return {"code": code, "message": message, "source": "timeline_api"}


def _trait_changes(
    previous: Optional[Mapping[str, Any]],
    current: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    previous_traits = dict(previous.get("traits", {})) if previous else {}
    current_traits = dict(current.get("traits", {}))
    changes = []
    for key in sorted(set(previous_traits) | set(current_traits)):
        before = previous_traits.get(key)
        after = current_traits.get(key)
        if before != after:
            changes.append({"key": key, "before": before, "after": after})
    return changes


def _agent_url(agent_id: str, *parts: str) -> str:
    encoded_parts = [quote(agent_id, safe=""), *(quote(part, safe="") for part in parts)]
    return "/api/v1/agents/" + "/".join(encoded_parts)


def _links(agent_id: str) -> Mapping[str, str]:
    base = _agent_url(agent_id)
    return {
        "self": base,
        "timeline": base + "/timeline",
        "profiles": base + "/profiles",
        "findings": base + "/findings",
        "timeline_evidence": base + "/evidence/identity-timeline.json",
        "events_evidence": base + "/evidence/identity-events.jsonl",
    }


def _status_text(status: int) -> str:
    return {
        200: "OK",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        500: "Internal Server Error",
    }.get(status, "OK")


__all__ = [
    "DirectoryIdentityTimelineRepository",
    "IdentityTimelineReadOnlyAPI",
    "IdentityTimelineWSGIApplication",
    "TimelineSnapshot",
    "build_identity_timeline_wsgi_app",
]
