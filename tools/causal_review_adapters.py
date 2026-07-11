#!/usr/bin/env python3
"""Adapt external review threads into evidence-bound LS causal artifacts."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.causal_review import ContractError, cluster_reviews, validate_review

PROVIDERS = {
    "coderabbit": {
        "display_name": "CodeRabbit",
        "authors": {"coderabbitai", "coderabbitai[bot]"},
        "finding_prefix": "CR",
    },
    "qodo": {
        "display_name": "Qodo",
        "authors": {"qodo-code-review", "qodo-code-review[bot]"},
        "finding_prefix": "QODO",
    },
}
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
RISK_FROM_SEVERITY = {
    "info": "none",
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}


class AdapterError(ContractError):
    """Raised when a provider bundle cannot be adapted without guessing."""


def _object(value: Any, field: str) -> Mapping[str, Any]:
    """Require one mapping value."""
    if not isinstance(value, Mapping):
        raise AdapterError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    """Require one list value."""
    if not isinstance(value, list):
        raise AdapterError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    """Require and trim one string value."""
    if not isinstance(value, str):
        raise AdapterError(f"{field} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise AdapterError(f"{field} must not be empty")
    return result


def _boolean(value: Any, field: str) -> bool:
    """Require one boolean value."""
    if not isinstance(value, bool):
        raise AdapterError(f"{field} must be a boolean")
    return value


def _line(value: Any, field: str) -> int | None:
    """Require a positive line number or null."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AdapterError(f"{field} must be null or a positive integer")
    return value


def _plain(text: str) -> str:
    """Remove lightweight HTML/Markdown while preserving reviewer wording."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[`*_]+", "", text)
    return " ".join(html.unescape(text).split())


def _match(text: str, *patterns: str) -> str | None:
    """Return the first non-empty normalized regex capture."""
    for pattern in patterns:
        found = re.search(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if found:
            value = _plain(found.group(1))
            if value:
                return value
    return None


def _provider_text(provider: str, body: str) -> tuple[str, str, str, str]:
    """Extract title, summary, recommendation, and severity deterministically."""
    if provider == "qodo":
        title = _match(
            body,
            r"^\s*\d+\\?\.\s*(.+?)(?:\s*<code|$)",
            r"<summary>\s*<strong>(.+?)</strong>\s*</summary>",
        ) or "Qodo review finding"
        summary = _match(body, r"<pre>\s*(.*?)\s*</pre>") or _plain(body)[:1000]
        recommendation = _match(
            body,
            r"## Implementation guidance\s*(.*?)(?:```|````|</details>|$)",
            r"## Fix Focus Areas\s*(.*?)(?:##|```|````|</details>|$)",
        )
        severity = (
            "high"
            if "Action_required" in body or "Action required" in body
            else "medium"
            if "Review_recommended" in body or "Remediation recommended" in body
            else "low"
        )
    else:
        title = _match(body, r"\*\*(.+?)\*\*") or "CodeRabbit review finding"
        remainder = re.split(re.escape(f"**{title}**"), body, maxsplit=1)
        summary = _plain((remainder[1] if len(remainder) == 2 else body).split("<details>", 1)[0])
        summary = summary or _plain(body)[:1000]
        recommendation = _match(
            body,
            r"Prompt for AI Agents.*?```\s*(.*?)\s*```",
            r"Proposed fix.*?```(?:diff)?\s*(.*?)\s*```",
        )
        severity = (
            "critical"
            if "_🔴 Critical_" in body
            else "high"
            if "_🟠 Major_" in body
            else "medium"
            if "_🟡 Minor_" in body
            else "low"
            if "_🟢" in body
            else "medium"
        )
    return title, summary, (recommendation or summary)[:1200], severity


def _author_login(thread: Mapping[str, Any]) -> str:
    """Read the normalized provider login from a thread export."""
    author = thread.get("author")
    if isinstance(author, Mapping):
        return _string(author.get("login"), "thread.author.login")
    return _string(thread.get("author_login"), "thread.author_login")


def _token(provider: str, thread: Mapping[str, Any], title: str, summary: str) -> str:
    """Build a stable provider-local identity without semantic deduplication."""
    material = "\n".join(
        str(value)
        for value in (
            provider,
            thread.get("id", ""),
            thread.get("path", ""),
            thread.get("line", ""),
            title,
            summary,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _adapt_thread(
    provider: str,
    thread: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Convert one active provider thread into a candidate causal finding."""
    thread_id = _string(thread.get("id"), "thread.id")
    login = _author_login(thread)
    expected = PROVIDERS[provider]["authors"]
    if login not in expected:
        raise AdapterError(
            f"thread {thread_id} author {login!r} does not match {provider}: "
            + ", ".join(sorted(expected))
        )

    resolved = _boolean(thread.get("is_resolved", False), f"thread {thread_id}.is_resolved")
    outdated = _boolean(thread.get("is_outdated", False), f"thread {thread_id}.is_outdated")
    if resolved or outdated:
        return None

    body = _string(thread.get("body"), f"thread {thread_id}.body")
    path = _string(thread.get("path"), f"thread {thread_id}.path")
    line = _line(thread.get("line"), f"thread {thread_id}.line")
    reference = _string(
        thread.get("source_url", f"review-thread:{thread_id}"),
        f"thread {thread_id}.source_url",
    )
    title, summary, recommendation, severity = _provider_text(provider, body)
    token = _token(provider, thread, title, summary)

    override = overrides.get(thread_id)
    if override is None:
        dedupe_key = f"external.{provider}.{token[:16]}"
    else:
        dedupe_key = _string(override, f"dedupe_overrides.{thread_id}")
        if dedupe_key.startswith("external."):
            raise AdapterError(
                f"dedupe_overrides.{thread_id} must not use the reserved external. prefix"
            )

    location = path if line is None else f"{path}:{line}"
    confidence = {"low": 0.50, "medium": 0.65, "high": 0.80, "critical": 0.90}[severity]
    display = PROVIDERS[provider]["display_name"]
    return {
        "id": f"{PROVIDERS[provider]['finding_prefix']}-{token[:8].upper()}",
        "severity": severity,
        "title": title[:240],
        "claim_status": "CANDIDATE",
        "location": {"path": path, "line": line},
        "causal_chain": {
            "change": f"{display} attached a finding to {location} on the frozen target.",
            "root_cause": summary[:1200],
            "failure_mechanism": (
                "Provider-authored causal claim; the adapter preserves the wording without "
                f"independently reproducing it: {summary[:900]}"
            ),
            "observable_effect": title[:500],
            "impact": (
                f"{display} classified this as {severity}; human adjudication must confirm "
                "the actual impact."
            ),
        },
        "evidence": [{"type": "other", "reference": reference, "excerpt": summary[:800]}],
        "confidence": confidence,
        "reproduction": "",
        "recommendation": recommendation,
        "dedupe_key": dedupe_key,
    }


def adapt_external_review(bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one provider bundle into a validated LS review artifact."""
    bundle = _object(bundle, "bundle")
    provider = _string(bundle.get("provider"), "provider").lower()
    if provider not in PROVIDERS:
        raise AdapterError(f"provider must be one of: {', '.join(sorted(PROVIDERS))}")

    target = dict(_object(bundle.get("target"), "target"))
    execution = _object(bundle.get("execution"), "execution")
    status = _string(execution.get("status"), "execution.status")
    provenance = _string(execution.get("provenance"), "execution.provenance")
    details = _string(execution.get("details", ""), "execution.details", allow_empty=True)
    threads = _array(bundle.get("threads", []), "threads")
    overrides = _object(bundle.get("dedupe_overrides", {}), "dedupe_overrides")
    display = PROVIDERS[provider]["display_name"]

    if status != "COMPLETED":
        return validate_review(
            {
                "schema_version": "ls.causal-review.v0.1",
                "reviewer": {"id": provider, "display_name": display, "model": None},
                "target": target,
                "execution": {"status": status, "provenance": provenance, "details": details},
                "verdict": None,
                "risk_level": "none",
                "findings": [],
                "tests_to_run": [],
                "human_decision_points": [],
            }
        )
    if provenance != "MATCHED":
        raise AdapterError("COMPLETED external review requires provenance=MATCHED")

    findings: list[dict[str, Any]] = []
    ignored = 0
    for raw_thread in threads:
        finding = _adapt_thread(provider, _object(raw_thread, "thread"), overrides)
        if finding is None:
            ignored += 1
        else:
            findings.append(finding)

    max_severity = max(
        (finding["severity"] for finding in findings),
        key=lambda value: SEVERITY_ORDER[value],
        default="info",
    )
    decisions = [
        "Provider-local dedupe keys do not create cross-provider corroboration. Use an explicit "
        "dedupe override only after a human confirms the same root cause."
    ]
    if ignored:
        decisions.append(
            f"{ignored} resolved or outdated reviewer thread(s) were preserved in raw input "
            "but excluded from the active causal queue."
        )

    return validate_review(
        {
            "schema_version": "ls.causal-review.v0.1",
            "reviewer": {"id": provider, "display_name": display, "model": None},
            "target": target,
            "execution": {"status": "COMPLETED", "provenance": "MATCHED", "details": details},
            "verdict": "COMMENT",
            "risk_level": RISK_FROM_SEVERITY[max_severity],
            "findings": findings,
            "tests_to_run": [],
            "human_decision_points": decisions,
        }
    )


def _bind_bundle_to_review(bundle: Mapping[str, Any], review: Mapping[str, Any], index: int) -> None:
    """Prevent raw metrics from being paired with a different reviewer or target."""
    provider = _string(bundle.get("provider"), f"bundles[{index}].provider").lower()
    target = dict(_object(bundle.get("target"), f"bundles[{index}].target"))
    if provider != review["reviewer"]["id"]:
        raise AdapterError(
            f"bundle/review provider mismatch at index {index}: {provider} != "
            f"{review['reviewer']['id']}"
        )
    if target != review["target"]:
        raise AdapterError(f"bundle/review target mismatch at index {index}")


def build_noise_report(
    bundles: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Measure deterministic queue compression for one exact frozen target."""
    if len(bundles) != len(reviews):
        raise AdapterError("bundles and reviews must have the same length")
    normalized = [validate_review(review) for review in reviews]
    for index, (bundle, review) in enumerate(zip(bundles, normalized, strict=True)):
        _bind_bundle_to_review(_object(bundle, f"bundles[{index}]"), review, index)

    clusters = cluster_reviews(normalized)
    raw_count = sum(len(_array(bundle.get("threads", []), "threads")) for bundle in bundles)
    ignored_count = sum(
        1
        for bundle in bundles
        for raw in _array(bundle.get("threads", []), "threads")
        if bool(_object(raw, "thread").get("is_resolved", False))
        or bool(_object(raw, "thread").get("is_outdated", False))
    )
    evidence_count = sum(
        len(review["findings"])
        for review in normalized
        if review["execution"]["status"] == "COMPLETED"
    )
    corroborated_count = sum(
        cluster["status"] == "CORROBORATED" for cluster in clusters["clusters"]
    )
    incomplete_count = sum(review["execution"]["status"] != "COMPLETED" for review in normalized)
    queue_count = clusters["cluster_count"] + incomplete_count
    local_key_count = sum(
        finding["dedupe_key"].startswith("external.")
        for review in normalized
        for finding in review["findings"]
    )

    def reduction(numerator: int, denominator: int) -> float | None:
        return None if denominator == 0 else 1.0 - (numerator / denominator)

    return {
        "schema_version": "ls.causal-review-noise-report.v0.1",
        "target": clusters["target"],
        "review_count": len(normalized),
        "completed_review_count": clusters["completed_review_count"],
        "incomplete_review_count": incomplete_count,
        "raw_finding_count": raw_count,
        "ignored_thread_count": ignored_count,
        "evidence_bound_count": evidence_count,
        "root_cause_cluster_count": clusters["cluster_count"],
        "corroborated_cluster_count": corroborated_count,
        "adjudication_item_count": queue_count,
        "provider_local_key_count": local_key_count,
        "explicit_override_count": evidence_count - local_key_count,
        "contract_rejection_rate": reduction(evidence_count, raw_count),
        "causal_deduplication_rate": reduction(clusters["cluster_count"], evidence_count),
        "human_queue_reduction": reduction(queue_count, raw_count),
        "clusters": clusters["clusters"],
    }


def _read_json(path: str | Path) -> dict[str, Any]:
    """Read one JSON object from disk."""
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AdapterError(f"{path} must contain one JSON object")
    return payload


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    """Write stable formatted JSON to disk."""
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    """Build the adapter command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    adapt = commands.add_parser("adapt")
    adapt.add_argument("input")
    adapt.add_argument("--output", required=True)
    report = commands.add_parser("report")
    report.add_argument("inputs", nargs="+")
    report.add_argument("--reviews", nargs="+", required=True)
    report.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the adapter CLI."""
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
