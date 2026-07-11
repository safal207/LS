#!/usr/bin/env python3
"""Adapt external PR review threads into the LS causal-review contract."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.causal_review import ContractError, cluster_reviews, validate_review

SUPPORTED_PROVIDERS = {"coderabbit", "qodo"}
EXPECTED_AUTHORS = {
    "coderabbit": {"coderabbitai", "coderabbitai[bot]"},
    "qodo": {"qodo-code-review", "qodo-code-review[bot]"},
}
DISPLAY_NAMES = {"coderabbit": "CodeRabbit", "qodo": "Qodo"}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
RISK_FROM_SEVERITY = {
    "info": "none",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


class AdapterError(ContractError):
    """Raised when an external reviewer bundle cannot be adapted safely."""


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AdapterError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise AdapterError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise AdapterError(f"{field} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise AdapterError(f"{field} must not be empty")
    return result


def _bool(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise AdapterError(f"{field} must be a boolean")
    return value


def _line(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AdapterError(f"{field} must be null or a positive integer")
    return value


def _strip_markup(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text)
    without_markdown = re.sub(r"[`*_]+", "", without_tags)
    return " ".join(html.unescape(without_markdown).split())


def _first_match(patterns: Sequence[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            value = _strip_markup(match.group(1))
            if value:
                return value
    return None


def _qodo_title(body: str) -> str:
    title = _first_match(
        [
            r"^\s*\d+\\?\.\s*(.+?)(?:\s*<code|$)",
            r"<summary>\s*<strong>(.+?)</strong>\s*</summary>",
        ],
        body,
    )
    return title or "Qodo review finding"


def _qodo_summary(body: str) -> str:
    summary = _first_match([r"<pre>\s*(.*?)\s*</pre>"], body)
    return summary or _strip_markup(body)[:1000]


def _coderabbit_title(body: str) -> str:
    title = _first_match([r"\*\*(.+?)\*\*"], body)
    return title or "CodeRabbit review finding"


def _coderabbit_summary(body: str, title: str) -> str:
    after_title = re.split(re.escape(f"**{title}**"), body, maxsplit=1)
    candidate = after_title[1] if len(after_title) == 2 else body
    candidate = candidate.split("<details>", 1)[0]
    summary = _strip_markup(candidate)
    return summary or _strip_markup(body)[:1000]


def _severity(provider: str, body: str) -> str:
    if provider == "qodo":
        if "Action_required" in body or "Action required" in body:
            return "high"
        if "Review_recommended" in body or "Remediation recommended" in body:
            return "medium"
        return "low"

    if "_🔴 Critical_" in body:
        return "critical"
    if "_🟠 Major_" in body:
        return "high"
    if "_🟡 Minor_" in body:
        return "medium"
    if "_🟢" in body:
        return "low"
    return "medium"


def _recommendation(provider: str, body: str, summary: str) -> str:
    if provider == "qodo":
        extracted = _first_match(
            [
                r"## Implementation guidance\s*(.*?)(?:```|````|</details>|$)",
                r"## Fix Focus Areas\s*(.*?)(?:##|```|````|</details>|$)",
            ],
            body,
        )
    else:
        extracted = _first_match(
            [
                r"Prompt for AI Agents.*?```\s*(.*?)\s*```",
                r"Proposed fix.*?```(?:diff)?\s*(.*?)\s*```",
            ],
            body,
        )
    return (extracted or summary or "Review the provider finding against the exact target.")[:1200]


def _stable_token(provider: str, thread: Mapping[str, Any], title: str, summary: str) -> str:
    material = "\n".join(
        [
            provider,
            str(thread.get("id", "")),
            str(thread.get("path", "")),
            str(thread.get("line", "")),
            title,
            summary,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _author_login(thread: Mapping[str, Any]) -> str:
    author = thread.get("author")
    if isinstance(author, Mapping):
        return _string(author.get("login"), "thread.author.login")
    return _string(thread.get("author_login"), "thread.author_login")


def _adapt_thread(
    provider: str,
    thread: Mapping[str, Any],
    dedupe_overrides: Mapping[str, Any],
) -> dict[str, Any] | None:
    thread_id = _string(thread.get("id"), "thread.id")
    author_login = _author_login(thread)
    if author_login not in EXPECTED_AUTHORS[provider]:
        expected = ", ".join(sorted(EXPECTED_AUTHORS[provider]))
        raise AdapterError(
            f"thread {thread_id} author {author_login!r} does not match {provider}: {expected}"
        )

    is_resolved = _bool(thread.get("is_resolved", False), f"thread {thread_id}.is_resolved")
    is_outdated = _bool(thread.get("is_outdated", False), f"thread {thread_id}.is_outdated")
    if is_resolved or is_outdated:
        return None

    body = _string(thread.get("body"), f"thread {thread_id}.body")
    path = _string(thread.get("path"), f"thread {thread_id}.path")
    line = _line(thread.get("line"), f"thread {thread_id}.line")
    source_url = _string(
        thread.get("source_url", f"review-thread:{thread_id}"),
        f"thread {thread_id}.source_url",
    )

    if provider == "qodo":
        title = _qodo_title(body)
        summary = _qodo_summary(body)
    else:
        title = _coderabbit_title(body)
        summary = _coderabbit_summary(body, title)

    severity = _severity(provider, body)
    recommendation = _recommendation(provider, body, summary)
    token = _stable_token(provider, thread, title, summary)
    override = dedupe_overrides.get(thread_id)
    if override is None:
        dedupe_key = f"external.{provider}.{token[:16]}"
    else:
        dedupe_key = _string(override, f"dedupe_overrides.{thread_id}")

    location = path if line is None else f"{path}:{line}"
    finding_prefix = "CR" if provider == "coderabbit" else "QODO"
    confidence = {
        "low": 0.50,
        "medium": 0.65,
        "high": 0.80,
        "critical": 0.90,
    }[severity]

    return {
        "id": f"{finding_prefix}-{token[:8].upper()}",
        "severity": severity,
        "title": title[:240],
        "claim_status": "CANDIDATE",
        "location": {"path": path, "line": line},
        "causal_chain": {
            "change": f"{DISPLAY_NAMES[provider]} attached a finding to {location} on the frozen target.",
            "root_cause": summary[:1200],
            "failure_mechanism": (
                "Provider-authored causal claim; the adapter preserves the wording "
                f"without independently reproducing it: {summary[:900]}"
            ),
            "observable_effect": title[:500],
            "impact": (
                f"{DISPLAY_NAMES[provider]} classified this as {severity}; "
                "human adjudication must confirm the actual impact."
            ),
        },
        "evidence": [
            {
                "type": "other",
                "reference": source_url,
                "excerpt": summary[:800],
            }
        ],
        "confidence": confidence,
        "reproduction": "",
        "recommendation": recommendation,
        "dedupe_key": dedupe_key,
    }


def adapt_external_review(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one external reviewer bundle into a validated LS review artifact."""
    bundle = _object(bundle, "bundle")
    provider = _string(bundle.get("provider"), "provider").lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise AdapterError(
            f"provider must be one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )

    target = dict(_object(bundle.get("target"), "target"))
    execution = dict(_object(bundle.get("execution"), "execution"))
    status = _string(execution.get("status"), "execution.status")
    provenance = _string(execution.get("provenance"), "execution.provenance")
    details = _string(execution.get("details", ""), "execution.details", allow_empty=True)
    threads = _array(bundle.get("threads", []), "threads")
    overrides = _object(bundle.get("dedupe_overrides", {}), "dedupe_overrides")

    if status != "COMPLETED":
        review = {
            "schema_version": "ls.causal-review.v0.1",
            "reviewer": {
                "id": provider,
                "display_name": DISPLAY_NAMES[provider],
                "model": None,
            },
            "target": target,
            "execution": {
                "status": status,
                "provenance": provenance,
                "details": details,
            },
            "verdict": None,
            "risk_level": "none",
            "findings": [],
            "tests_to_run": [],
            "human_decision_points": [],
        }
        return validate_review(review)

    if provenance != "MATCHED":
        raise AdapterError("COMPLETED external review requires provenance=MATCHED")

    findings: list[dict[str, Any]] = []
    skipped_count = 0
    for raw_thread in threads:
        thread = _object(raw_thread, "thread")
        finding = _adapt_thread(provider, thread, overrides)
        if finding is None:
            skipped_count += 1
        else:
            findings.append(finding)

    max_severity = max(
        (finding["severity"] for finding in findings),
        key=lambda value: SEVERITY_ORDER[value],
        default="info",
    )
    decision_points = [
        (
            "Provider-local dedupe keys do not create cross-provider corroboration. "
            "Use an explicit dedupe override only after a human confirms the same root cause."
        )
    ]
    if skipped_count:
        decision_points.append(
            f"{skipped_count} resolved or outdated reviewer thread(s) were preserved in raw input but excluded from the active causal queue."
        )

    review = {
        "schema_version": "ls.causal-review.v0.1",
        "reviewer": {
            "id": provider,
            "display_name": DISPLAY_NAMES[provider],
            "model": None,
        },
        "target": target,
        "execution": {
            "status": "COMPLETED",
            "provenance": "MATCHED",
            "details": details,
        },
        "verdict": "COMMENT",
        "risk_level": RISK_FROM_SEVERITY[max_severity],
        "findings": findings,
        "tests_to_run": [],
        "human_decision_points": decision_points,
    }
    return validate_review(review)


def build_noise_report(
    bundles: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Measure deterministic queue compression for one exact frozen target."""
    if len(bundles) != len(reviews):
        raise AdapterError("bundles and reviews must have the same length")

    normalized_reviews = [validate_review(review) for review in reviews]
    clusters = cluster_reviews(normalized_reviews)
    raw_finding_count = sum(len(_array(bundle.get("threads", []), "threads")) for bundle in bundles)
    ignored_thread_count = sum(
        1
        for bundle in bundles
        for raw in _array(bundle.get("threads", []), "threads")
        if bool(_object(raw, "thread").get("is_resolved", False))
        or bool(_object(raw, "thread").get("is_outdated", False))
    )
    evidence_bound_count = sum(
        len(review["findings"])
        for review in normalized_reviews
        if review["execution"]["status"] == "COMPLETED"
    )
    corroborated_cluster_count = sum(
        cluster["status"] == "CORROBORATED" for cluster in clusters["clusters"]
    )
    incomplete_review_count = sum(
        review["execution"]["status"] != "COMPLETED" for review in normalized_reviews
    )
    adjudication_item_count = clusters["cluster_count"] + incomplete_review_count
    provider_local_key_count = sum(
        finding["dedupe_key"].startswith("external.")
        for review in normalized_reviews
        for finding in review["findings"]
    )
    explicit_override_count = evidence_bound_count - provider_local_key_count

    def reduction(numerator: int, denominator: int) -> float | None:
        return None if denominator == 0 else 1.0 - (numerator / denominator)

    return {
        "schema_version": "ls.causal-review-noise-report.v0.1",
        "target": clusters["target"],
        "review_count": len(normalized_reviews),
        "completed_review_count": clusters["completed_review_count"],
        "incomplete_review_count": incomplete_review_count,
        "raw_finding_count": raw_finding_count,
        "ignored_thread_count": ignored_thread_count,
        "evidence_bound_count": evidence_bound_count,
        "root_cause_cluster_count": clusters["cluster_count"],
        "corroborated_cluster_count": corroborated_cluster_count,
        "adjudication_item_count": adjudication_item_count,
        "provider_local_key_count": provider_local_key_count,
        "explicit_override_count": explicit_override_count,
        "contract_rejection_rate": reduction(evidence_bound_count, raw_finding_count),
        "causal_deduplication_rate": reduction(
            clusters["cluster_count"], evidence_bound_count
        ),
        "human_queue_reduction": reduction(
            adjudication_item_count, raw_finding_count
        ),
        "clusters": clusters["clusters"],
    }


def _read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AdapterError(f"{path} must contain one JSON object")
    return payload


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    adapt = subparsers.add_parser("adapt")
    adapt.add_argument("input")
    adapt.add_argument("--output", required=True)

    report = subparsers.add_parser("report")
    report.add_argument("inputs", nargs="+")
    report.add_argument("--reviews", nargs="+", required=True)
    report.add_argument("--output", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "adapt":
            _write_json(args.output, adapt_external_review(_read_json(args.input)))
        else:
            if len(args.inputs) != len(args.reviews):
                raise AdapterError("--reviews must contain one path per input bundle")
            bundles = [_read_json(path) for path in args.inputs]
            reviews = [_read_json(path) for path in args.reviews]
            _write_json(args.output, build_noise_report(bundles, reviews))
    except (AdapterError, ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"causal-review adapter error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
