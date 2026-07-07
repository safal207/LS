from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

DIGEST = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
IDENT = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,63}$")
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
LANES = {"FRONTIER_MODEL", "LS"}
SEVERITIES = {"critical", "high", "medium", "low"}
CLASSIFICATIONS = {
    "CONFIRMED_DEFECT",
    "REPRODUCIBLE_HYPOTHESIS",
    "UNSUPPORTED_HYPOTHESIS",
    "DESIGN_QUESTION",
}
REPRODUCTION_STATUSES = {
    "REPRODUCED",
    "STATICALLY_PROVEN",
    "PROPOSED",
    "NOT_AVAILABLE",
}
RELATION_STATUSES = {"OBSERVED", "INFERRED", "MISSING", "CONTRADICTED"}
PROBE_STATUSES = {"PASSED", "FAILED", "INCONCLUSIVE", "NOT_RUN"}
CHANNELS = {"WEB_UI", "API", "LOCAL", "WORKFLOW"}
PROVENANCE_LEVELS = {"USER_ATTESTED", "API_VERIFIED", "WORKFLOW_VERIFIED"}
VERDICTS = {"APPROVE", "COMMENT", "REQUEST_CHANGES", "INCOMPLETE"}


class BenchmarkV02Error(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkV02Error(f"cannot load JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkV02Error(f"{path} must contain an object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact(value: Any, keys: set[str], field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BenchmarkV02Error(f"{field} must be an object")
    actual = set(value)
    if actual != keys:
        raise BenchmarkV02Error(
            f"{field} keys mismatch; missing={sorted(keys-actual)}, "
            f"extra={sorted(actual-keys)}"
        )
    return value


def text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise BenchmarkV02Error(f"{field} must be a non-empty string")
    return value


def strings(value: Any, field: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise BenchmarkV02Error(f"{field} must be an array")
    if any(not isinstance(item, str) or not item for item in value):
        raise BenchmarkV02Error(f"{field} must contain non-empty strings")
    return value


def repo_path(value: Any, field: str) -> str:
    result = text(value, field)
    path = PurePosixPath(result)
    if path.is_absolute() or ".." in path.parts:
        raise BenchmarkV02Error(f"{field} must remain inside the repository")
    return result


def digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not DIGEST.fullmatch(value):
        raise BenchmarkV02Error(f"{field} must be a lowercase SHA-256")
    return value


def confidence(value: Any, field: str) -> float:
    valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    if not valid or not 0 <= value <= 1:
        raise BenchmarkV02Error(f"{field} must be between 0 and 1")
    return float(value)
