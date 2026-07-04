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


def parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"invalid date-time: {value}") from exc


def unique_index(items: list[dict[str, Any]], key: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        value = item.get(key)
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{label} requires non-empty {key}")
        if value in result:
            raise ValidationError(f"duplicate {label} {key}: {value}")
        result[value] = item
    return result


def require_refs(values: list[str], known: set[str], label: str) -> None:
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValidationError(f"{label} references unknown ids: {', '.join(unknown)}")


def validate(trail: dict[str, Any], axis: dict[str, Any]) -> None:
    if axis.get("schemaVersion") != "ls.visual-benchmark-axis.v0":
        raise ValidationError("unsupported visual benchmark schemaVersion")
    if axis.get("authority") != "ADVISORY_ONLY":
        raise ValidationError("visual benchmark authority must remain ADVISORY_ONLY")
    if axis.get("trailId") != trail.get("trailId"):
        raise ValidationError("visual benchmark trailId must match the causal trail")

    subject = axis["subject"]
    trail_subject = trail["subject"]
    for field, trail_field in (("repository", "repository"), ("pullRequest", "pullRequest"), ("head", "currentHead")):
        if subject.get(field) != trail_subject.get(trail_field):
            raise ValidationError(f"visual benchmark subject {field} must match causal trail {trail_field}")
    if not subject.get("surfaceEvidenceIds"):
        raise ValidationError("visual benchmark requires interface surface evidence")

    window = axis["benchmarkWindow"]
    observed = parse_time(window["observedAt"])
    valid_until = parse_time(window["validUntil"])
    if valid_until <= observed:
        raise ValidationError("benchmark validUntil must be after observedAt")
    if window["periodKey"] != observed.strftime("%Y-%m"):
        raise ValidationError("periodKey must match observedAt year and month")

    source_by_id = unique_index(axis["sources"], "id", "source")
    criterion_by_id = unique_index(axis["criteria"], "id", "criterion")
    assessment_by_id = unique_index(axis["assessments"], "criterionId", "assessment")
    pattern_by_id = unique_index(axis["patternDecisions"], "patternId", "pattern")

    if set(assessment_by_id) != set(criterion_by_id):
        raise ValidationError("each criterion must have exactly one assessment")

    source_ids = set(source_by_id)
    criterion_ids = set(criterion_by_id)
    surface_ids = set(subject["surfaceEvidenceIds"])

    for source in source_by_id.values():
        captured = parse_time(source["capturedAt"])
        source_valid_until = parse_time(source["validUntil"])
        if captured > observed:
            raise ValidationError(f"source {source['id']} was captured after benchmark observation")
        if source_valid_until < observed:
            raise ValidationError(f"source {source['id']} was already stale at observation time")
        if source["class"] in {"TREND_FEED", "EXEMPLAR"} and source_valid_until - captured > timedelta(days=62):
            raise ValidationError(f"fast-moving source {source['id']} has an overlong validity window")
        if not source.get("claims"):
            raise ValidationError(f"source {source['id']} requires at least one bounded claim")

    weighted_current = 0.0
    weighted_target = 0.0
    total_weight = 0
    gaps: dict[str, float] = {}

    for criterion_id, assessment in assessment_by_id.items():
        criterion = criterion_by_id[criterion_id]
        require_refs(assessment["sourceIds"], source_ids, f"assessment {criterion_id}")
        require_refs(assessment["interfaceEvidenceIds"], surface_ids, f"assessment {criterion_id}")

        expected_gap = round(float(assessment["targetScore"]) - float(assessment["currentScore"]), 2)
        if round(float(assessment["gap"]), 2) != expected_gap:
            raise ValidationError(f"assessment {criterion_id} gap must equal targetScore - currentScore")

        cited_classes = {source_by_id[source_id]["class"] for source_id in assessment["sourceIds"]}
        if criterion["normative"] and "NORMATIVE" not in cited_classes:
            raise ValidationError(f"normative criterion {criterion_id} requires a NORMATIVE source")

        weight = int(criterion["weight"])
        total_weight += weight
        weighted_current += float(assessment["currentScore"]) * weight
        weighted_target += float(assessment["targetScore"]) * weight
        gaps[criterion_id] = expected_gap

    expected_current = round(weighted_current / total_weight, 2)
    expected_target = round(weighted_target / total_weight, 2)
    summary = axis["summary"]
    if round(float(summary["weightedCurrentScore"]), 2) != expected_current:
        raise ValidationError("summary weightedCurrentScore does not match assessments")
    if round(float(summary["weightedTargetScore"]), 2) != expected_target:
        raise ValidationError("summary weightedTargetScore does not match assessments")

    largest_gap = max(gaps.values())
    expected_largest = {criterion_id for criterion_id, gap in gaps.items() if gap == largest_gap}
    if set(summary["largestGapCriterionIds"]) != expected_largest:
        raise ValidationError("summary largestGapCriterionIds does not match the maximum gap")

    adopted: set[str] = set()
    experimental: set[str] = set()
    for pattern_id, pattern in pattern_by_id.items():
        require_refs(pattern["sourceIds"], source_ids, f"pattern {pattern_id}")
        require_refs(pattern["criterionIds"], criterion_ids, f"pattern {pattern_id}")
        cited_classes = {source_by_id[source_id]["class"] for source_id in pattern["sourceIds"]}
        if pattern["status"] == "ADOPT":
            adopted.add(pattern_id)
            if cited_classes <= {"TREND_FEED", "EXEMPLAR"}:
                raise ValidationError(f"pattern {pattern_id} cannot be adopted from trend evidence alone")
        if pattern["status"] == "EXPERIMENT":
            experimental.add(pattern_id)
            if not pattern.get("experimentGuard"):
                raise ValidationError(f"experimental pattern {pattern_id} requires an experimentGuard")
        elif pattern.get("experimentGuard") is not None:
            raise ValidationError(f"non-experimental pattern {pattern_id} must not declare experimentGuard")

    if set(summary["adoptedPatternIds"]) != adopted:
        raise ValidationError("summary adoptedPatternIds does not match pattern decisions")
    if set(summary["experimentalPatternIds"]) != experimental:
        raise ValidationError("summary experimentalPatternIds does not match pattern decisions")
    if summary["refreshRequiredAfter"] != window["validUntil"]:
        raise ValidationError("summary refreshRequiredAfter must equal benchmarkWindow validUntil")
    if summary.get("mergeAuthority") is not False:
        raise ValidationError("visual benchmark must never grant merge authority")


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: validate_visual_benchmark.py TRAIL.json AXIS.json", file=sys.stderr)
        return 2
    trail = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    axis = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    try:
        validate(trail, axis)
    except (KeyError, TypeError, ValidationError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: {axis['axisId']} period={axis['benchmarkWindow']['periodKey']} authority={axis['authority']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
