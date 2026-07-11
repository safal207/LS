#!/usr/bin/env python3
"""Provider-neutral LS causal review contract and deterministic clustering."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "ls.causal-review.v0.1"
EXECUTION_STATUSES = {"COMPLETED", "NOT_RUN", "FAILED", "DIAGNOSTIC"}
PROVENANCE_STATUSES = {"MATCHED", "MISSING", "MISMATCH", "UNVERIFIED"}
VERDICTS = {"APPROVE", "COMMENT", "REQUEST_CHANGES"}
RISK_LEVELS = {"none", "low", "medium", "high", "critical"}
SEVERITIES = {"info", "low", "medium", "high", "critical"}
CLAIM_STATUSES = {
    "CANDIDATE",
    "REPRODUCED",
    "CONFIRMED",
    "REJECTED",
    "REQUIRES_HUMAN_DECISION",
}
EVIDENCE_TYPES = {"patch", "test", "workflow", "spec", "runtime", "other"}
CAUSAL_KEYS = (
    "change",
    "root_cause",
    "failure_mechanism",
    "observable_effect",
    "impact",
)
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
PATCH_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
DEDUPE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._:/-]{2,127}$")
SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


class ContractError(ValueError):
    """Raised when a review violates the LS causal review contract."""


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContractError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ContractError(f"{field} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise ContractError(f"{field} must not be empty")
    return result


def _string_list(value: Any, field: str) -> list[str]:
    items = _list(value, field)
    return [_string(item, f"{field}[{index}]") for index, item in enumerate(items)]


def _enum(value: Any, field: str, allowed: set[str]) -> str:
    result = _string(value, field)
    if result not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ContractError(f"{field} must be one of: {choices}")
    return result


def _optional_line(value: Any, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ContractError(f"{field} must be null or a positive integer")
    return value


def parse_model_json(text: str) -> dict[str, Any]:
    """Parse a model response that is raw JSON or one fenced JSON object."""
    candidate = _string(text, "model response")
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, re.DOTALL | re.IGNORECASE)
    if fence:
        candidate = fence.group(1).strip()
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ContractError(
            f"model response is not one JSON object: line {exc.lineno}, column {exc.colno}"
        ) from exc
    if not isinstance(payload, dict):
        raise ContractError("model response JSON must be an object")
    return payload


def validate_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize one complete causal review envelope."""
    review = copy.deepcopy(dict(_mapping(payload, "review")))

    if review.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version must equal {SCHEMA_VERSION}")

    reviewer = _mapping(review.get("reviewer"), "reviewer")
    reviewer_id = _string(reviewer.get("id"), "reviewer.id")
    display_name = _string(reviewer.get("display_name"), "reviewer.display_name")
    model = reviewer.get("model")
    if model is not None:
        model = _string(model, "reviewer.model")

    target = _mapping(review.get("target"), "target")
    repository = _string(target.get("repository"), "target.repository")
    pr_number = target.get("pr_number")
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number < 1:
        raise ContractError("target.pr_number must be a positive integer")
    head_sha = _string(target.get("head_sha"), "target.head_sha").lower()
    if not SHA_RE.fullmatch(head_sha):
        raise ContractError("target.head_sha must be a 40-character lowercase Git SHA")
    patch_sha256 = _string(target.get("patch_sha256"), "target.patch_sha256").lower()
    if not PATCH_DIGEST_RE.fullmatch(patch_sha256):
        raise ContractError("target.patch_sha256 must be sha256:<64 lowercase hex>")

    execution = _mapping(review.get("execution"), "execution")
    execution_status = _enum(
        execution.get("status"), "execution.status", EXECUTION_STATUSES
    )
    provenance = _enum(
        execution.get("provenance"), "execution.provenance", PROVENANCE_STATUSES
    )
    details = _string(
        execution.get("details", ""),
        "execution.details",
        allow_empty=True,
    )

    verdict_raw = review.get("verdict")
    verdict = None if verdict_raw is None else _enum(verdict_raw, "verdict", VERDICTS)
    risk_level = _enum(review.get("risk_level"), "risk_level", RISK_LEVELS)
    findings_raw = _list(review.get("findings"), "findings")

    if execution_status == "COMPLETED":
        if provenance != "MATCHED":
            raise ContractError(
                "COMPLETED review requires execution.provenance=MATCHED"
            )
        if verdict is None:
            raise ContractError("COMPLETED review requires a verdict")
    else:
        if verdict is not None:
            raise ContractError(
                f"{execution_status} review must not publish a verdict"
            )
        if findings_raw:
            raise ContractError(
                f"{execution_status} review must not publish model findings"
            )
        if risk_level != "none":
            raise ContractError(
                f"{execution_status} review requires risk_level=none"
            )

    if verdict == "REQUEST_CHANGES" and not findings_raw:
        raise ContractError("REQUEST_CHANGES requires at least one finding")

    normalized_findings: list[dict[str, Any]] = []
    finding_ids: set[str] = set()
    for index, raw_finding in enumerate(findings_raw):
        prefix = f"findings[{index}]"
        finding = _mapping(raw_finding, prefix)
        finding_id = _string(finding.get("id"), f"{prefix}.id")
        if finding_id in finding_ids:
            raise ContractError(f"duplicate finding id: {finding_id}")
        finding_ids.add(finding_id)

        severity = _enum(finding.get("severity"), f"{prefix}.severity", SEVERITIES)
        title = _string(finding.get("title"), f"{prefix}.title")
        claim_status = _enum(
            finding.get("claim_status", "CANDIDATE"),
            f"{prefix}.claim_status",
            CLAIM_STATUSES,
        )

        location = _mapping(finding.get("location"), f"{prefix}.location")
        path = _string(location.get("path"), f"{prefix}.location.path")
        line = _optional_line(location.get("line"), f"{prefix}.location.line")

        causal_chain = _mapping(
            finding.get("causal_chain"), f"{prefix}.causal_chain"
        )
        normalized_chain = {
            key: _string(causal_chain.get(key), f"{prefix}.causal_chain.{key}")
            for key in CAUSAL_KEYS
        }

        evidence_raw = _list(finding.get("evidence"), f"{prefix}.evidence")
        if not evidence_raw:
            raise ContractError(f"{prefix}.evidence must contain at least one item")
        evidence: list[dict[str, str]] = []
        for evidence_index, raw_item in enumerate(evidence_raw):
            item_prefix = f"{prefix}.evidence[{evidence_index}]"
            item = _mapping(raw_item, item_prefix)
            evidence_type = _enum(
                item.get("type"), f"{item_prefix}.type", EVIDENCE_TYPES
            )
            reference = _string(item.get("reference"), f"{item_prefix}.reference")
            excerpt = _string(
                item.get("excerpt", ""),
                f"{item_prefix}.excerpt",
                allow_empty=True,
            )
            evidence.append(
                {
                    "type": evidence_type,
                    "reference": reference,
                    "excerpt": excerpt,
                }
            )

        confidence = finding.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ContractError(f"{prefix}.confidence must be a number")
        confidence = float(confidence)
        if not 0.0 <= confidence <= 1.0:
            raise ContractError(f"{prefix}.confidence must be between 0 and 1")

        reproduction = _string(
            finding.get("reproduction", ""),
            f"{prefix}.reproduction",
            allow_empty=True,
        )
        recommendation = _string(
            finding.get("recommendation"), f"{prefix}.recommendation"
        )
        dedupe_key = _string(
            finding.get("dedupe_key"), f"{prefix}.dedupe_key"
        ).lower()
        if not DEDUPE_KEY_RE.fullmatch(dedupe_key):
            raise ContractError(
                f"{prefix}.dedupe_key must match {DEDUPE_KEY_RE.pattern}"
            )

        normalized_findings.append(
            {
                "id": finding_id,
                "severity": severity,
                "title": title,
                "claim_status": claim_status,
                "location": {"path": path, "line": line},
                "causal_chain": normalized_chain,
                "evidence": evidence,
                "confidence": confidence,
                "reproduction": reproduction,
                "recommendation": recommendation,
                "dedupe_key": dedupe_key,
            }
        )

    tests_to_run = _string_list(review.get("tests_to_run"), "tests_to_run")
    human_decision_points = _string_list(
        review.get("human_decision_points"), "human_decision_points"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "reviewer": {
            "id": reviewer_id,
            "display_name": display_name,
            "model": model,
        },
        "target": {
            "repository": repository,
            "pr_number": pr_number,
            "head_sha": head_sha,
            "patch_sha256": patch_sha256,
        },
        "execution": {
            "status": execution_status,
            "provenance": provenance,
            "details": details,
        },
        "verdict": verdict,
        "risk_level": risk_level,
        "findings": normalized_findings,
        "tests_to_run": tests_to_run,
        "human_decision_points": human_decision_points,
    }


def cluster_reviews(payloads: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Cluster evidence-bound findings by explicit root-cause dedupe key."""
    reviews = [validate_review(payload) for payload in payloads]
    clusters: dict[str, dict[str, Any]] = {}

    for review in reviews:
        if review["execution"]["status"] != "COMPLETED":
            continue
        reviewer_id = review["reviewer"]["id"]
        for finding in review["findings"]:
            if finding["claim_status"] == "REJECTED":
                continue
            key = finding["dedupe_key"]
            cluster = clusters.setdefault(
                key,
                {
                    "dedupe_key": key,
                    "titles": [],
                    "reviewer_ids": set(),
                    "finding_ids": [],
                    "severities": [],
                    "confidences": [],
                    "evidence_count": 0,
                    "locations": [],
                },
            )
            cluster["titles"].append(finding["title"])
            cluster["reviewer_ids"].add(reviewer_id)
            cluster["finding_ids"].append(f"{reviewer_id}:{finding['id']}")
            cluster["severities"].append(finding["severity"])
            cluster["confidences"].append(finding["confidence"])
            cluster["evidence_count"] += len(finding["evidence"])
            cluster["locations"].append(finding["location"])

    output_clusters: list[dict[str, Any]] = []
    for key in sorted(clusters):
        cluster = clusters[key]
        reviewer_ids = sorted(cluster["reviewer_ids"])
        max_severity = max(
            cluster["severities"], key=lambda value: SEVERITY_ORDER[value]
        )
        output_clusters.append(
            {
                "dedupe_key": key,
                "title": cluster["titles"][0],
                "support_count": len(reviewer_ids),
                "reviewer_ids": reviewer_ids,
                "finding_ids": sorted(cluster["finding_ids"]),
                "max_severity": max_severity,
                "max_confidence": max(cluster["confidences"]),
                "evidence_count": cluster["evidence_count"],
                "locations": cluster["locations"],
                "status": (
                    "CORROBORATED"
                    if len(reviewer_ids) >= 2
                    else "SINGLE_REVIEWER"
                ),
            }
        )

    return {
        "schema_version": "ls.causal-review-clusters.v0.1",
        "review_count": len(reviews),
        "completed_review_count": sum(
            review["execution"]["status"] == "COMPLETED" for review in reviews
        ),
        "cluster_count": len(output_clusters),
        "clusters": output_clusters,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    """Render a validated causal review into concise human-readable Markdown."""
    review = validate_review(payload)
    reviewer = review["reviewer"]
    target = review["target"]
    execution = review["execution"]

    lines = [
        f"_Reviewer: `{reviewer['id']}`"
        + (f"; model: `{reviewer['model']}`" if reviewer["model"] else "")
        + f". Target: `{target['head_sha']}`. Patch: `{target['patch_sha256']}`._",
        "",
        f"**Execution:** `{execution['status']}` · provenance `{execution['provenance']}`",
    ]
    if execution["details"]:
        lines.extend(["", execution["details"]])

    if execution["status"] != "COMPLETED":
        lines.extend(
            [
                "",
                "⚠️ No model verdict or findings were accepted from this lane.",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    lines.extend(
        [
            "",
            f"## Verdict: {review['verdict']}",
            "",
            f"Risk level: **{review['risk_level']}**",
        ]
    )

    if not review["findings"]:
        lines.extend(["", "_No evidence-bound findings._"])
    else:
        lines.extend(["", "## Causal findings"])
        for finding in review["findings"]:
            location = finding["location"]["path"]
            if finding["location"]["line"] is not None:
                location += f":{finding['location']['line']}"
            chain = finding["causal_chain"]
            lines.extend(
                [
                    "",
                    f"### {finding['id']} · {finding['severity']} · {finding['title']}",
                    "",
                    f"`{location}` · confidence `{finding['confidence']:.2f}` · "
                    f"status `{finding['claim_status']}`",
                    "",
                    "```text",
                    f"Change: {chain['change']}",
                    f"  → Root cause: {chain['root_cause']}",
                    f"  → Failure mechanism: {chain['failure_mechanism']}",
                    f"  → Observable effect: {chain['observable_effect']}",
                    f"  → Impact: {chain['impact']}",
                    "```",
                    "",
                    f"**Root-cause key:** `{finding['dedupe_key']}`",
                    "",
                    "**Evidence:**",
                ]
            )
            for item in finding["evidence"]:
                evidence_line = f"- `{item['type']}` {item['reference']}"
                if item["excerpt"]:
                    evidence_line += f" — {item['excerpt']}"
                lines.append(evidence_line)
            if finding["reproduction"]:
                lines.extend(["", f"**Reproduction:** {finding['reproduction']}"])
            lines.extend(
                ["", f"**Recommendation:** {finding['recommendation']}"]
            )

    if review["tests_to_run"]:
        lines.extend(["", "## Tests to add or run"])
        lines.extend(f"- {item}" for item in review["tests_to_run"])

    if review["human_decision_points"]:
        lines.extend(["", "## Human decision points"])
        lines.extend(f"- {item}" for item in review["human_decision_points"])

    return "\n".join(lines).rstrip() + "\n"


def _read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ContractError(f"{path} must contain one JSON object")
    return value


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("input")
    validate_parser.add_argument("--normalized")
    validate_parser.add_argument("--markdown")

    cluster_parser = subparsers.add_parser("cluster")
    cluster_parser.add_argument("inputs", nargs="+")
    cluster_parser.add_argument("--output", required=True)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("input")
    render_parser.add_argument("--output", required=True)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            review = validate_review(_read_json(args.input))
            if args.normalized:
                _write_json(args.normalized, review)
            if args.markdown:
                Path(args.markdown).write_text(
                    render_markdown(review), encoding="utf-8"
                )
            if not args.normalized and not args.markdown:
                print(json.dumps(review, indent=2, sort_keys=True))
        elif args.command == "cluster":
            result = cluster_reviews(_read_json(path) for path in args.inputs)
            _write_json(args.output, result)
        elif args.command == "render":
            Path(args.output).write_text(
                render_markdown(_read_json(args.input)), encoding="utf-8"
            )
    except (ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"causal-review contract error: {exc}", file=__import__("sys").stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
