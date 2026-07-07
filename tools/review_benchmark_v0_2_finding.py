from __future__ import annotations

from typing import Any

from review_benchmark_v0_2_common import (
    CLASSIFICATIONS,
    IDENT,
    REPRODUCTION_STATUSES,
    SEVERITIES,
    BenchmarkV02Error,
    confidence,
    exact,
    repo_path,
    strings,
    text,
)


def validate_finding(item: Any, index: int, ids: set[str], lane: str) -> None:
    field = f"findings[{index}]"
    exact(
        item,
        {
            "finding_id", "title", "severity", "classification", "confidence",
            "claim", "evidence", "failure_scenario", "reproduction",
            "recommendation", "uncertainties",
        },
        field,
    )
    finding_id = item["finding_id"]
    if not isinstance(finding_id, str) or not IDENT.fullmatch(finding_id):
        raise BenchmarkV02Error(f"{field}.finding_id is invalid")
    prefix = "FM-" if lane == "FRONTIER_MODEL" else "LS-"
    if not finding_id.startswith(prefix):
        raise BenchmarkV02Error(f"{field}.finding_id must start with {prefix}")
    if finding_id in ids:
        raise BenchmarkV02Error(f"duplicate finding_id: {finding_id}")
    ids.add(finding_id)
    text(item["title"], f"{field}.title")
    if item["severity"] not in SEVERITIES:
        raise BenchmarkV02Error(f"{field}.severity is invalid")
    if item["classification"] not in CLASSIFICATIONS:
        raise BenchmarkV02Error(f"{field}.classification is invalid")
    confidence(item["confidence"], f"{field}.confidence")
    for name in ("claim", "failure_scenario", "recommendation"):
        text(item[name], f"{field}.{name}")
    strings(item["uncertainties"], f"{field}.uncertainties")

    evidence = item["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise BenchmarkV02Error(f"{field}.evidence must not be empty")
    for offset, source in enumerate(evidence):
        exact(
            source,
            {"path", "line_start", "line_end", "observation"},
            f"{field}.evidence[{offset}]",
        )
        repo_path(source["path"], "evidence.path")
        start, end = source["line_start"], source["line_end"]
        if (start is None) != (end is None):
            raise BenchmarkV02Error("evidence line range must be both null or integers")
        if start is not None and (
            not isinstance(start, int) or isinstance(start, bool)
            or not isinstance(end, int) or isinstance(end, bool)
            or start < 1 or end < start
        ):
            raise BenchmarkV02Error("evidence line range is invalid")
        text(source["observation"], "evidence.observation")
    reproduction = exact(item["reproduction"], {"status", "steps"}, "reproduction")
    status = reproduction["status"]
    if status not in REPRODUCTION_STATUSES:
        raise BenchmarkV02Error("reproduction.status is invalid")
    strings(
        reproduction["steps"],
        "reproduction.steps",
        nonempty=status in {"REPRODUCED", "STATICALLY_PROVEN"},
    )
