"""Exact-head artifact acquisition for immutable review evidence bundles."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, Sequence

_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SCHEMA_VERSION = "ls.exact_head_evidence_bundle.v0.1"
_MANIFEST_VERSION = "ls.exact_head_acquisition_manifest.v0.1"


def _require_sha1(value: str, field_name: str) -> str:
    if not isinstance(value, str) or _SHA1_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a lowercase 40-character Git SHA")
    return value


def normalize_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("artifact path must be a non-empty string")
    if "\\" in value or value.startswith("/") or value.endswith("/") or "//" in value:
        raise ValueError(f"artifact path is not canonical: {value!r}")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"artifact path escapes or aliases the repository: {value!r}")
    normalized = path.as_posix()
    if normalized != value:
        raise ValueError(f"artifact path is not canonical: {value!r}")
    return normalized


@dataclass(frozen=True)
class PullRequestSnapshot:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    changed_file_count: int


@dataclass(frozen=True)
class FetchedArtifact:
    path: str
    git_blob_sha: str
    content: bytes


@dataclass(frozen=True)
class RelatedArtifactAdmission:
    source_path: str
    path: str
    relation: str
    evidence: str

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "RelatedArtifactAdmission":
        if not isinstance(value, dict):
            raise ValueError("related artifact admission must be an object")
        relation = value.get("relation")
        evidence = value.get("evidence")
        if not isinstance(relation, str) or not relation.strip():
            raise ValueError("related artifact relation is required")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError("related artifact evidence is required")
        return cls(
            source_path=normalize_repo_path(value.get("source_path")),
            path=normalize_repo_path(value.get("path")),
            relation=relation.strip(),
            evidence=evidence.strip(),
        )


@dataclass(frozen=True)
class AcquisitionManifest:
    repository: str
    pr_number: int
    expected_base_sha: str
    expected_head_sha: str
    expected_changed_file_count: int
    artifact_paths: tuple[str, ...]
    related_artifacts: tuple[RelatedArtifactAdmission, ...]
    selection_mode: str
    max_file_bytes: int
    max_total_bytes: int

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AcquisitionManifest":
        if not isinstance(value, dict):
            raise ValueError("manifest must be an object")
        if value.get("schema_version") != _MANIFEST_VERSION:
            raise ValueError(f"manifest schema_version must be {_MANIFEST_VERSION}")
        repository = value.get("repository")
        if not isinstance(repository, str) or _REPOSITORY_RE.fullmatch(repository) is None:
            raise ValueError("repository must use owner/name form")
        pr_number = value.get("pr_number")
        if not isinstance(pr_number, int) or isinstance(pr_number, bool) or pr_number <= 0:
            raise ValueError("pr_number must be a positive integer")
        expected_changed_file_count = value.get("expected_changed_file_count")
        if (
            not isinstance(expected_changed_file_count, int)
            or isinstance(expected_changed_file_count, bool)
            or expected_changed_file_count <= 0
        ):
            raise ValueError("expected_changed_file_count must be a positive integer")

        raw_paths = value.get("artifact_paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            raise ValueError("artifact_paths must be a non-empty array")
        artifact_paths = tuple(normalize_repo_path(path) for path in raw_paths)

        raw_related = value.get("related_artifacts", [])
        if not isinstance(raw_related, list):
            raise ValueError("related_artifacts must be an array")
        related = tuple(RelatedArtifactAdmission.from_dict(item) for item in raw_related)

        selected = list(artifact_paths) + [item.path for item in related]
        if len(selected) != len(set(selected)):
            raise ValueError("artifact paths must be unique across direct and related admissions")

        selection_mode = value.get("selection_mode")
        if selection_mode not in {"ALL_CHANGED", "DECLARED_SUBSET"}:
            raise ValueError("selection_mode must be ALL_CHANGED or DECLARED_SUBSET")

        max_file_bytes = value.get("max_file_bytes", 200_000)
        max_total_bytes = value.get("max_total_bytes", 2_000_000)
        for name, limit in (
            ("max_file_bytes", max_file_bytes),
            ("max_total_bytes", max_total_bytes),
        ):
            if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if max_file_bytes > max_total_bytes:
            raise ValueError("max_file_bytes cannot exceed max_total_bytes")

        return cls(
            repository=repository,
            pr_number=pr_number,
            expected_base_sha=_require_sha1(value.get("expected_base_sha"), "expected_base_sha"),
            expected_head_sha=_require_sha1(value.get("expected_head_sha"), "expected_head_sha"),
            expected_changed_file_count=expected_changed_file_count,
            artifact_paths=artifact_paths,
            related_artifacts=related,
            selection_mode=selection_mode,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
        )


@dataclass(frozen=True)
class EvidenceArtifact:
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    path: str
    git_blob_sha: str
    content_sha256: str
    byte_length: int
    content: str
    admission: str
    relation: str | None = None
    relation_source_path: str | None = None
    relation_evidence: str | None = None


@dataclass(frozen=True)
class ExactHeadEvidenceBundle:
    schema_version: str
    repository: str
    pr_number: int
    base_sha: str
    head_sha: str
    changed_file_count: int
    selection_mode: str
    artifacts: tuple[EvidenceArtifact, ...]
    evidence_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AcquisitionClient(Protocol):
    def get_pull_request(self, repository: str, pr_number: int) -> PullRequestSnapshot:
        ...

    def list_changed_paths(
        self, repository: str, base_sha: str, head_sha: str
    ) -> Sequence[str]:
        ...

    def fetch_artifact(self, repository: str, head_sha: str, path: str) -> FetchedArtifact:
        ...


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def acquire_exact_head_bundle(
    manifest: AcquisitionManifest,
    client: AcquisitionClient,
) -> ExactHeadEvidenceBundle:
    pr = client.get_pull_request(manifest.repository, manifest.pr_number)
    if pr.repository != manifest.repository or pr.pr_number != manifest.pr_number:
        raise ValueError("pull request identity mismatch")
    _require_sha1(pr.base_sha, "live base_sha")
    _require_sha1(pr.head_sha, "live head_sha")
    if (
        not isinstance(pr.changed_file_count, int)
        or isinstance(pr.changed_file_count, bool)
        or pr.changed_file_count < 0
    ):
        raise ValueError("live changed_file_count must be a non-negative integer")
    if pr.changed_file_count != manifest.expected_changed_file_count:
        raise ValueError(
            "changed-file count drift: "
            f"expected {manifest.expected_changed_file_count}, "
            f"observed {pr.changed_file_count}"
        )
    if pr.base_sha != manifest.expected_base_sha:
        raise ValueError(
            f"base SHA drift: expected {manifest.expected_base_sha}, observed {pr.base_sha}"
        )
    if pr.head_sha != manifest.expected_head_sha:
        raise ValueError(
            f"head SHA drift: expected {manifest.expected_head_sha}, observed {pr.head_sha}"
        )

    changed_paths = {
        normalize_repo_path(path)
        for path in client.list_changed_paths(
            manifest.repository,
            manifest.expected_base_sha,
            manifest.expected_head_sha,
        )
    }
    if len(changed_paths) != pr.changed_file_count:
        raise ValueError(
            "changed-file listing is incomplete or duplicated: "
            f"metadata={pr.changed_file_count}, listed={len(changed_paths)}"
        )
    for path in manifest.artifact_paths:
        if path not in changed_paths:
            raise ValueError(f"direct artifact is not changed on the exact PR head: {path}")

    direct_paths = set(manifest.artifact_paths)
    if manifest.selection_mode == "ALL_CHANGED" and direct_paths != changed_paths:
        omitted = sorted(changed_paths - direct_paths)
        undeclared = sorted(direct_paths - changed_paths)
        raise ValueError(
            f"ALL_CHANGED selection mismatch: omitted={omitted}, undeclared={undeclared}"
        )

    related_by_path: dict[str, RelatedArtifactAdmission] = {}
    for admission in manifest.related_artifacts:
        if admission.source_path not in direct_paths:
            raise ValueError(
                f"related artifact source must be a directly changed artifact: {admission.source_path}"
            )
        if admission.path in changed_paths:
            raise ValueError(
                f"changed artifact cannot be admitted as RELATED: {admission.path}"
            )
        related_by_path[admission.path] = admission

    artifacts: list[EvidenceArtifact] = []
    total_bytes = 0
    for path in sorted(direct_paths | set(related_by_path)):
        fetched = client.fetch_artifact(
            manifest.repository,
            manifest.expected_head_sha,
            path,
        )
        if normalize_repo_path(fetched.path) != path:
            raise ValueError(f"fetched path mismatch: expected {path}, observed {fetched.path}")
        _require_sha1(fetched.git_blob_sha, f"{path} git_blob_sha")
        if not isinstance(fetched.content, bytes):
            raise ValueError(f"{path}: fetched content must be bytes")
        byte_length = len(fetched.content)
        if byte_length > manifest.max_file_bytes:
            raise ValueError(
                f"{path}: {byte_length} bytes exceeds max_file_bytes={manifest.max_file_bytes}"
            )
        total_bytes += byte_length
        if total_bytes > manifest.max_total_bytes:
            raise ValueError(
                f"bundle exceeds max_total_bytes={manifest.max_total_bytes}"
            )
        try:
            text = fetched.content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path}: artifact is not valid UTF-8") from exc

        admission = related_by_path.get(path)
        artifacts.append(
            EvidenceArtifact(
                repository=manifest.repository,
                pr_number=manifest.pr_number,
                base_sha=manifest.expected_base_sha,
                head_sha=manifest.expected_head_sha,
                path=path,
                git_blob_sha=fetched.git_blob_sha,
                content_sha256=hashlib.sha256(fetched.content).hexdigest(),
                byte_length=byte_length,
                content=text,
                admission="RELATED" if admission else "CHANGED",
                relation=admission.relation if admission else None,
                relation_source_path=admission.source_path if admission else None,
                relation_evidence=admission.evidence if admission else None,
            )
        )

    final_pr = client.get_pull_request(manifest.repository, manifest.pr_number)
    if (
        final_pr.repository != manifest.repository
        or final_pr.pr_number != manifest.pr_number
        or final_pr.base_sha != manifest.expected_base_sha
        or final_pr.head_sha != manifest.expected_head_sha
        or final_pr.changed_file_count != manifest.expected_changed_file_count
    ):
        raise ValueError("pull request changed during acquisition")

    evidence = {
        "schema_version": _SCHEMA_VERSION,
        "repository": manifest.repository,
        "pr_number": manifest.pr_number,
        "base_sha": manifest.expected_base_sha,
        "head_sha": manifest.expected_head_sha,
        "changed_file_count": manifest.expected_changed_file_count,
        "selection_mode": manifest.selection_mode,
        "artifacts": [asdict(item) for item in artifacts],
    }
    evidence_sha256 = hashlib.sha256(_canonical_bytes(evidence)).hexdigest()
    return ExactHeadEvidenceBundle(
        schema_version=_SCHEMA_VERSION,
        repository=manifest.repository,
        pr_number=manifest.pr_number,
        base_sha=manifest.expected_base_sha,
        head_sha=manifest.expected_head_sha,
        changed_file_count=manifest.expected_changed_file_count,
        selection_mode=manifest.selection_mode,
        artifacts=tuple(artifacts),
        evidence_sha256=evidence_sha256,
    )


class _RejectRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Fail closed instead of forwarding authorization across redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class GitHubRestClient:
    """Read-only GitHub REST client that fetches file content by exact commit SHA."""

    def __init__(
        self,
        *,
        token: str | None = None,
        api_url: str = "https://api.github.com",
        timeout_seconds: int = 30,
        opener: Any | None = None,
    ) -> None:
        parsed = urllib.parse.urlparse(api_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("api_url must be an absolute HTTPS URL")
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        self._opener = opener or urllib.request.build_opener(_RejectRedirectHandler())

    def _request_json(self, path: str) -> Any:
        url = f"{self.api_url}{path}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ls-exact-head-evidence-acquisition-v0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(
                f"GitHub API HTTP {exc.code} for {path}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(
                f"GitHub API transport failure for {path} "
                f"(timeout={self.timeout_seconds}s): {type(exc).__name__}"
            ) from exc
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"GitHub API returned non-UTF-8 data for {path}") from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GitHub API returned invalid JSON for {path}") from exc

    def get_pull_request(self, repository: str, pr_number: int) -> PullRequestSnapshot:
        value = self._request_json(f"/repos/{repository}/pulls/{pr_number}")
        return PullRequestSnapshot(
            repository=repository,
            pr_number=pr_number,
            base_sha=value["base"]["sha"],
            head_sha=value["head"]["sha"],
            changed_file_count=value["changed_files"],
        )

    def list_changed_paths(
        self, repository: str, base_sha: str, head_sha: str
    ) -> Sequence[str]:
        _require_sha1(base_sha, "base_sha")
        _require_sha1(head_sha, "head_sha")
        value = self._request_json(
            f"/repos/{repository}/compare/{base_sha}...{head_sha}"
        )
        if not isinstance(value, dict) or not isinstance(value.get("files"), list):
            raise RuntimeError("GitHub compare response must contain a files array")
        return [item["filename"] for item in value["files"]]

    def fetch_artifact(self, repository: str, head_sha: str, path: str) -> FetchedArtifact:
        _require_sha1(head_sha, "head_sha")
        normalized = normalize_repo_path(path)
        encoded_path = urllib.parse.quote(normalized, safe="/")
        encoded_ref = urllib.parse.quote(head_sha, safe="")
        value = self._request_json(
            f"/repos/{repository}/contents/{encoded_path}?ref={encoded_ref}"
        )
        if value.get("type") != "file" or value.get("encoding") != "base64":
            raise RuntimeError(f"{normalized}: GitHub contents response is not a base64 file")
        returned_path = normalize_repo_path(value.get("path"))
        try:
            encoded_content = "".join(value["content"].split())
            content = base64.b64decode(encoded_content, validate=True)
        except (KeyError, AttributeError, ValueError) as exc:
            raise RuntimeError(f"{normalized}: invalid base64 content response") from exc
        return FetchedArtifact(
            path=returned_path,
            git_blob_sha=value["sha"],
            content=content,
        )


def load_manifest(path: Path) -> AcquisitionManifest:
    value = json.loads(path.read_text(encoding="utf-8"))
    return AcquisitionManifest.from_dict(value)


def write_bundle(path: Path, bundle: ExactHeadEvidenceBundle) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(bundle.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def run_cli(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Acquire an immutable exact-head evidence bundle from GitHub."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--github-token-env",
        default="GITHUB_TOKEN",
        help="environment variable containing a read-only GitHub token",
    )
    args = parser.parse_args(argv)

    if args.manifest_root is not None:
        manifest_path = args.manifest.resolve()
        manifest_root = args.manifest_root.resolve()
        try:
            manifest_path.relative_to(manifest_root)
        except ValueError as exc:
            raise ValueError("manifest must be located under --manifest-root") from exc
    manifest = load_manifest(args.manifest)
    client = GitHubRestClient(token=os.environ.get(args.github_token_env))
    bundle = acquire_exact_head_bundle(manifest, client)
    write_bundle(args.output, bundle)
    print(
        f"evidence_sha256={bundle.evidence_sha256} "
        f"artifacts={len(bundle.artifacts)} head_sha={bundle.head_sha}"
    )
    return 0
