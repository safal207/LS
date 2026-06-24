"""Policy helpers for OVC -> VerifiedEpisode v0.2."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

SEVERITY = {
    "WRITE_CANDIDATE": 0,
    "ABSTAIN": 1,
    "FORGET": 2,
    "REVIEW": 3,
    "REJECT": 4,
}

REASON_ORDER = {
    "REJECT": [
        "OVC_SAFETY_INVARIANT_VIOLATION",
        "OVC_NOT_VERIFIED",
        "EXPERIENCE_NOT_ELIGIBLE",
        "MISSING_IDENTITY_BINDING",
        "MISSING_PROVENANCE",
        "EPISODE_REPLAY",
        "CAUSAL_TRACE_REPLAY",
        "INVALID_RETENTION_WINDOW",
        "UNSUPPORTED_VERSION",
    ],
    "REVIEW": [
        "OVC_OUTCOME_REASON_MISMATCH",
        "LESSON_OUTCOME_MISMATCH",
    ],
    "FORGET": ["RETENTION_EXPIRED"],
    "ABSTAIN": [
        "REDACTION_INCOMPLETE",
        "MISSING_LESSON_EVIDENCE",
    ],
}


def parse_timestamp(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def choose(faults: list[tuple[str, str]]) -> tuple[str, str]:
    if not faults:
        return "WRITE_CANDIDATE", "VERIFIED_EXPERIENCE_READY"

    severity = max(SEVERITY[verdict] for verdict, _ in faults)
    verdict = next(
        name for name, value in SEVERITY.items() if value == severity
    )
    reasons = {reason for candidate, reason in faults if candidate == verdict}

    for reason in REASON_ORDER[verdict]:
        if reason in reasons:
            return verdict, reason

    return verdict, sorted(reasons)[0]


def stable_episode_id(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"episode:sha256:{digest}"
