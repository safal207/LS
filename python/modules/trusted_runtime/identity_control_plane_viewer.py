"""Read-only Identity Control Plane status layered onto the timeline viewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import unquote

from .identity_catalog_publisher import (
    CatalogPublicationIntegrityError,
    load_published_identity_catalog,
)
from .identity_live_viewer import (
    CatalogIdentityTimelineRepository,
    SignedCatalogIdentityTimelineAPI,
    SignedCatalogIdentityTimelineWSGIApplication,
)
from .persistence import digest_json


CONTROL_PLANE_STATUS_VERSION = "trusted_runtime.identity_control_plane_status.v0.1"


class IdentityControlPlaneStatusRepository:
    """Verify publication and trigger metadata without mutating runtime state."""

    def __init__(
        self,
        publisher_root: Path,
        trigger_root: Path,
        *,
        keyring: Mapping[str, bytes],
        acceptance_manifest_path: Optional[Path] = None,
    ) -> None:
        self.publisher_root = Path(publisher_root)
        self.trigger_root = Path(trigger_root)
        self.keyring = {str(key): bytes(value) for key, value in keyring.items()}
        self.acceptance_manifest_path = (
            Path(acceptance_manifest_path) if acceptance_manifest_path else None
        )

    def status(self) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        state = self._read_optional(
            self.trigger_root / "identity-catalog-trigger-state.json",
            findings,
            code="TRIGGER_STATE_UNAVAILABLE",
        )
        health = self._read_optional(
            self.trigger_root / "identity-catalog-trigger-health.json",
            findings,
            code="TRIGGER_HEALTH_UNAVAILABLE",
        )
        batch = self._read_optional(
            self.trigger_root / "identity-catalog-trigger-generation.json",
            findings,
            code="TRIGGER_BATCH_UNAVAILABLE",
        )
        minimum_generation = (
            int(state["last_generation"])
            if state and state.get("last_generation") is not None
            else None
        )
        publication = None
        try:
            publication = load_published_identity_catalog(
                self.publisher_root / "identity-catalog-publication.json",
                keyring=self.keyring,
                minimum_generation=minimum_generation,
            )
        except (
            OSError,
            ValueError,
            KeyError,
            CatalogPublicationIntegrityError,
        ) as error:
            findings.append(
                {
                    "code": "PUBLICATION_INTEGRITY_FAILURE",
                    "message": str(error),
                    "source": "identity_catalog_publication",
                }
            )

        if batch:
            unsigned = dict(batch)
            integrity = unsigned.pop("integrity", None)
            expected = (
                integrity.get("trigger_batch_digest")
                if isinstance(integrity, Mapping)
                else None
            )
            if expected != digest_json(unsigned):
                findings.append(
                    {
                        "code": "TRIGGER_BATCH_DIGEST_MISMATCH",
                        "message": "trigger generation metadata digest is invalid",
                        "source": "identity_catalog_trigger",
                    }
                )

        if publication and state:
            if state.get("last_generation") != publication.generation:
                findings.append(
                    {
                        "code": "GENERATION_CHECKPOINT_MISMATCH",
                        "message": "trigger checkpoint generation differs from publication",
                        "source": "identity_catalog_trigger",
                    }
                )
            if state.get("last_publication_digest") != publication.publication_digest:
                findings.append(
                    {
                        "code": "PUBLICATION_CHECKPOINT_MISMATCH",
                        "message": "trigger checkpoint digest differs from publication",
                        "source": "identity_catalog_trigger",
                    }
                )
        if publication and batch:
            if batch.get("generation") != publication.generation:
                findings.append(
                    {
                        "code": "TRIGGER_GENERATION_MISMATCH",
                        "message": "latest trigger batch does not match publication generation",
                        "source": "identity_catalog_trigger",
                    }
                )
            if batch.get("publication_digest") != publication.publication_digest:
                findings.append(
                    {
                        "code": "TRIGGER_PUBLICATION_DIGEST_MISMATCH",
                        "message": "trigger batch publication digest does not match",
                        "source": "identity_catalog_trigger",
                    }
                )

        authoritative = publication is not None and not findings
        return {
            "schema_version": CONTROL_PLANE_STATUS_VERSION,
            "read_only": True,
            "integrity_status": "VALID" if authoritative else "INVALID",
            "authoritative": authoritative,
            "generation": publication.generation if publication else None,
            "publication_digest": (
                publication.publication_digest if publication else None
            ),
            "previous_publication_digest": (
                publication.previous_publication_digest if publication else None
            ),
            "active_key_id": publication.active_key_id if publication else None,
            "accepted_key_ids": (
                list(publication.accepted_key_ids) if publication else []
            ),
            "agent_count": len(publication.entries) if publication else 0,
            "authoritative_agent_count": (
                sum(1 for item in publication.entries if item.authoritative)
                if publication
                else 0
            ),
            "trigger": {
                "request_ids": list(batch.get("request_ids", ())) if batch else [],
                "tail_event_refs": (
                    list(batch.get("trigger_tail_event_refs", ())) if batch else []
                ),
                "agent_ids": list(batch.get("agent_ids", ())) if batch else [],
                "outbox_sequences": (
                    list(batch.get("outbox_sequences", ())) if batch else []
                ),
                "processed_at": batch.get("processed_at") if batch else None,
            },
            "health": {
                "publisher_lag_seconds": (
                    health.get("publisher_lag_seconds") if health else None
                ),
                "pending_request_count": (
                    health.get("pending_request_count") if health else None
                ),
                "quarantined_request_count": (
                    health.get("quarantined_request_count") if health else None
                ),
                "pending_request_ids": (
                    list(health.get("pending_request_ids", ())) if health else []
                ),
                "quarantined": list(health.get("quarantined", ())) if health else [],
                "last_successful_generation": (
                    health.get("last_successful_generation") if health else None
                ),
            },
            "findings": findings,
            "links": {
                "acceptance_manifest": (
                    "/api/v1/control-plane/evidence/acceptance-manifest.json"
                    if self.acceptance_manifest_path
                    else None
                )
            },
        }

    def acceptance_manifest(self) -> Optional[dict[str, Any]]:
        if self.acceptance_manifest_path is None:
            return None
        payload = json.loads(self.acceptance_manifest_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("acceptance manifest must be a JSON object")
        return payload

    @staticmethod
    def _read_optional(
        path: Path,
        findings: list[dict[str, Any]],
        *,
        code: str,
    ) -> Optional[dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("expected a JSON object")
            return payload
        except (OSError, ValueError, json.JSONDecodeError) as error:
            findings.append(
                {
                    "code": code,
                    "message": str(error),
                    "source": path.name,
                }
            )
            return None


class IdentityControlPlaneReadOnlyAPI(SignedCatalogIdentityTimelineAPI):
    """Expose verified control-plane status alongside existing read-only routes."""

    def __init__(
        self,
        timeline_repository: CatalogIdentityTimelineRepository,
        status_repository: IdentityControlPlaneStatusRepository,
    ) -> None:
        super().__init__(timeline_repository)
        self.status_repository = status_repository

    def handle_live(
        self,
        method: str,
        path: str,
        *,
        query_string: str = "",
        if_none_match: Optional[str] = None,
    ) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
        normalized = method.upper()
        if normalized not in self.allowed_methods:
            return super().handle_live(
                normalized,
                path,
                query_string=query_string,
                if_none_match=if_none_match,
            )
        segments = [unquote(segment) for segment in path.split("/") if segment]
        if segments == ["api", "v1", "control-plane", "status"]:
            response = self._json(200, self.status_repository.status())
            return _head_if_needed(normalized, response)
        if segments == [
            "api",
            "v1",
            "control-plane",
            "evidence",
            "acceptance-manifest.json",
        ]:
            manifest = self.status_repository.acceptance_manifest()
            if manifest is None:
                response = self._json(
                    404,
                    {
                        "error": "acceptance_manifest_not_found",
                        "message": "Acceptance manifest is not configured.",
                    },
                )
            else:
                response = self._json(200, manifest)
            return _head_if_needed(normalized, response)
        return super().handle_live(
            normalized,
            path,
            query_string=query_string,
            if_none_match=if_none_match,
        )


def build_identity_control_plane_viewer(
    data_root: Path,
    catalog_path: Path,
    publisher_root: Path,
    trigger_root: Path,
    *,
    catalog_secret: bytes,
    publication_keyring: Mapping[str, bytes],
    acceptance_manifest_path: Optional[Path] = None,
    asset_root: Optional[Path] = None,
) -> SignedCatalogIdentityTimelineWSGIApplication:
    timeline_repository = CatalogIdentityTimelineRepository(
        data_root,
        catalog_path,
        secret=catalog_secret,
    )
    status_repository = IdentityControlPlaneStatusRepository(
        publisher_root,
        trigger_root,
        keyring=publication_keyring,
        acceptance_manifest_path=acceptance_manifest_path,
    )
    api = IdentityControlPlaneReadOnlyAPI(
        timeline_repository,
        status_repository,
    )
    return SignedCatalogIdentityTimelineWSGIApplication(api, asset_root=asset_root)


def _head_if_needed(
    method: str,
    response: tuple[int, str, bytes, tuple[tuple[str, str], ...]],
) -> tuple[int, str, bytes, tuple[tuple[str, str], ...]]:
    if method == "HEAD":
        return response[0], response[1], b"", response[3]
    return response


__all__ = [
    "IdentityControlPlaneReadOnlyAPI",
    "IdentityControlPlaneStatusRepository",
    "build_identity_control_plane_viewer",
]
