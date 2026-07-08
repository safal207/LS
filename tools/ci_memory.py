#!/usr/bin/env python3
"""Build an event-sourced CI memory report.

The CI memory layer is intentionally small and local-first. It stores known
failure classes as append-only JSON events, replays them into a deterministic
report, and emits machine-readable artifacts for GitHub Actions.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EVENT_SCHEMA_VERSION = "ls.ci_memory_event.v0.1"
REPORT_SCHEMA_VERSION = "ls.ci_memory_report.v0.1"
DEFAULT_EVENTS_DIR = ROOT / "audits" / "ci-memory" / "events"
DEFAULT_OUT_DIR = ROOT / "artifacts" / "ci-memory"

REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "event_type",
    "observed_at",
    "observed_in_pr",
    "subject",
    "source",
    "decision",
    "evidence",
}

BLOCKING_EVENT_TYPES = {
    "PROVENANCE_MISMATCH",
    "KNOWN_FAILURE_REPLAYED",
}


def load_event(path: Path) -> dict[str, Any]:
    event = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise ValueError(f"{path}: event must be an object")
    return event


def load_events(events_dir: Path) -> list[dict[str, Any]]:
    if not events_dir.exists():
        return []
    events = []
    for path in sorted(events_dir.glob("*.json")):
        events.append(load_event(path))
    return events


def validate_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_EVENT_FIELDS - event.keys()
    if missing:
        errors.append(f"missing fields: {sorted(missing)}")

    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EVENT_SCHEMA_VERSION}")

    if not isinstance(event.get("event_id"), str) or not event.get("event_id"):
        errors.append("event_id must be a non-empty string")

    if not isinstance(event.get("event_type"), str) or not event.get("event_type"):
        errors.append("event_type must be a non-empty string")

    if not isinstance(event.get("observed_in_pr"), int) or event.get("observed_in_pr", 0) <= 0:
        errors.append("observed_in_pr must be a positive integer")

    subject = event.get("subject")
    if not isinstance(subject, dict):
        errors.append("subject must be an object")
    else:
        if not isinstance(subject.get("pr_number"), int) or subject.get("pr_number", 0) <= 0:
            errors.append("subject.pr_number must be a positive integer")
        if not isinstance(subject.get("commit_sha"), str) or not subject.get("commit_sha"):
            errors.append("subject.commit_sha must be a non-empty string")

    source = event.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        if not isinstance(source.get("pr_number"), int) or source.get("pr_number", 0) <= 0:
            errors.append("source.pr_number must be a positive integer")
        if not isinstance(source.get("head_sha"), str) or not source.get("head_sha"):
            errors.append("source.head_sha must be a non-empty string")

    if not isinstance(event.get("evidence"), list):
        errors.append("evidence must be a list")

    return errors


def is_known_failure(event: dict[str, Any]) -> bool:
    if event.get("event_type") not in BLOCKING_EVENT_TYPES:
        return False
    if event.get("decision") != "BLOCK_MERGE":
        return False
    subject = event.get("subject", {})
    source = event.get("source", {})
    return isinstance(subject, dict) and isinstance(source, dict) and (
        subject.get("pr_number") != source.get("pr_number")
        or subject.get("commit_sha") != source.get("head_sha")
    )


def replay_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    validation: list[dict[str, Any]] = []
    known_failures: list[dict[str, Any]] = []
    event_ids: set[str] = set()

    for event in events:
        errors = validate_event(event)
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id in event_ids:
            errors.append(f"duplicate event_id: {event_id}")
        if isinstance(event_id, str):
            event_ids.add(event_id)

        validation.append(
            {
                "event_id": event.get("event_id"),
                "valid": not errors,
                "errors": errors,
            }
        )
        if not errors and is_known_failure(event):
            known_failures.append(event)

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "events_count": len(events),
        "valid_events_count": sum(1 for item in validation if item["valid"]),
        "known_failures_count": len(known_failures),
        "known_failure_ids": [event["event_id"] for event in known_failures],
        "status": "KNOWN_FAILURE_REPLAYED" if known_failures else "CLEAR",
        "validation": validation,
        "known_failures": known_failures,
    }


def write_ndjson(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
        encoding="utf-8",
    )


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# LS CI Memory Report",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Events replayed: `{report['events_count']}`",
        f"Known failures replayed: `{report['known_failures_count']}`",
        "",
        "## Known failures",
        "",
    ]
    if not report["known_failures"]:
        lines.append("No known blocking failure patterns replayed.")
    else:
        lines.append("| Event | Type | Observed in PR | Decision |")
        lines.append("|---|---|---:|---|")
        for event in report["known_failures"]:
            lines.append(
                f"| `{event['event_id']}` | `{event['event_type']}` | "
                f"#{event['observed_in_pr']} | `{event['decision']}` |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_ci_memory(events_dir: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    events = load_events(events_dir)
    report = replay_events(events)

    write_ndjson(out_dir / "ci_memory_events.ndjson", events)
    (out_dir / "ci_memory_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_markdown(out_dir / "ci_memory_report.md", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-dir", default=str(DEFAULT_EVENTS_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument(
        "--fail-on-known-failure",
        action="store_true",
        help="Exit non-zero when known blocking failure patterns are replayed.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_ci_memory(Path(args.events_dir), Path(args.out_dir))
    print(
        "CI memory replayed "
        f"{report['events_count']} events; status={report['status']}"
    )
    if args.fail_on_known_failure and report["status"] == "KNOWN_FAILURE_REPLAYED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
