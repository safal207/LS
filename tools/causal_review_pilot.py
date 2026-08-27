#!/usr/bin/env python3
"""Build one provisional causal-review pilot report across reviewer types."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.causal_review import ContractError, cluster_reviews, validate_review

MEASUREMENT_CLASSES = {"DEMO", "PILOT", "ENSEMBLE"}
THREAD_PROVIDERS = {"coderabbit", "qodo"}


class PilotError(ContractError):
    """Raised when raw evidence cannot be bound to its adapted review."""


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PilotError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise PilotError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PilotError(f"{field} must be a string")
    result = value.strip()
    if not allow_empty and not result:
        raise PilotError(f"{field} must not be empty")
    return result


def _boolean(value: Any, field: str) -> bool:
    if not isinstance(value, bool):
        raise PilotError(f"{field} must be a boolean")
    return value


def _execution(raw: Mapping[str, Any], field: str) -> tuple[str, str, str]:
    execution = _object(raw.get("execution"), f"{field}.execution")
    return (
        _string(execution.get("status"), f"{field}.execution.status"),
        _string(execution.get("provenance"), f"{field}.execution.provenance"),
        _string(
            execution.get("details", ""),
            f"{field}.execution.details",
            allow_empty=True,
        ),
    )


def _raw_identity(
    raw: Mapping[str, Any], index: int
) -> tuple[str, Mapping[str, Any], str, str, str, int, int]:
    field = f"raw_bundles[{index}]"
    target = _object(raw.get("target"), f"{field}.target")
    status, provenance, details = _execution(raw, field)

    provider_value = raw.get("provider")
    if provider_value is not None:
        provider = _string(provider_value, f"{field}.provider").lower()
        if provider not in THREAD_PROVIDERS:
            raise PilotError(
                f"{field}.provider must be one of: {', '.join(sorted(THREAD_PROVIDERS))}"
            )
        threads = _array(raw.get("threads"), f"{field}.threads")
        ignored = 0
        for thread_index, raw_thread in enumerate(threads):
            thread = _object(
                raw_thread, f"{field}.threads[{thread_index}]"
            )
            resolved = _boolean(
                thread.get("is_resolved", False),
                f"{field}.threads[{thread_index}].is_resolved",
            )
            outdated = _boolean(
                thread.get("is_outdated", False),
                f"{field}.threads[{thread_index}].is_outdated",
            )
            ignored += int(resolved or outdated)
        return (
            provider,
            target,
            status,
            provenance,
            details,
            len(threads),
            ignored,
        )

    schema_version = _string(
        raw.get("schema_version"), f"{field}.schema_version"
    )
    if schema_version == "ls.deepseek-causal-lane.v0.1":
        findings = _array(raw.get("findings"), f"{field}.findings")
        return (
            "deepseek",
            target,
            status,
            provenance,
            details,
            len(findings),
            0,
        )

    if schema_version == "ls.causal-review.v0.1":
        review = validate_review(raw)
        provider = _string(
            _object(review.get("reviewer"), f"{field}.reviewer").get("id"),
            f"{field}.reviewer.id",
        )
        return (
            provider,
            review["target"],
            review["execution"]["status"],
            review["execution"]["provenance"],
            review["execution"]["details"],
            len(review["findings"]),
            0,
        )

    raise PilotError(
        f"{field} is not a thread bundle, DeepSeek lane, or native causal review"
    )


def _bind_raw_to_review(
    raw: Mapping[str, Any],
    review: Mapping[str, Any],
    index: int,
) -> dict[str, Any]:
    (
        provider,
        target,
        status,
        provenance,
        details,
        raw_count,
        ignored_count,
    ) = _raw_identity(raw, index)
    if provider != review["reviewer"]["id"]:
        raise PilotError(
            f"raw/review provider mismatch at index {index}: {provider} != "
            f"{review['reviewer']['id']}"
        )
    if dict(target) != review["target"]:
        raise PilotError(f"raw/review target mismatch at index {index}")
    if status != review["execution"]["status"]:
        raise PilotError(
            f"raw/review execution status mismatch at index {index}: "
            f"{status} != {review['execution']['status']}"
        )
    if provenance != review["execution"]["provenance"]:
        raise PilotError(
            f"raw/review provenance mismatch at index {index}: "
            f"{provenance} != {review['execution']['provenance']}"
        )

    expected_findings = (
        raw_count - ignored_count if status == "COMPLETED" else 0
    )
    actual_findings = len(review["findings"])
    if actual_findings != expected_findings:
        raise PilotError(
            f"raw/review finding count mismatch at index {index}: "
            f"expected {expected_findings}, got {actual_findings}"
        )

    return {
        "provider": provider,
        "status": status,
        "provenance": provenance,
        "details": details,
        "raw_count": raw_count,
        "ignored_count": ignored_count,
    }


def _reduction(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else 1.0 - (numerator / denominator)


def build_pilot_report(
    raw_bundles: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
    *,
    measurement_class: str = "DEMO",
) -> dict[str, Any]:
    """Build a provisional multi-provider report for one exact target."""
    if len(raw_bundles) != len(reviews):
        raise PilotError("raw_bundles and reviews must have the same length")
    if not raw_bundles:
        raise PilotError("pilot report requires at least one reviewer lane")
    measurement_class = _string(measurement_class, "measurement_class").upper()
    if measurement_class not in MEASUREMENT_CLASSES:
        raise PilotError(
            "measurement_class must be one of: "
            + ", ".join(sorted(MEASUREMENT_CLASSES))
        )

    normalized = [validate_review(review) for review in reviews]
    lanes = [
        _bind_raw_to_review(_object(raw, f"raw_bundles[{index}]"), review, index)
        for index, (raw, review) in enumerate(
            zip(raw_bundles, normalized, strict=True)
        )
    ]
    providers = [lane["provider"] for lane in lanes]
    duplicates = sorted(
        provider for provider in set(providers) if providers.count(provider) > 1
    )
    if duplicates:
        raise PilotError(
            "pilot report allows one lane per provider; duplicates: "
            + ", ".join(duplicates)
        )

    clusters = cluster_reviews(normalized)
    raw_count = sum(lane["raw_count"] for lane in lanes)
    ignored_count = sum(lane["ignored_count"] for lane in lanes)
    evidence_count = sum(
        len(review["findings"])
        for review in normalized
        if review["execution"]["status"] == "COMPLETED"
    )
    incomplete_lanes = [
        {
            "provider": lane["provider"],
            "status": lane["status"],
            "provenance": lane["provenance"],
            "details": lane["details"],
        }
        for lane in lanes
        if lane["status"] != "COMPLETED"
    ]
    corroborated_count = sum(
        cluster["status"] == "CORROBORATED"
        for cluster in clusters["clusters"]
    )
    adjudication_count = clusters["cluster_count"] + len(incomplete_lanes)

    return {
        "schema_version": "ls.causal-review-pilot-report.v0.1",
        "measurement_class": measurement_class,
        "measurement_status": "PROVISIONAL",
        "production_claim_allowed": False,
        "human_adjudication": "PENDING",
        "target": clusters["target"],
        "review_count": len(normalized),
        "completed_review_count": clusters["completed_review_count"],
        "incomplete_review_count": len(incomplete_lanes),
        "raw_finding_count": raw_count,
        "ignored_thread_count": ignored_count,
        "evidence_bound_count": evidence_count,
        "root_cause_cluster_count": clusters["cluster_count"],
        "corroborated_cluster_count": corroborated_count,
        "adjudication_item_count": adjudication_count,
        "contract_rejection_rate": _reduction(evidence_count, raw_count),
        "causal_deduplication_rate": _reduction(
            clusters["cluster_count"], evidence_count
        ),
        "human_queue_reduction": _reduction(
            adjudication_count, raw_count
        ),
        "incomplete_lanes": incomplete_lanes,
        "clusters": clusters["clusters"],
        "interpretation": (
            "Queue reduction is provisional. Negative values mean incomplete lanes or distinct "
            "root causes created more human work than the raw finding count alone reveals."
        ),
    }


def _read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise PilotError(f"{path} must contain one JSON object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", nargs="+", required=True)
    parser.add_argument("--reviews", nargs="+", required=True)
    parser.add_argument("--measurement-class", default="DEMO")
    parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if len(args.raw) != len(args.reviews):
            raise PilotError("--raw and --reviews must contain the same number of paths")
        report = build_pilot_report(
            [_read_json(path) for path in args.raw],
            [_read_json(path) for path in args.reviews],
            measurement_class=args.measurement_class,
        )
        Path(args.output).write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (PilotError, ContractError, OSError, json.JSONDecodeError) as exc:
        print(f"causal-review pilot error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
