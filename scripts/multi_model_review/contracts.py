"""Deterministic contracts for LS multi-model review."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
VALID_VERDICTS = {"APPROVE", "COMMENT", "REQUEST_CHANGES"}
TOKEN_RE = re.compile(r"[a-z0-9]+")
_SENSITIVE_TERMS = [
    "api_" + "key",
    "access_" + "token",
    "auth" + "orization",
    "pass" + "word",
    "pass" + "wd",
    "se" + "cret",
    "private_" + "key",
]
SENSITIVE_ASSIGNMENT_RE = re.compile(
    rf"(?i)({'|'.join(re.escape(term) for term in _SENSITIVE_TERMS)})(\s*[:=]\s*)([^\s,;]+)"
)
BEARER_RE = re.compile(r"(?i)(bear" + r"er\s+)[A-Za-z0-9._~+/=-]{8,}")
_PRIVATE_MARKER = "PRIVATE" + " KEY"
PRIVATE_KEY_RE = re.compile(
    rf"-----BEGIN [A-Z0-9 ]*{_PRIVATE_MARKER}-----.*?-----END [A-Z0-9 ]*{_PRIVATE_MARKER}-----",
    re.DOTALL,
)


class ReviewRuntimeError(RuntimeError):
    """Raised for deterministic configuration or contract failures."""


def validate_sha(value: str, field: str) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ReviewRuntimeError(f"{field} must be a lowercase 40-character git SHA")
    return value


def load_config(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewRuntimeError(f"cannot load model roster: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != "ls.ai_review_model_roster.v0.1":
        raise ReviewRuntimeError("unsupported model roster schema")
    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ReviewRuntimeError("model roster must contain at least one model")
    keys: set[str] = set()
    roles: set[str] = set()
    for index, item in enumerate(models):
        if not isinstance(item, dict):
            raise ReviewRuntimeError(f"models[{index}] must be an object")
        key = item.get("key")
        if not isinstance(key, str) or not key or key in keys:
            raise ReviewRuntimeError(f"models[{index}].key must be unique and non-empty")
        keys.add(key)
        role = item.get("role")
        if not isinstance(role, str) or not role.strip() or role in roles:
            raise ReviewRuntimeError(f"models[{index}].role must be unique and non-empty")
        roles.add(role)
        if item.get("activation") not in {"always", "high_risk", "conflict"}:
            raise ReviewRuntimeError(f"models[{index}].activation is invalid")
        if item.get("enabled", True) not in {True, False}:
            raise ReviewRuntimeError(f"models[{index}].enabled must be boolean when present")
        if not isinstance(item.get("model"), str) or not item["model"].endswith(":free"):
            raise ReviewRuntimeError(f"models[{index}].model must name an explicit :free endpoint")
        fallbacks = item.get("fallbacks", [])
        if not isinstance(fallbacks, list) or any(
            not isinstance(value, str) or not value.endswith(":free") for value in fallbacks
        ):
            raise ReviewRuntimeError(f"models[{index}].fallbacks must contain only explicit :free endpoints")
        if item["model"] in fallbacks or len(fallbacks) != len(set(fallbacks)):
            raise ReviewRuntimeError(f"models[{index}].fallbacks must be unique and exclude the primary model")
    return data


def changed_files_from_diff(diff_text: str) -> list[str]:
    files: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path != "/dev/null":
                files.add(path)
        elif line.startswith("diff --git a/") and " b/" in line:
            path = line.split(" b/", 1)[1].strip()
            if path:
                files.add(path)
    return sorted(files)


def redact_diff(diff_text: str, max_chars: int) -> tuple[str, dict[str, Any]]:
    if max_chars < 1000:
        raise ReviewRuntimeError("max_diff_chars must be at least 1000")
    redactions = 0

    def assignment_replacer(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        return f"{match.group(1)}{match.group(2)}<REDACTED>"

    def bearer_replacer(match: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        return f"{match.group(1)}<REDACTED>"

    def private_key_replacer(_: re.Match[str]) -> str:
        nonlocal redactions
        redactions += 1
        return "<REDACTED_PRIVATE_KEY_BLOCK>"

    redacted = PRIVATE_KEY_RE.sub(private_key_replacer, diff_text)
    redacted = SENSITIVE_ASSIGNMENT_RE.sub(assignment_replacer, redacted)
    redacted = BEARER_RE.sub(bearer_replacer, redacted)
    truncated = len(redacted) > max_chars
    bounded = redacted[:max_chars]
    if truncated:
        bounded += "\n\n<DIFF_TRUNCATED_BY_LS>\n"
    return bounded, {
        "original_chars": len(diff_text),
        "sent_chars": len(bounded),
        "redaction_count": redactions,
        "truncated": truncated,
        "sha256": hashlib.sha256(diff_text.encode("utf-8")).hexdigest(),
    }


def classify_risk(changed_files: Iterable[str]) -> dict[str, Any]:
    patterns = {
        "ci": (".github/workflows/", ".github/actions/"),
        "security": ("security", "auth", "credential", "secret", "token"),
        "governance": ("governance", "approval", "decision", "merge", "deploy", "release"),
        "data": ("migration", "schema", "database", "store", "ledger"),
        "runtime": ("runtime", "executor", "scripts/"),
    }
    tags: set[str] = set()
    matched: list[str] = []
    for path in changed_files:
        lower = path.lower()
        path_tags = [tag for tag, needles in patterns.items() if any(needle in lower for needle in needles)]
        if path_tags:
            tags.update(path_tags)
            matched.append(path)
    return {"high_risk": bool(tags), "tags": sorted(tags), "matched_files": matched}


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    decoder = json.JSONDecoder()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            value, end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if stripped[index + end :].strip():
            continue
        if not isinstance(value, dict):
            raise ReviewRuntimeError("model output JSON must be an object")
        return value
    raise ReviewRuntimeError("model output does not contain one valid JSON object")


def _bounded_string(value: Any, field: str, *, max_length: int) -> str:
    if not isinstance(value, str):
        raise ReviewRuntimeError(f"{field} must be a string")
    clean = value.strip()
    if not clean:
        raise ReviewRuntimeError(f"{field} must not be empty")
    if len(clean) > max_length:
        raise ReviewRuntimeError(f"{field} exceeds {max_length} characters")
    return clean


def validate_review_payload(payload: dict[str, Any], changed_files: list[str]) -> dict[str, Any]:
    verdict = payload.get("verdict")
    if verdict not in VALID_VERDICTS:
        raise ReviewRuntimeError("verdict is invalid")
    confidence = payload.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        raise ReviewRuntimeError("confidence must be a number from 0 to 1")
    summary = _bounded_string(payload.get("summary"), "summary", max_length=2000)
    findings_raw = payload.get("findings")
    if not isinstance(findings_raw, list) or len(findings_raw) > 20:
        raise ReviewRuntimeError("findings must be an array with at most 20 entries")
    changed = set(changed_files)
    findings: list[dict[str, Any]] = []
    for index, item in enumerate(findings_raw):
        if not isinstance(item, dict):
            raise ReviewRuntimeError(f"findings[{index}] must be an object")
        severity = item.get("severity")
        if severity not in SEVERITY_ORDER:
            raise ReviewRuntimeError(f"findings[{index}].severity is invalid")
        file_path = _bounded_string(item.get("file"), f"findings[{index}].file", max_length=500)
        if file_path not in changed:
            raise ReviewRuntimeError(f"findings[{index}].file is not an exact changed file")
        line = item.get("line")
        if line is not None and (isinstance(line, bool) or not isinstance(line, int) or line <= 0):
            raise ReviewRuntimeError(f"findings[{index}].line must be a positive integer or null")
        findings.append(
            {
                "severity": severity,
                "title": _bounded_string(item.get("title"), f"findings[{index}].title", max_length=240),
                "file": file_path,
                "line": line,
                "evidence": _bounded_string(item.get("evidence"), f"findings[{index}].evidence", max_length=1500),
                "failure_scenario": _bounded_string(
                    item.get("failure_scenario"), f"findings[{index}].failure_scenario", max_length=1500
                ),
                "recommendation": _bounded_string(
                    item.get("recommendation"), f"findings[{index}].recommendation", max_length=1500
                ),
            }
        )
    uncertainties_raw = payload.get("uncertainties", [])
    if not isinstance(uncertainties_raw, list) or len(uncertainties_raw) > 20:
        raise ReviewRuntimeError("uncertainties must be an array with at most 20 entries")
    uncertainties = [
        _bounded_string(value, f"uncertainties[{index}]", max_length=500)
        for index, value in enumerate(uncertainties_raw)
    ]
    return {
        "verdict": verdict,
        "confidence": round(float(confidence), 4),
        "summary": summary,
        "findings": findings,
        "uncertainties": uncertainties,
    }
