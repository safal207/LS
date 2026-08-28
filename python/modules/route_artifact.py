"""Deterministic Route Artifact v2 verification and registry projection."""

from __future__ import annotations

import contextlib
import copy
import hashlib
import heapq
import io
import json
import math
import os
import re
import shlex
import subprocess
import tarfile
import tempfile
import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

API_VERSION = "ls.route/v2"
KIND = "RouteArtifact"
STATUSES = {"draft", "experimental", "candidate", "validated", "deprecated", "revoked"}
TIERS = {"T0_deterministic_replay", "T1_artifact_attested", "T2_narrative_only"}
CAPABILITIES = {"frontier", "mid", "small", "open_weight", "human", "deterministic_tool"}
RISKS = {"low", "medium", "high", "critical"}

DEFAULT_PROMOTION_THRESHOLDS_PATH = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "route_artifact_v2_promotion_thresholds.json"
)
PROMOTION_THRESHOLD_KEYS = {
    "minimum_t0_runs",
    "minimum_repositories",
    "minimum_task_variants",
    "minimum_sealed_honeypot_runs",
}

ROUTE_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
REF_RE = re.compile(
    r"^[a-z0-9]+(?:-[a-z0-9]+)*@(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")
HOST_RE = re.compile(r"^[a-z0-9.-]+$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF_NAME_RE = re.compile(r"^(HEAD|refs/[A-Za-z0-9._/-]+)$")


class RouteArtifactError(ValueError):
    """Stable fail-closed validation error."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def fail(code: str, message: str) -> None:
    raise RouteArtifactError(code, message)


def _reject_duplicate_policy_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            fail(
                "ROUTE-V2-POLICY",
                f"duplicate JSON object key in promotion thresholds: {key}",
            )
        value[key] = item
    return value


def _normalize_json(value: Any, path: str = "$") -> Any:
    """Normalize strings to NFC and reject unsupported or non-finite JSON values."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            fail("ROUTE-V2-CANONICAL", f"{path} contains a non-finite number")
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            if not isinstance(raw_key, str):
                fail("ROUTE-V2-CANONICAL", f"{path} contains a non-string object key")
            key = unicodedata.normalize("NFC", raw_key)
            if key in normalized:
                fail(
                    "ROUTE-V2-CANONICAL",
                    f"{path} contains keys that collide after NFC normalization",
                )
            normalized[key] = _normalize_json(raw_value, f"{path}.{key}")
        return normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [
            _normalize_json(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    fail(
        "ROUTE-V2-CANONICAL",
        f"{path} contains unsupported JSON value {type(value).__name__}",
    )


def canonical_json(value: Any) -> str:
    """Return the canonical JSON subset used for content addressing."""
    return json.dumps(
        _normalize_json(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def protected_payload(artifact: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(artifact))
    if isinstance(payload.get("integrity"), dict):
        payload["integrity"]["content_digest"] = None
    return payload


def compute_content_digest(artifact: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(protected_payload(artifact)).encode("utf-8")
    ).hexdigest()


def replay_evidence_payload(replay: Mapping[str, Any]) -> dict[str, Any]:
    """Return the replay evidence bytes covered by evidence_digest."""
    payload = copy.deepcopy(dict(replay))
    payload.pop("evidence_digest", None)
    return payload


def compute_replay_evidence_digest(replay: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        canonical_json(replay_evidence_payload(replay)).encode("utf-8")
    ).hexdigest()


def artifact_ref(artifact: Mapping[str, Any]) -> str:
    return f"{artifact.get('route_id')}@{artifact.get('version')}"


def obj(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        fail("ROUTE-V2-TYPE", f"{path} must be an object")
    return value


def arr(value: Any, path: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        fail("ROUTE-V2-TYPE", f"{path} must be an array")
    return value


def text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        fail("ROUTE-V2-TYPE", f"{path} must be a non-empty string")
    return value


def integer(value: Any, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        fail("ROUTE-V2-TYPE", f"{path} must be an integer >= {minimum}")
    return value


def boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        fail("ROUTE-V2-TYPE", f"{path} must be a boolean")
    return value


def exact(value: Mapping[str, Any], path: str, keys: set[str]) -> None:
    missing = keys - set(value)
    extra = set(value) - keys
    if missing:
        fail("ROUTE-V2-SHAPE", f"{path} is missing keys: {sorted(missing)}")
    if extra:
        fail("ROUTE-V2-SHAPE", f"{path} contains unknown keys: {sorted(extra)}")


def promotion_thresholds(
    value: Any,
    path: str = "promotion_thresholds",
) -> dict[str, int]:
    """Validate externally selected numeric promotion thresholds."""
    configured = obj(value, path)
    exact(configured, path, PROMOTION_THRESHOLD_KEYS)
    return {
        key: integer(configured[key], f"{path}.{key}", 1)
        for key in sorted(PROMOTION_THRESHOLD_KEYS)
    }


def load_promotion_thresholds(
    path: Path | str = DEFAULT_PROMOTION_THRESHOLDS_PATH,
) -> dict[str, int]:
    """Load and validate a promotion-threshold configuration file."""
    source = Path(path)
    try:
        value = json.loads(
            source.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_policy_keys,
        )
    except (OSError, json.JSONDecodeError) as exc:
        fail(
            "ROUTE-V2-POLICY",
            f"cannot load promotion thresholds from {source}: {exc}",
        )
    return promotion_thresholds(value)


def metric(
    value: Any,
    path: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> None:
    value = obj(value, path)
    exact(value, path, {"point", "ci95"})
    point = value["point"]
    ci = value["ci95"]

    if point is not None:
        if isinstance(point, bool) or not isinstance(point, (int, float)):
            fail("ROUTE-V2-METRIC", f"{path}.point must be numeric or null")
        if not math.isfinite(point):
            fail("ROUTE-V2-METRIC", f"{path}.point must be finite")
        if minimum is not None and point < minimum:
            fail("ROUTE-V2-METRIC", f"{path}.point must be >= {minimum}")
        if maximum is not None and point > maximum:
            fail("ROUTE-V2-METRIC", f"{path}.point must be <= {maximum}")

    if ci is None:
        if point is not None:
            fail("ROUTE-V2-METRIC", f"{path}.ci95 is required when point is present")
        return

    ci = obj(ci, f"{path}.ci95")
    exact(ci, f"{path}.ci95", {"lower", "upper"})
    lower = ci["lower"]
    upper = ci["upper"]
    for name, bound in (("lower", lower), ("upper", upper)):
        if isinstance(bound, bool) or not isinstance(bound, (int, float)):
            fail("ROUTE-V2-METRIC", f"{path}.ci95.{name} must be numeric")
        if not math.isfinite(bound):
            fail("ROUTE-V2-METRIC", f"{path}.ci95.{name} must be finite")
        if minimum is not None and bound < minimum:
            fail(
                "ROUTE-V2-METRIC",
                f"{path}.ci95.{name} must be >= {minimum}",
            )
        if maximum is not None and bound > maximum:
            fail(
                "ROUTE-V2-METRIC",
                f"{path}.ci95.{name} must be <= {maximum}",
            )
    if lower > upper or (point is not None and not lower <= point <= upper):
        fail("ROUTE-V2-METRIC", f"{path} has inconsistent point/ci95")


def complete_metric(value: Mapping[str, Any]) -> bool:
    ci = value.get("ci95")
    return (
        value.get("point") is not None
        and isinstance(ci, Mapping)
        and ci.get("lower") is not None
        and ci.get("upper") is not None
    )


def empty_metric(value: Mapping[str, Any]) -> bool:
    return value.get("point") is None and value.get("ci95") is None


def verify_replay(value: Any) -> Mapping[str, Any]:
    replay = obj(value, "verification.replay")
    exact(
        replay,
        "verification.replay",
        {
            "command",
            "expected_exit_code",
            "observed_exit_code",
            "assertions",
            "passed",
            "evidence_digest",
        },
    )
    text(replay["command"], "verification.replay.command")
    expected = integer(
        replay["expected_exit_code"], "verification.replay.expected_exit_code"
    )
    observed = integer(
        replay["observed_exit_code"], "verification.replay.observed_exit_code"
    )
    if not boolean(replay["passed"], "verification.replay.passed") or observed != expected:
        fail(
            "ROUTE-V2-REPLAY",
            "deterministic replay did not reproduce the expected result",
        )

    digest = text(replay["evidence_digest"], "verification.replay.evidence_digest")
    if not SHA256_RE.fullmatch(digest):
        fail(
            "ROUTE-V2-DIGEST",
            "replay evidence_digest must be lowercase SHA-256",
        )

    assertions = arr(replay["assertions"], "verification.replay.assertions")
    if not assertions:
        fail("ROUTE-V2-REPLAY", "replay assertions must not be empty")

    seen_names: set[str] = set()
    for index, raw in enumerate(assertions):
        path = f"verification.replay.assertions[{index}]"
        assertion = obj(raw, path)
        exact(assertion, path, {"name", "passed"})
        name = text(assertion["name"], f"{path}.name")
        if name in seen_names:
            fail("ROUTE-V2-REPLAY", f"duplicate replay assertion: {name}")
        seen_names.add(name)
        if not boolean(assertion["passed"], f"{path}.passed"):
            fail("ROUTE-V2-REPLAY", f"replay assertion failed: {name}")

    expected_digest = compute_replay_evidence_digest(replay)
    if digest != expected_digest:
        fail(
            "ROUTE-V2-DIGEST",
            f"replay evidence digest mismatch: expected {expected_digest}",
        )
    return replay


def _reject_external_command_paths(arguments: Sequence[str]) -> None:
    """Reject command tokens that can address files outside the exact tree."""
    for argument in arguments:
        candidates = [argument]
        if "=" in argument:
            candidates.append(argument.split("=", 1)[1])
        for raw_candidate in candidates:
            candidate = raw_candidate.replace("\\", "/")
            path = PurePosixPath(candidate)
            if (
                path.is_absolute()
                or ".." in path.parts
                or re.match(r"^[A-Za-z]:/", candidate)
            ):
                fail(
                    "ROUTE-V2-REPLAY",
                    "replay command paths must remain inside the exact source tree",
                )


def _verify_replay_entrypoint(arguments: Sequence[str], replay_root: Path) -> None:
    """Require one exact-tree implementation behind an operator-provided runner."""
    if "/" in arguments[0] or "\\" in arguments[0] or arguments[0].startswith("."):
        entrypoint = arguments[0]
    else:
        if len(arguments) < 2 or arguments[1].startswith("-"):
            fail(
                "ROUTE-V2-REPLAY",
                (
                    "replay command must name a repository-local implementation "
                    "immediately after its sandbox runner"
                ),
            )
        entrypoint = arguments[1]

    candidate = replay_root / entrypoint
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        fail(
            "ROUTE-V2-REPLAY",
            f"replay implementation is missing from the exact source tree: {entrypoint}",
        )
    if not resolved.is_relative_to(replay_root) or not resolved.is_file():
        fail(
            "ROUTE-V2-REPLAY",
            "replay implementation must be a regular file inside the exact source tree",
        )


@contextlib.contextmanager
def _materialized_exact_tree(
    repository_root: Path,
    exact_head: str,
) -> Iterator[Path]:
    """Materialize only exact-head Git objects into a verifier-owned directory."""
    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(repository_root),
                "archive",
                "--format=tar",
                exact_head,
            ],
            check=True,
            capture_output=True,
            timeout=60,
            env=_sanitized_git_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        fail("ROUTE-V2-HEAD", f"unable to materialize exact source tree: {exc}")

    with tempfile.TemporaryDirectory(prefix="route-v2-replay-") as directory:
        replay_root = Path(directory).resolve()
        try:
            with tarfile.open(
                fileobj=io.BytesIO(completed.stdout), mode="r:"
            ) as archive:
                members = archive.getmembers()
                for member in members:
                    path = PurePosixPath(member.name)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or member.isdev()
                        or member.isfifo()
                        or member.islnk()
                    ):
                        fail(
                            "ROUTE-V2-HEAD",
                            "exact source archive contains an unsafe entry",
                        )
                archive.extractall(replay_root, members=members, filter="data")
        except (OSError, tarfile.TarError) as exc:
            fail("ROUTE-V2-HEAD", f"unable to extract exact source tree: {exc}")
        yield replay_root


def execute_replay(
    replay: Mapping[str, Any],
    repository_root: Path | str,
    exact_head: str,
) -> Mapping[str, str]:
    """Execute exact-tree replay and hash its canonical honeypot results locally."""
    command = text(replay["command"], "verification.replay.command")
    try:
        arguments = shlex.split(command)
    except ValueError as exc:
        fail("ROUTE-V2-REPLAY", f"invalid replay command: {exc}")
    if not arguments:
        fail("ROUTE-V2-REPLAY", "replay command must not be empty")
    _reject_external_command_paths(arguments)

    with _materialized_exact_tree(
        Path(repository_root).resolve(), exact_head
    ) as replay_root:
        _verify_replay_entrypoint(arguments, replay_root)
        try:
            completed = subprocess.run(
                arguments,
                cwd=replay_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
                env=_sanitized_git_environment(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            fail("ROUTE-V2-REPLAY", f"unable to execute replay command: {exc}")

    expected = replay["expected_exit_code"]
    observed = replay["observed_exit_code"]
    if completed.returncode != expected or completed.returncode != observed:
        fail(
            "ROUTE-V2-REPLAY",
            (
                "executed replay exit code "
                f"{completed.returncode} does not match declared "
                f"expected={expected} and observed={observed}"
            ),
        )

    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        fail(
            "ROUTE-V2-REPLAY",
            f"replay stdout must be one JSON execution report: {exc}",
        )
    report = obj(report, "replay_execution_report")
    exact(
        report,
        "replay_execution_report",
        {"assertions", "honeypot_results"},
    )
    reported_assertions = arr(
        report["assertions"],
        "replay_execution_report.assertions",
    )
    if canonical_json(reported_assertions) != canonical_json(replay["assertions"]):
        fail(
            "ROUTE-V2-REPLAY",
            "executed assertion report does not match declared assertions",
        )

    raw_results = obj(
        report["honeypot_results"],
        "replay_execution_report.honeypot_results",
    )
    results: dict[str, str] = {}
    for evaluation_id, raw_result in raw_results.items():
        if not isinstance(evaluation_id, str) or not NAME_RE.fullmatch(evaluation_id):
            fail("ROUTE-V2-HONEYPOT", "execution report has an invalid honeypot id")
        results[evaluation_id] = hashlib.sha256(
            canonical_json(raw_result).encode("utf-8")
        ).hexdigest()
    return results


def verify_honeypot_evaluations(value: Any) -> list[Mapping[str, Any]]:
    evaluations = arr(value, "verification.honeypot_evaluations")
    seen_ids: set[str] = set()

    for index, raw in enumerate(evaluations):
        path = f"verification.honeypot_evaluations[{index}]"
        evaluation = obj(raw, path)
        exact(
            evaluation,
            path,
            {
                "id",
                "sealed",
                "ground_truth_digest",
                "observed_result_digest",
                "matched",
            },
        )
        evaluation_id = text(evaluation["id"], f"{path}.id")
        if not NAME_RE.fullmatch(evaluation_id) or evaluation_id in seen_ids:
            fail(
                "ROUTE-V2-HONEYPOT",
                f"invalid or duplicate honeypot evaluation id: {evaluation_id}",
            )
        seen_ids.add(evaluation_id)
        if not boolean(evaluation["sealed"], f"{path}.sealed"):
            fail("ROUTE-V2-HONEYPOT", f"{evaluation_id} was not sealed")
        if not boolean(evaluation["matched"], f"{path}.matched"):
            fail(
                "ROUTE-V2-HONEYPOT",
                f"{evaluation_id} did not match known ground truth",
            )
        for key in ("ground_truth_digest", "observed_result_digest"):
            digest = text(evaluation[key], f"{path}.{key}")
            if not SHA256_RE.fullmatch(digest):
                fail(
                    "ROUTE-V2-HONEYPOT",
                    f"{path}.{key} must be lowercase SHA-256",
                )

    return list(evaluations)


def bind_trusted_honeypot_ground_truth(
    route_ref: str,
    evaluations: Sequence[Mapping[str, Any]],
    trusted_ground_truth: Mapping[str, Any] | None,
) -> dict[str, str]:
    """Bind producer declarations to operator-supplied sealed ground truth."""
    if not evaluations:
        return {}
    if trusted_ground_truth is None:
        fail(
            "ROUTE-V2-HONEYPOT",
            "T0 honeypots require operator-supplied sealed ground truth",
        )
    trusted_routes = obj(trusted_ground_truth, "trusted_honeypot_ground_truth")
    if route_ref not in trusted_routes:
        fail(
            "ROUTE-V2-HONEYPOT",
            f"operator ground truth is missing route {route_ref}",
        )
    route_truth = obj(
        trusted_routes[route_ref],
        f"trusted_honeypot_ground_truth.{route_ref}",
    )
    expected_ids = {evaluation["id"] for evaluation in evaluations}
    if set(route_truth) != expected_ids:
        fail(
            "ROUTE-V2-HONEYPOT",
            "operator ground-truth ids do not match the declared honeypot set",
        )

    trusted: dict[str, str] = {}
    for evaluation in evaluations:
        evaluation_id = evaluation["id"]
        digest = text(
            route_truth[evaluation_id],
            f"trusted_honeypot_ground_truth.{route_ref}.{evaluation_id}",
        )
        if not SHA256_RE.fullmatch(digest):
            fail(
                "ROUTE-V2-HONEYPOT",
                f"trusted ground truth for {evaluation_id} is not lowercase SHA-256",
            )
        if evaluation["ground_truth_digest"] != digest:
            fail(
                "ROUTE-V2-HONEYPOT",
                f"declared ground truth for {evaluation_id} is not operator-bound",
            )
        trusted[evaluation_id] = digest
    return trusted


def verify_executed_honeypots(
    evaluations: Sequence[Mapping[str, Any]],
    executed_results: Mapping[str, str],
    trusted_ground_truth: Mapping[str, str],
) -> int:
    """Count only results bound to both execution and trusted ground truth."""
    expected_ids = {evaluation["id"] for evaluation in evaluations}
    if set(executed_results) != expected_ids:
        fail(
            "ROUTE-V2-HONEYPOT",
            "executed honeypot result ids do not match the declared set",
        )
    for evaluation in evaluations:
        evaluation_id = evaluation["id"]
        observed = executed_results[evaluation_id]
        if evaluation["observed_result_digest"] != observed:
            fail(
                "ROUTE-V2-HONEYPOT",
                f"declared result for {evaluation_id} does not match replay output",
            )
        if observed != trusted_ground_truth[evaluation_id]:
            fail(
                "ROUTE-V2-HONEYPOT",
                f"executed result for {evaluation_id} did not match sealed ground truth",
            )
    return len(evaluations)


def _sanitized_git_environment() -> dict[str, str]:
    """Drop caller-controlled Git overrides before source-bound operations."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    return environment


def _run_git(repository_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
            env=_sanitized_git_environment(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        fail("ROUTE-V2-HEAD", f"unable to verify source checkout: {exc}")
    return completed.stdout.strip()


def _normalize_remote(remote: str) -> tuple[str, str] | None:
    remote = remote.strip()
    patterns = (
        re.compile(r"^https?://(?P<host>[^/]+)/(?P<repo>[^/]+/[^/]+?)(?:\.git)?$"),
        re.compile(r"^ssh://git@(?P<host>[^/]+)/(?P<repo>[^/]+/[^/]+?)(?:\.git)?$"),
        re.compile(r"^git@(?P<host>[^:]+):(?P<repo>[^/]+/[^/]+?)(?:\.git)?$"),
    )
    for pattern in patterns:
        match = pattern.fullmatch(remote)
        if match:
            return (
                match.group("host").lower(),
                match.group("repo").removesuffix(".git"),
            )
    return None


def verify_source_checkout(
    source: Any,
    exact_head: str,
    repository_root: Path | str | None,
) -> None:
    """Bind T0 evidence to an actual local checkout at the declared repository HEAD."""
    source = obj(source, "verification.source")
    exact(source, "verification.source", {"host", "repository", "ref", "commit"})
    host = text(source["host"], "verification.source.host").lower()
    repository = text(source["repository"], "verification.source.repository")
    ref_name = text(source["ref"], "verification.source.ref")
    commit = text(source["commit"], "verification.source.commit")

    if (
        not HOST_RE.fullmatch(host)
        or not REPOSITORY_RE.fullmatch(repository)
        or not REF_NAME_RE.fullmatch(ref_name)
    ):
        fail("ROUTE-V2-HEAD", "source host, repository, or ref is invalid")
    if not HEAD_RE.fullmatch(commit) or commit != exact_head:
        fail("ROUTE-V2-HEAD", "source.commit must equal verification.exact_head")
    if repository_root is None:
        fail("ROUTE-V2-HEAD", "T0 ingest requires a local repository checkout")

    root = Path(repository_root).resolve()
    if not root.is_dir():
        fail("ROUTE-V2-HEAD", f"repository checkout does not exist: {root}")

    replacement_refs = _run_git(
        root,
        "for-each-ref",
        "--format=%(refname)",
        "refs/replace",
    )
    if replacement_refs:
        fail("ROUTE-V2-HEAD", "source checkout contains Git replacement refs")

    current_head = _run_git(root, "rev-parse", "--verify", "HEAD^{commit}")
    if current_head != exact_head:
        fail(
            "ROUTE-V2-HEAD",
            f"checkout HEAD {current_head} does not match exact_head {exact_head}",
        )
    index_records = _run_git(root, "ls-files", "-v", "-z")
    for record in index_records.split("\0"):
        if record and record[0] in {"h", "S"}:
            fail(
                "ROUTE-V2-HEAD",
                (
                    "source checkout contains an assume-unchanged or "
                    f"skip-worktree index entry: {record[2:]}"
                ),
            )
    if _run_git(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--ignored=matching",
        "--ignore-submodules=none",
    ):
        fail(
            "ROUTE-V2-HEAD",
            "source checkout contains tracked, untracked, or ignored material",
        )
    declared_ref = _run_git(
        root,
        "rev-parse",
        "--verify",
        f"{ref_name}^{{commit}}",
    )
    if declared_ref != exact_head:
        fail(
            "ROUTE-V2-HEAD",
            f"source ref {ref_name} does not resolve to exact_head",
        )
    _run_git(root, "cat-file", "-e", f"{exact_head}^{{commit}}")

    remote = _run_git(root, "remote", "get-url", "origin")
    normalized = _normalize_remote(remote)
    if normalized is None:
        fail(
            "ROUTE-V2-HEAD",
            f"unsupported origin URL for deterministic binding: {remote}",
        )
    actual_host, actual_repository = normalized
    if actual_host != host or actual_repository.lower() != repository.lower():
        fail(
            "ROUTE-V2-HEAD",
            (
                f"origin {actual_host}/{actual_repository} does not match "
                f"declared {host}/{repository}"
            ),
        )


def verify_promotion(
    route: Mapping[str, Any],
    configured_thresholds: Mapping[str, int],
    verified_counts: Mapping[str, int],
) -> None:
    status = route["status"]
    if status not in {"candidate", "validated"}:
        return
    if status == "validated":
        fail(
            "ROUTE-V2-GOVERNANCE",
            (
                "validated state requires an independently authenticated "
                "governance decision, which is outside this artifact contract"
            ),
        )
    if route["verification"]["tier"] != "T0_deterministic_replay":
        fail(
            "ROUTE-V2-PROMOTION",
            f"{status} status requires T0 deterministic replay",
        )

    metrics = route["metrics"]
    policy = route["promotion_policy"]
    honeypots = route["verification"]["honeypot_evaluations"]
    failures: list[str] = []

    metric_floors = {
        "t0_runs": (
            verified_counts["t0_runs"],
            configured_thresholds["minimum_t0_runs"],
        ),
        "repository_count": (
            verified_counts["repository_count"],
            configured_thresholds["minimum_repositories"],
        ),
        "task_variant_count": (
            verified_counts["task_variant_count"],
            configured_thresholds["minimum_task_variants"],
        ),
        "sealed_honeypot_runs": (
            verified_counts["sealed_honeypot_runs"],
            configured_thresholds["minimum_sealed_honeypot_runs"],
        ),
    }
    for metric_key, (verified_count, floor) in metric_floors.items():
        if verified_count < floor:
            failures.append(metric_key)

    if len(honeypots) < configured_thresholds["minimum_sealed_honeypot_runs"]:
        failures.append("sealed_honeypot_ground_truth_evaluations")
    if (
        policy["requires_zero_unresolved_critical_false_negatives"]
        and metrics["unresolved_critical_false_negatives"]
    ):
        failures.append("unresolved_critical_false_negatives")
    if policy["requires_confidence_intervals"]:
        if not complete_metric(metrics["confirmed_effectiveness"]):
            failures.append("confirmed_effectiveness_ci95")
        if not complete_metric(metrics["false_positive_rate"]):
            failures.append("false_positive_rate_ci95")
    if failures:
        fail(
            "ROUTE-V2-PROMOTION",
            f"promotion gates failed: {', '.join(failures)}",
        )


def verify_route_artifact(
    artifact: Any,
    *,
    canonical_store: bool = True,
    repository_root: Path | str | None = None,
    configured_thresholds: Mapping[str, Any] | None = None,
    execute_declared_replay: bool = False,
    trusted_honeypot_ground_truth: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected_thresholds = promotion_thresholds(
        load_promotion_thresholds()
        if configured_thresholds is None
        else configured_thresholds
    )
    route = obj(artifact, "route")
    exact(
        route,
        "route",
        {
            "api_version",
            "kind",
            "route_id",
            "version",
            "status",
            "integrity",
            "lineage",
            "task_profile",
            "executor_profile",
            "stages",
            "verification",
            "metrics",
            "promotion_policy",
            "training",
            "license",
            "publishability",
            "provenance",
        },
    )
    if route["api_version"] != API_VERSION or route["kind"] != KIND:
        fail("ROUTE-V2-VERSION", "unsupported Route Artifact version or kind")

    route_id = text(route["route_id"], "route.route_id")
    version = text(route["version"], "route.version")
    status = text(route["status"], "route.status")
    if not ROUTE_RE.fullmatch(route_id) or not SEMVER_RE.fullmatch(version):
        fail("ROUTE-V2-ID", "route_id or version is invalid")
    if status not in STATUSES:
        fail("ROUTE-V2-STATUS", f"unsupported status: {status}")

    integrity = obj(route["integrity"], "route.integrity")
    exact(integrity, "route.integrity", {"digest_algorithm", "content_digest"})
    digest = text(integrity["content_digest"], "route.integrity.content_digest")
    if integrity["digest_algorithm"] != "sha256" or not SHA256_RE.fullmatch(digest):
        fail("ROUTE-V2-DIGEST", "invalid content digest contract")
    expected_digest = compute_content_digest(route)
    if digest != expected_digest:
        fail(
            "ROUTE-V2-DIGEST",
            f"content digest mismatch: expected {expected_digest}",
        )

    ref = artifact_ref(route)
    lineage = obj(route["lineage"], "route.lineage")
    exact(lineage, "route.lineage", {"supersedes"})
    parents = arr(lineage["supersedes"], "route.lineage.supersedes")
    seen_parents: set[str] = set()
    for parent_value in parents:
        parent = text(parent_value, "route.lineage.supersedes[]")
        if not REF_RE.fullmatch(parent) or parent == ref or parent in seen_parents:
            fail(
                "ROUTE-V2-LINEAGE",
                f"invalid supersession reference: {parent}",
            )
        seen_parents.add(parent)

    profile = obj(route["task_profile"], "route.task_profile")
    exact(profile, "route.task_profile", {"category", "subtype", "risk_level"})
    text(profile["category"], "route.task_profile.category")
    text(profile["subtype"], "route.task_profile.subtype")
    if profile["risk_level"] not in RISKS:
        fail("ROUTE-V2-RISK", "unsupported risk level")

    roles: dict[str, str] = {}
    executors = arr(route["executor_profile"], "route.executor_profile")
    if not executors:
        fail("ROUTE-V2-EXECUTOR", "executor_profile must not be empty")
    for index, raw in enumerate(executors):
        path = f"route.executor_profile[{index}]"
        executor = obj(raw, path)
        exact(executor, path, {"role", "capability_class"})
        role = text(executor["role"], f"{path}.role")
        capability = text(executor["capability_class"], f"{path}.capability_class")
        if (
            not NAME_RE.fullmatch(role)
            or capability not in CAPABILITIES
            or role in roles
        ):
            fail(
                "ROUTE-V2-EXECUTOR",
                f"invalid or duplicate executor: {role}",
            )
        roles[role] = capability

    known_stages: set[str] = set()
    stages = arr(route["stages"], "route.stages")
    if not stages:
        fail("ROUTE-V2-STAGE", "stages must not be empty")
    for index, raw in enumerate(stages):
        path = f"route.stages[{index}]"
        stage = obj(raw, path)
        exact(
            stage,
            path,
            {"id", "role", "capability_class", "independent", "depends_on"},
        )
        stage_id = text(stage["id"], f"{path}.id")
        role = text(stage["role"], f"{path}.role")
        capability = text(stage["capability_class"], f"{path}.capability_class")
        boolean(stage["independent"], f"{path}.independent")
        if (
            not NAME_RE.fullmatch(stage_id)
            or stage_id in known_stages
            or role not in roles
            or capability != roles[role]
        ):
            fail("ROUTE-V2-STAGE", f"invalid stage declaration: {stage_id}")
        dependencies = arr(stage["depends_on"], f"{path}.depends_on")
        seen_dependencies: set[str] = set()
        for dependency_value in dependencies:
            if not isinstance(dependency_value, str):
                fail(
                    "ROUTE-V2-STAGE",
                    f"stage {stage_id} dependency must be a string",
                )
            dependency = dependency_value
            if dependency in seen_dependencies or dependency not in known_stages:
                fail(
                    "ROUTE-V2-STAGE",
                    f"stage {stage_id} has missing, repeated, or non-prior dependency",
                )
            seen_dependencies.add(dependency)
        known_stages.add(stage_id)

    verification = obj(route["verification"], "route.verification")
    exact(
        verification,
        "route.verification",
        {
            "tier",
            "source",
            "exact_head",
            "sandbox",
            "replay",
            "artifact_refs",
            "human_sign_off",
            "narrative",
            "honeypot_evaluations",
        },
    )
    tier = text(verification["tier"], "route.verification.tier")
    if tier not in TIERS:
        fail("ROUTE-V2-TIER", f"unsupported tier: {tier}")
    sandbox = boolean(verification["sandbox"], "route.verification.sandbox")
    artifact_refs = arr(
        verification["artifact_refs"],
        "route.verification.artifact_refs",
    )
    for item in artifact_refs:
        text(item, "route.verification.artifact_refs[]")

    head = verification["exact_head"]
    if head is not None and (
        not isinstance(head, str) or not HEAD_RE.fullmatch(head)
    ):
        fail(
            "ROUTE-V2-HEAD",
            "exact_head must be a lowercase 40-character git SHA",
        )

    sign_off = verification["human_sign_off"]
    if sign_off is not None:
        sign_off = obj(sign_off, "route.verification.human_sign_off")
        exact(
            sign_off,
            "route.verification.human_sign_off",
            {"actor", "signed_at", "decision"},
        )
        text(sign_off["actor"], "route.verification.human_sign_off.actor")
        text(sign_off["signed_at"], "route.verification.human_sign_off.signed_at")
        if sign_off["decision"] != "attested":
            fail("ROUTE-V2-TIER", "human sign-off must be attested")

    narrative = verification["narrative"]
    if narrative is not None:
        text(narrative, "route.verification.narrative")
    honeypots = verify_honeypot_evaluations(
        verification["honeypot_evaluations"]
    )

    verified_counts = {
        "t0_runs": 0,
        "repository_count": 0,
        "task_variant_count": 0,
        "sealed_honeypot_runs": 0,
    }
    if tier == "T0_deterministic_replay":
        if head is None or not sandbox or verification["source"] is None:
            fail(
                "ROUTE-V2-T0",
                "T0 requires source, exact_head and sandbox=true",
            )
        if narrative is not None:
            fail("ROUTE-V2-T0", "T0 narrative must be null")
        replay = verify_replay(verification["replay"])
        verify_source_checkout(
            verification["source"],
            head,
            repository_root,
        )
        if not execute_declared_replay:
            fail(
                "ROUTE-V2-REPLAY",
                (
                    "T0 assignment requires explicit replay execution in an "
                    "operator-controlled sandbox"
                ),
            )
        trusted_ground_truth = bind_trusted_honeypot_ground_truth(
            ref,
            honeypots,
            trusted_honeypot_ground_truth,
        )
        executed_honeypots = execute_replay(replay, repository_root, head)
        verified_honeypot_count = verify_executed_honeypots(
            honeypots,
            executed_honeypots,
            trusted_ground_truth,
        )
        verified_counts.update(
            {
                "t0_runs": 1,
                "repository_count": 1,
                "task_variant_count": 1,
                "sealed_honeypot_runs": verified_honeypot_count,
            }
        )
    elif tier == "T1_artifact_attested":
        if (
            verification["source"] is not None
            or head is not None
            or sandbox
            or verification["replay"] is not None
            or honeypots
        ):
            fail(
                "ROUTE-V2-T1",
                (
                    "T1 cannot claim source, exact-head, sandbox, replay, "
                    "or honeypot ground-truth verification"
                ),
            )
        if not artifact_refs or sign_off is None or narrative is not None:
            fail(
                "ROUTE-V2-T1",
                "T1 requires artifacts and sign-off without narrative",
            )
    else:
        if (
            verification["source"] is not None
            or head is not None
            or sandbox
            or verification["replay"] is not None
            or artifact_refs
            or sign_off is not None
            or honeypots
        ):
            fail("ROUTE-V2-T2", "T2 must remain strictly narrative-only")
        if not narrative:
            fail("ROUTE-V2-T2", "T2 rejection audit requires a narrative")
        if canonical_store:
            fail(
                "ROUTE-V2-T2",
                "narrative-only submissions are rejected from the canonical store",
            )

    metrics = obj(route["metrics"], "route.metrics")
    exact(
        metrics,
        "route.metrics",
        {
            "sample_size",
            "t0_runs",
            "repository_count",
            "task_variant_count",
            "sealed_honeypot_runs",
            "unresolved_critical_false_negatives",
            "confirmed_effectiveness",
            "false_positive_rate",
            "reviewer_minutes_saved",
            "maintainer_approved",
        },
    )
    for key in (
        "sample_size",
        "t0_runs",
        "repository_count",
        "task_variant_count",
        "sealed_honeypot_runs",
        "unresolved_critical_false_negatives",
    ):
        integer(metrics[key], f"route.metrics.{key}")
    if metrics["t0_runs"] > metrics["sample_size"]:
        fail("ROUTE-V2-METRIC", "t0_runs cannot exceed sample_size")
    if metrics["sealed_honeypot_runs"] != len(honeypots):
        fail(
            "ROUTE-V2-HONEYPOT",
            (
                "sealed_honeypot_runs must equal the number of "
                "verified honeypot evaluations"
            ),
        )
    for key in ("confirmed_effectiveness", "false_positive_rate"):
        metric(
            metrics[key],
            f"route.metrics.{key}",
            minimum=0.0,
            maximum=1.0,
        )
    metric(
        metrics["reviewer_minutes_saved"],
        "route.metrics.reviewer_minutes_saved",
        minimum=0.0,
    )
    maintainer_approved = boolean(
        metrics["maintainer_approved"],
        "route.metrics.maintainer_approved",
    )
    if maintainer_approved:
        fail(
            "ROUTE-V2-GOVERNANCE",
            "producer-authored maintainer_approved must remain false",
        )
    if tier == "T0_deterministic_replay":
        for key in (
            "confirmed_effectiveness",
            "false_positive_rate",
            "reviewer_minutes_saved",
        ):
            if not empty_metric(metrics[key]):
                fail(
                    "ROUTE-V2-METRIC",
                    (
                        f"producer-authored {key} must remain empty until an "
                        "independent scorer evidence contract is supplied"
                    ),
                )

    policy = obj(route["promotion_policy"], "route.promotion_policy")
    exact(
        policy,
        "route.promotion_policy",
        {
            "minimum_t0_runs",
            "minimum_repositories",
            "minimum_task_variants",
            "minimum_sealed_honeypot_runs",
            "requires_zero_unresolved_critical_false_negatives",
            "requires_confidence_intervals",
            "requires_maintainer_approval",
        },
    )
    for key, configured_value in selected_thresholds.items():
        value = integer(policy[key], f"route.promotion_policy.{key}", 1)
        if value != configured_value:
            fail(
                "ROUTE-V2-POLICY",
                (
                    f"route.promotion_policy.{key} must equal the externally "
                    f"configured threshold {configured_value}"
                ),
            )
    for key in (
        "requires_zero_unresolved_critical_false_negatives",
        "requires_confidence_intervals",
        "requires_maintainer_approval",
    ):
        if not boolean(policy[key], f"route.promotion_policy.{key}"):
            fail(
                "ROUTE-V2-POLICY",
                f"initial v2 policy requires {key}=true",
            )

    training = obj(route["training"], "route.training")
    exact(training, "route.training", {"eligible", "corpus_scope"})
    eligible = boolean(training["eligible"], "route.training.eligible")
    if training["corpus_scope"] not in {"none", "research", "distillation"}:
        fail("ROUTE-V2-TRAINING", "unsupported corpus scope")

    license_value = obj(route["license"], "route.license")
    exact(
        license_value,
        "route.license",
        {
            "artifact_license",
            "training_permission",
            "redistribution_permission",
            "commercial_use",
        },
    )
    text(license_value["artifact_license"], "route.license.artifact_license")
    if license_value["training_permission"] not in {
        "none",
        "open_weight_only_v1",
        "any_with_attribution_v1",
    }:
        fail("ROUTE-V2-LICENSE", "unsupported training permission")
    if license_value["redistribution_permission"] not in {
        "prohibited",
        "allowed_with_attribution",
        "allowed",
    }:
        fail("ROUTE-V2-LICENSE", "unsupported redistribution permission")
    if license_value["commercial_use"] not in {
        "prohibited",
        "restricted",
        "allowed",
    }:
        fail("ROUTE-V2-LICENSE", "unsupported commercial-use policy")

    publishability = obj(route["publishability"], "route.publishability")
    exact(publishability, "route.publishability", {"level"})
    if publishability["level"] not in {"private", "community", "public"}:
        fail("ROUTE-V2-PUBLISH", "unsupported publishability level")

    provenance = obj(route["provenance"], "route.provenance")
    exact(
        provenance,
        "route.provenance",
        {"contributors", "source_runs", "created_at"},
    )
    for contributor in arr(
        provenance["contributors"],
        "route.provenance.contributors",
    ):
        text(contributor, "route.provenance.contributors[]")
    for source_run in arr(
        provenance["source_runs"],
        "route.provenance.source_runs",
    ):
        text(source_run, "route.provenance.source_runs[]")
    text(provenance["created_at"], "route.provenance.created_at")

    if tier != "T0_deterministic_replay":
        if (
            eligible
            or training["corpus_scope"] != "none"
            or metrics["t0_runs"] != 0
            or metrics["sealed_honeypot_runs"] != 0
        ):
            fail(
                "ROUTE-V2-TRAINING",
                (
                    "non-T0 routes cannot claim T0 runs, honeypot runs, "
                    "or training eligibility"
                ),
            )
        for key in (
            "confirmed_effectiveness",
            "false_positive_rate",
            "reviewer_minutes_saved",
        ):
            if not empty_metric(metrics[key]):
                fail(
                    "ROUTE-V2-METRIC",
                    f"non-T0 routes cannot claim {key}",
                )
    elif eligible and license_value["training_permission"] == "none":
        fail(
            "ROUTE-V2-TRAINING",
            "training eligibility requires explicit permission",
        )

    verify_promotion(route, selected_thresholds, verified_counts)
    return {
        "route_ref": ref,
        "content_digest": digest,
        "tier": tier,
        "status": status,
        "canonical_store_eligible": tier != "T2_narrative_only",
        "training_eligible": eligible,
        "source_bound": tier == "T0_deterministic_replay",
        "honeypot_evaluations": len(honeypots),
        "verified_promotion_counts": verified_counts,
    }


def verify_immutable_update(
    existing_digests: Mapping[str, str],
    artifact: Mapping[str, Any],
    *,
    repository_root: Path | str | None = None,
    configured_thresholds: Mapping[str, Any] | None = None,
    execute_declared_replay: bool = False,
    trusted_honeypot_ground_truth: Mapping[str, Any] | None = None,
) -> None:
    summary = verify_route_artifact(
        artifact,
        repository_root=repository_root,
        configured_thresholds=configured_thresholds,
        execute_declared_replay=execute_declared_replay,
        trusted_honeypot_ground_truth=trusted_honeypot_ground_truth,
    )
    previous = existing_digests.get(summary["route_ref"])
    if previous is not None and previous != summary["content_digest"]:
        fail(
            "ROUTE-V2-IMMUTABLE",
            f"immutable route version was modified: {summary['route_ref']}",
        )


def build_registry_projection(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    repository_root: Path | str | None = None,
    configured_thresholds: Mapping[str, Any] | None = None,
    execute_declared_replay: bool = False,
    trusted_honeypot_ground_truth: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected_thresholds = promotion_thresholds(
        load_promotion_thresholds()
        if configured_thresholds is None
        else configured_thresholds
    )
    records: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        summary = verify_route_artifact(
            artifact,
            repository_root=repository_root,
            configured_thresholds=selected_thresholds,
            execute_declared_replay=execute_declared_replay,
            trusted_honeypot_ground_truth=trusted_honeypot_ground_truth,
        )
        ref = summary["route_ref"]
        if ref in records:
            fail("ROUTE-V2-REGISTRY", f"duplicate route version: {ref}")
        records[ref] = {
            "route_ref": ref,
            "content_digest": summary["content_digest"],
            "status": summary["status"],
            "tier": summary["tier"],
            "supersedes": list(artifact["lineage"]["supersedes"]),
            "superseded_by": [],
        }

    children: dict[str, list[str]] = {ref: [] for ref in records}
    indegree: dict[str, int] = {ref: 0 for ref in records}
    for ref, record in records.items():
        for parent in record["supersedes"]:
            if parent not in records:
                fail(
                    "ROUTE-V2-REGISTRY",
                    f"{ref} supersedes missing route version {parent}",
                )
            records[parent]["superseded_by"].append(ref)
            children[parent].append(ref)
            indegree[ref] += 1

    queue = [ref for ref, degree in indegree.items() if degree == 0]
    heapq.heapify(queue)
    topological_order: list[str] = []
    while queue:
        current = heapq.heappop(queue)
        topological_order.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                heapq.heappush(queue, child)

    if len(topological_order) != len(records):
        cycle_nodes = sorted(
            ref for ref, degree in indegree.items() if degree > 0
        )
        fail(
            "ROUTE-V2-REGISTRY",
            f"supersession cycle detected: {', '.join(cycle_nodes)}",
        )

    for record in records.values():
        record["superseded_by"].sort()
    return {
        "routes": [records[ref] for ref in sorted(records)],
        "topological_order": topological_order,
    }
