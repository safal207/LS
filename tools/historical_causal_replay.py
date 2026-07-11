#!/usr/bin/env python3
"""Measure historical reviewer noise from exact-head, source-linked adjudication records."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "ls.historical-causal-replay.v0.1"
REPORT_VERSION = "ls.historical-causal-replay-report.v0.1"
SUMMARY_VERSION = "ls.historical-causal-replay-summary.v0.1"
ADJUDICATIONS = {
    "TRUE_CONFIRMED",
    "TRUE_REPRODUCED",
    "FALSE_POSITIVE",
    "REQUIRES_HUMAN_DECISION",
}
TRUE_ADJUDICATIONS = {"TRUE_CONFIRMED", "TRUE_REPRODUCED"}
ROOT_CAUSE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:/-]{2,127}$")


class ReplayError(ValueError):
    """Raised when historical evidence is incomplete or cross-head."""


def _object(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReplayError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReplayError(f"{field} must be an array")
    return value


def _string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ReplayError(f"{field} must be a string")
    value = value.strip()
    if not allow_empty and not value:
        raise ReplayError(f"{field} must not be empty")
    return value


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ReplayError(f"{field} must be a positive integer")
    return value


def _sha(value: Any, field: str) -> str:
    value = _string(value, field)
    if len(value) != 40 or any(char not in "0123456789abcdef" for char in value):
        raise ReplayError(f"{field} must be a 40-character lowercase Git SHA")
    return value


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else 1.0 - numerator / denominator


def build_replay(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build one exact-head replay report from human adjudication records."""
    replay = _object(payload, "replay")
    if replay.get("schema_version") != SCHEMA_VERSION:
        raise ReplayError(f"schema_version must equal {SCHEMA_VERSION}")
    repository = _string(replay.get("repository"), "repository")
    if repository.count("/") != 1:
        raise ReplayError("repository must use owner/name form")
    pr_number = _integer(replay.get("pr_number"), "pr_number")
    head_sha = _sha(replay.get("head_sha"), "head_sha")
    records = _array(replay.get("records"), "records")
    if not records:
        raise ReplayError("historical replay requires at least one record")

    source_ids: set[str] = set()
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    reviewer_counts: dict[str, int] = {}
    source_prefix = f"https://github.com/{repository}/"

    for index, raw_record in enumerate(records):
        field = f"records[{index}]"
        record = _object(raw_record, field)
        source_id = _string(record.get("source_id"), f"{field}.source_id")
        if source_id in source_ids:
            raise ReplayError(f"duplicate source_id: {source_id}")
        source_ids.add(source_id)
        reviewer_id = _string(record.get("reviewer_id"), f"{field}.reviewer_id").lower()
        source_url = _string(record.get("source_url"), f"{field}.source_url")
        if not source_url.startswith(source_prefix):
            raise ReplayError(f"{field}.source_url must point to {repository}")
        commit_sha = _sha(record.get("commit_sha"), f"{field}.commit_sha")
        if commit_sha != head_sha:
            raise ReplayError(
                f"{field}.commit_sha does not match replay head: {commit_sha} != {head_sha}"
            )
        title = _string(record.get("title"), f"{field}.title")
        adjudication = _string(
            record.get("adjudication"), f"{field}.adjudication"
        )
        if adjudication not in ADJUDICATIONS:
            raise ReplayError(
                f"{field}.adjudication must be one of: {', '.join(sorted(ADJUDICATIONS))}"
            )
        root_cause_raw = record.get("root_cause_key")
        root_cause_key = (
            None
            if root_cause_raw is None
            else _string(root_cause_raw, f"{field}.root_cause_key")
        )
        if adjudication in TRUE_ADJUDICATIONS:
            if root_cause_key is None or not ROOT_CAUSE_PATTERN.fullmatch(root_cause_key):
                raise ReplayError(
                    f"{field}.root_cause_key is required and must be normalized for true findings"
                )
        elif root_cause_key is not None and not ROOT_CAUSE_PATTERN.fullmatch(root_cause_key):
            raise ReplayError(f"{field}.root_cause_key has invalid syntax")

        normalized = {
            "source_id": source_id,
            "reviewer_id": reviewer_id,
            "source_url": source_url,
            "commit_sha": commit_sha,
            "title": title,
            "adjudication": adjudication,
            "root_cause_key": root_cause_key,
        }
        reviewer_counts[reviewer_id] = reviewer_counts.get(reviewer_id, 0) + 1
        if adjudication in TRUE_ADJUDICATIONS:
            accepted.append(normalized)
        elif adjudication == "FALSE_POSITIVE":
            rejected.append(normalized)
        else:
            pending.append(normalized)

    clusters_by_key: dict[str, list[dict[str, Any]]] = {}
    for record in accepted:
        clusters_by_key.setdefault(record["root_cause_key"], []).append(record)
    clusters = [
        {
            "root_cause_key": key,
            "finding_count": len(items),
            "reviewer_ids": sorted({item["reviewer_id"] for item in items}),
            "source_ids": sorted(item["source_id"] for item in items),
            "corroborated": len({item["reviewer_id"] for item in items}) >= 2,
        }
        for key, items in sorted(clusters_by_key.items())
    ]

    raw_count = len(records)
    adjudication_items = len(clusters) + len(pending)
    return {
        "schema_version": REPORT_VERSION,
        "measurement_class": "HISTORICAL_REPLAY",
        "measurement_status": "MEASURED" if not pending else "PARTIAL",
        "production_claim_allowed": False,
        "human_adjudication": "COMPLETE" if not pending else "PENDING",
        "target": {
            "repository": repository,
            "pr_number": pr_number,
            "head_sha": head_sha,
        },
        "raw_finding_count": raw_count,
        "true_finding_count": len(accepted),
        "false_positive_count": len(rejected),
        "pending_decision_count": len(pending),
        "root_cause_cluster_count": len(clusters),
        "corroborated_cluster_count": sum(cluster["corroborated"] for cluster in clusters),
        "adjudication_item_count": adjudication_items,
        "causal_deduplication_rate": _rate(len(clusters), len(accepted)),
        "human_queue_reduction": _rate(adjudication_items, raw_count),
        "reviewer_counts": dict(sorted(reviewer_counts.items())),
        "clusters": clusters,
        "false_positives": rejected,
        "pending_decisions": pending,
    }


def summarize_replays(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Combine exact-head reports without merging clusters across targets."""
    if not reports:
        raise ReplayError("summary requires at least one replay report")
    normalized: list[Mapping[str, Any]] = []
    targets: set[tuple[str, int, str]] = set()
    for index, raw in enumerate(reports):
        report = _object(raw, f"reports[{index}]")
        if report.get("schema_version") != REPORT_VERSION:
            raise ReplayError(f"reports[{index}] has unsupported schema_version")
        target = _object(report.get("target"), f"reports[{index}].target")
        identity = (
            _string(target.get("repository"), f"reports[{index}].target.repository"),
            _integer(target.get("pr_number"), f"reports[{index}].target.pr_number"),
            _sha(target.get("head_sha"), f"reports[{index}].target.head_sha"),
        )
        if identity in targets:
            raise ReplayError(f"duplicate replay target: {identity}")
        targets.add(identity)
        normalized.append(report)

    raw_count = sum(int(report["raw_finding_count"]) for report in normalized)
    true_count = sum(int(report["true_finding_count"]) for report in normalized)
    false_count = sum(int(report["false_positive_count"]) for report in normalized)
    pending_count = sum(int(report["pending_decision_count"]) for report in normalized)
    cluster_count = sum(int(report["root_cause_cluster_count"]) for report in normalized)
    queue_count = sum(int(report["adjudication_item_count"]) for report in normalized)
    return {
        "schema_version": SUMMARY_VERSION,
        "measurement_class": "HISTORICAL_REPLAY",
        "measurement_status": "MEASURED" if pending_count == 0 else "PARTIAL",
        "production_claim_allowed": False,
        "target_count": len(normalized),
        "raw_finding_count": raw_count,
        "true_finding_count": true_count,
        "false_positive_count": false_count,
        "pending_decision_count": pending_count,
        "root_cause_cluster_count": cluster_count,
        "adjudication_item_count": queue_count,
        "causal_deduplication_rate": _rate(cluster_count, true_count),
        "human_queue_reduction": _rate(queue_count, raw_count),
        "targets": [report["target"] for report in normalized],
    }


def _read_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ReplayError(f"{path} must contain one JSON object")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    replay = commands.add_parser("replay")
    replay.add_argument("input")
    replay.add_argument("--output", required=True)
    summary = commands.add_parser("summary")
    summary.add_argument("inputs", nargs="+")
    summary.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "replay":
            output = build_replay(_read_json(args.input))
        else:
            output = summarize_replays([_read_json(path) for path in args.inputs])
        Path(args.output).write_text(
            json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except (ReplayError, OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"historical causal replay error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
