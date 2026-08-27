#!/usr/bin/env python3
"""Fail-closed semantic validator for the LS Visual Benchmark Axis V0."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class ValidationError(ValueError):
    pass


def require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{label} must be an object")
    return value


def require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{label} must be an array")
    return value


def parse_time(value: Any, label: str = "date-time") -> datetime:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"invalid {label}: {value}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError(f"{label} must include a timezone offset")
    return parsed


def unique_index(items: Any, key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, raw_item in enumerate(require_list(items, f"{label}s")):
        item = require_object(raw_item, f"{label}[{index}]")
        value = item.get(key)
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{label} requires non-empty {key}")
        if value in result:
            raise ValidationError(f"duplicate {label} {key}: {value}")
        result[value] = item
    return result


def require_refs(values: Any, known: set[str], label: str) -> None:
    refs = require_list(values, label)
    if not all(isinstance(value, str) and value for value in refs):
        raise ValidationError(f"{label} must contain non-empty string ids")
    unknown = sorted(set(refs) - known)
    if unknown:
        raise ValidationError(f"{label} references unknown ids: {', '.join(unknown)}")


def validate(trail: Any, axis: Any) -> None:
    trail = require_object(trail, "trail")
    axis = require_object(axis, "visual benchmark axis")

    if axis.get("schemaVersion") != "ls.visual-benchmark-axis.v0":
        raise ValidationError("unsupported visual benchmark schemaVersion")
    if axis.get("authority") != "ADVISORY_ONLY":
        raise ValidationError("visual benchmark authority must remain ADVISORY_ONLY")
    if axis.get("trailId") != trail.get("trailId"):
        raise ValidationError("visual benchmark trailId must match the causal trail")

    subject = require_object(axis.get("subject"), "visual benchmark subject")
    trail_subject = require_object(trail.get("subject"), "causal trail subject")
    for field, trail_field in (("repository", "repository"), ("pullRequest", "pullRequest"), ("head", "currentHead")):
        if subject.get(field) != trail_subject.get(trail_field):
            raise ValidationError(f"visual benchmark subject {field} must match causal trail {trail_field}")

    surface_evidence_ids = require_list(subject.get("surfaceEvidenceIds"), "subject.surfaceEvidenceIds")
    if not surface_evidence_ids:
        raise ValidationError("visual benchmark requires interface surface evidence")
    if not all(isinstance(value, str) and value for value in surface_evidence_ids):
        raise ValidationError("subject.surfaceEvidenceIds must contain non-empty string ids")

    window = require_object(axis.get("benchmarkWindow"), "benchmarkWindow")
    observed = parse_time(window.get("observedAt"), "benchmarkWindow.observedAt")
    valid_until = parse_time(window.get("validUntil"), "benchmarkWindow.validUntil")
    if valid_until <= observed:
        raise ValidationError("benchmark validUntil must be after observedAt")
    if window.get("periodKey") != observed.strftime("%Y-%m"):
        raise ValidationError("periodKey must match observedAt year and month")

    source_by_id = unique_index(axis.get("sources"), "id", "source")
    criterion_by_id = unique_index(axis.get("criteria"), "id", "criterion")
    assessment_by_id = unique_index(axis.get("assessments"), "criterionId", "assessment")
    pattern_by_id = unique_index(axis.get("patternDecisions"), "patternId", "pattern")

    if not source_by_id:
        raise ValidationError("visual benchmark requires at least one source")
    if not criterion_by_id:
        raise ValidationError("visual benchmark requires at least one criterion")
    if set(assessment_by_id) != set(criterion_by_id):
        raise ValidationError("each criterion must have exactly one assessment")

    source_ids = set(source_by_id)
    criterion_ids = set(criterion_by_id)
    surface_ids = set(surface_evidence_ids)

    for source in source_by_id.values():
        captured = parse_time(source.get("capturedAt"), f"source {source['id']}.capturedAt")
        source_valid_until = parse_time(source.get("validUntil"), f"source {source['id']}.validUntil")
        if captured > observed:
            raise ValidationError(f"source {source['id']} was captured after benchmark observation")
        if source_valid_until < observed:
            raise ValidationError(f"source {source['id']} was already stale at observation time")
        if source.get("class") in {"TREND_FEED", "EXEMPLAR"} and source_valid_until - captured > timedelta(days=62):
            raise ValidationError(f"fast-moving source {source['id']} has an overlong validity window")
        claims = require_list(source.get("claims"), f"source {source['id']}.claims")
        if not claims:
            raise ValidationError(f"source {source['id']} requires at least one bounded claim")

    weighted_current = 0.0
    weighted_target = 0.0
    total_weight = 0
    gaps: dict[str, float] = {}

    for criterion_id, assessment in assessment_by_id.items():
        criterion = criterion_by_id[criterion_id]
        require_refs(assessment.get("sourceIds"), source_ids, f"assessment {criterion_id}.sourceIds")
        require_refs(
            assessment.get("interfaceEvidenceIds"),
            surface_ids,
            f"assessment {criterion_id}.interfaceEvidenceIds",
        )

        expected_gap = round(float(assessment["targetScore"]) - float(assessment["currentScore"]), 2)
        if round(float(assessment["gap"]), 2) != expected_gap:
            raise ValidationError(f"assessment {criterion_id} gap must equal targetScore - currentScore")

        cited_classes = {source_by_id[source_id].get("class") for source_id in assessment["sourceIds"]}
        if criterion.get("normative") and "NORMATIVE" not in cited_classes:
            raise ValidationError(f"normative criterion {criterion_id} requires a NORMATIVE source")

        weight = int(criterion["weight"])
        if weight <= 0:
            raise ValidationError(f"criterion {criterion_id} weight must be positive")
        total_weight += weight
        weighted_current += float(assessment["currentScore"]) * weight
        weighted_target += float(assessment["targetScore"]) * weight
        gaps[criterion_id] = expected_gap

    if total_weight <= 0:
        raise ValidationError("visual benchmark total criterion weight must be positive")

    expected_current = round(weighted_current / total_weight, 2)
    expected_target = round(weighted_target / total_weight, 2)
    summary = require_object(axis.get("summary"), "summary")
    if round(float(summary["weightedCurrentScore"]), 2) != expected_current:
        raise ValidationError("summary weightedCurrentScore does not match assessments")
    if round(float(summary["weightedTargetScore"]), 2) != expected_target:
        raise ValidationError("summary weightedTargetScore does not match assessments")

    largest_gap = max(gaps.values())
    expected_largest = {criterion_id for criterion_id, gap in gaps.items() if gap == largest_gap}
    largest_gap_ids = require_list(summary.get("largestGapCriterionIds"), "summary.largestGapCriterionIds")
    if set(largest_gap_ids) != expected_largest:
        raise ValidationError("summary largestGapCriterionIds does not match the maximum gap")

    adopted: set[str] = set()
    experimental: set[str] = set()
    for pattern_id, pattern in pattern_by_id.items():
        require_refs(pattern.get("sourceIds"), source_ids, f"pattern {pattern_id}.sourceIds")
        require_refs(pattern.get("criterionIds"), criterion_ids, f"pattern {pattern_id}.criterionIds")
        cited_classes = {source_by_id[source_id].get("class") for source_id in pattern["sourceIds"]}
        if pattern.get("status") == "ADOPT":
            adopted.add(pattern_id)
            if cited_classes <= {"TREND_FEED", "EXEMPLAR"}:
                raise ValidationError(f"pattern {pattern_id} cannot be adopted from trend evidence alone")
        if pattern.get("status") == "EXPERIMENT":
            experimental.add(pattern_id)
            if not pattern.get("experimentGuard"):
                raise ValidationError(f"experimental pattern {pattern_id} requires an experimentGuard")
        elif pattern.get("experimentGuard") is not None:
            raise ValidationError(f"non-experimental pattern {pattern_id} must not declare experimentGuard")

    adopted_ids = require_list(summary.get("adoptedPatternIds"), "summary.adoptedPatternIds")
    experimental_ids = require_list(summary.get("experimentalPatternIds"), "summary.experimentalPatternIds")
    if set(adopted_ids) != adopted:
        raise ValidationError("summary adoptedPatternIds does not match pattern decisions")
    if set(experimental_ids) != experimental:
        raise ValidationError("summary experimentalPatternIds does not match pattern decisions")
    if summary.get("refreshRequiredAfter") != window.get("validUntil"):
        raise ValidationError("summary refreshRequiredAfter must equal benchmarkWindow validUntil")
    if summary.get("mergeAuthority") is not False:
        raise ValidationError("visual benchmark must never grant merge authority")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: validate_visual_benchmark.py TRAIL.json AXIS.json", file=sys.stderr)
        return 2
    try:
        trail = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        axis = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        validate(trail, axis)
        axis_object = require_object(axis, "visual benchmark axis")
        window = require_object(axis_object.get("benchmarkWindow"), "benchmarkWindow")
        print(
            f"VALID: {axis_object['axisId']} "
            f"period={window['periodKey']} authority={axis_object['authority']}"
        )
        return 0
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
