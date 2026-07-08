#!/usr/bin/env python3
"""Build an event-sourced CI memory report.

The CI memory layer is intentionally small and local-first. It stores known
failure classes as append-only JSON events, replays them into a deterministic
report, and emits machine-readable artifacts for GitHub Actions.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
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
    "harmony_axis",
    "trajectory_axis",
}
REQUIRED_HARMONY_AXIS_FIELDS = {
    "balance",
    "project",
    "intermediate",
    "realization",
    "chaos_sources",
    "harmony_mechanisms",
    "transition",
}
REQUIRED_TRAJECTORY_AXIS_FIELDS = {
    "from_state",
    "to_state",
    "direction",
    "phase",
    "phase_order",
    "transition_path",
    "trajectory_summary",
}

BLOCKING_EVENT_TYPES = {
    "PROVENANCE_MISMATCH",
    "KNOWN_FAILURE_REPLAYED",
}
VALID_DECISIONS = {
    "BLOCK_MERGE",
    "DOCUMENT_ONLY",
    "ALLOW_WITH_GUARDRAIL",
}
VALID_HARMONY_BALANCES = {
    "CHAOS",
    "MIXED",
    "HARMONY",
    "STRONG_HARMONY",
}
VALID_TRAJECTORY_DIRECTIONS = {
    "CHAOS_TO_HARMONY",
    "HARMONY_TO_CHAOS",
    "STABLE_HARMONY",
    "STABLE_CHAOS",
    "MIXED_TRANSITION",
}
TRAJECTORY_PHASES = [
    "DRIFT",
    "COLLISION",
    "CAPTURE",
    "TRANSLATION",
    "REPLAY",
    "STABILIZATION",
    "INSTITUTIONALIZATION",
]
TRAJECTORY_PHASE_ORDER = {
    phase: index for index, phase in enumerate(TRAJECTORY_PHASES, start=1)
}
VALID_TRAJECTORY_PHASES = set(TRAJECTORY_PHASES)
TIME_SLICES = ("t_past", "t_more", "t_present")
SPACE_LAYERS = ("project", "intermediate", "realization")


def invalid_event(path: Path, error: str) -> dict[str, Any]:
    """Return a synthetic event so replay can continue after a bad file."""
    return {
        "event_id": f"invalid:{path.name}",
        "event_type": "INVALID_EVENT_FILE",
        "source_file": str(path),
        "_load_errors": [error],
    }


def parse_observed_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def event_sort_key(event: dict[str, Any]) -> tuple[str, str]:
    parsed = parse_observed_at(event.get("observed_at"))
    observed_key = parsed.isoformat() if parsed else "9999-12-31T23:59:59+00:00"
    event_id = event.get("event_id")
    return observed_key, event_id if isinstance(event_id, str) else ""


def load_event(path: Path) -> dict[str, Any]:
    try:
        event = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return invalid_event(path, "file not found")
    except OSError as exc:
        return invalid_event(path, f"failed to read event file: {exc}")
    except json.JSONDecodeError as exc:
        return invalid_event(
            path,
            f"invalid JSON at line {exc.lineno} column {exc.colno}: {exc.msg}",
        )

    if not isinstance(event, dict):
        return invalid_event(path, "event must be an object")
    event.setdefault("source_file", str(path))
    return event


def load_events(events_dir: Path) -> list[dict[str, Any]]:
    if not events_dir.exists():
        return []
    events = []
    for path in sorted(events_dir.glob("*.json")):
        events.append(load_event(path))
    return sorted(events, key=event_sort_key)


def validate_string_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field_name} must be a list"]
    if not all(isinstance(item, str) and item for item in value):
        return [f"{field_name} must contain only non-empty strings"]
    return []


def validate_harmony_axis(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    axis = event.get("harmony_axis")
    if not isinstance(axis, dict):
        return ["harmony_axis must be an object"]

    missing = REQUIRED_HARMONY_AXIS_FIELDS - axis.keys()
    if missing:
        errors.append(f"harmony_axis missing fields: {sorted(missing)}")

    for field in ("balance", "project", "intermediate", "realization"):
        if axis.get(field) not in VALID_HARMONY_BALANCES:
            errors.append(f"harmony_axis.{field} must be one of {sorted(VALID_HARMONY_BALANCES)}")

    errors.extend(validate_string_list(axis.get("chaos_sources"), "harmony_axis.chaos_sources"))
    errors.extend(
        validate_string_list(axis.get("harmony_mechanisms"), "harmony_axis.harmony_mechanisms")
    )
    if not isinstance(axis.get("transition"), str) or not axis.get("transition"):
        errors.append("harmony_axis.transition must be a non-empty string")

    return errors


def validate_transition_path(value: Any, phase: Any) -> list[str]:
    errors = validate_string_list(value, "trajectory_axis.transition_path")
    if errors:
        return errors
    assert isinstance(value, list)

    invalid_phases = [item for item in value if item not in VALID_TRAJECTORY_PHASES]
    if invalid_phases:
        errors.append(f"trajectory_axis.transition_path contains invalid phases: {invalid_phases}")
        return errors

    phase_orders = [TRAJECTORY_PHASE_ORDER[item] for item in value]
    if phase_orders != sorted(phase_orders) or len(phase_orders) != len(set(phase_orders)):
        errors.append("trajectory_axis.transition_path must be strictly ordered by phase")

    if isinstance(phase, str) and value and value[-1] != phase:
        errors.append("trajectory_axis.transition_path must end with trajectory_axis.phase")

    return errors


def validate_trajectory_axis(event: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    axis = event.get("trajectory_axis")
    if not isinstance(axis, dict):
        return ["trajectory_axis must be an object"]

    missing = REQUIRED_TRAJECTORY_AXIS_FIELDS - axis.keys()
    if missing:
        errors.append(f"trajectory_axis missing fields: {sorted(missing)}")

    for field in ("from_state", "to_state", "trajectory_summary"):
        if not isinstance(axis.get(field), str) or not axis.get(field):
            errors.append(f"trajectory_axis.{field} must be a non-empty string")

    direction = axis.get("direction")
    if direction not in VALID_TRAJECTORY_DIRECTIONS:
        errors.append(
            f"trajectory_axis.direction must be one of {sorted(VALID_TRAJECTORY_DIRECTIONS)}"
        )

    phase = axis.get("phase")
    if phase not in VALID_TRAJECTORY_PHASES:
        errors.append(f"trajectory_axis.phase must be one of {sorted(VALID_TRAJECTORY_PHASES)}")

    phase_order = axis.get("phase_order")
    if not isinstance(phase_order, int) or phase_order <= 0:
        errors.append("trajectory_axis.phase_order must be a positive integer")
    elif isinstance(phase, str) and phase in TRAJECTORY_PHASE_ORDER:
        expected_order = TRAJECTORY_PHASE_ORDER[phase]
        if phase_order != expected_order:
            errors.append(
                f"trajectory_axis.phase_order must be {expected_order} for phase {phase}"
            )

    errors.extend(validate_transition_path(axis.get("transition_path"), phase))
    return errors


def harmony_axis_summary(event: dict[str, Any]) -> dict[str, Any]:
    axis = event.get("harmony_axis")
    if not isinstance(axis, dict):
        return {}
    return {
        "event_id": event.get("event_id"),
        "balance": axis.get("balance"),
        "project": axis.get("project"),
        "intermediate": axis.get("intermediate"),
        "realization": axis.get("realization"),
        "chaos_sources": axis.get("chaos_sources", []),
        "harmony_mechanisms": axis.get("harmony_mechanisms", []),
        "transition": axis.get("transition"),
    }


def trajectory_axis_summary(event: dict[str, Any]) -> dict[str, Any]:
    axis = event.get("trajectory_axis")
    if not isinstance(axis, dict):
        return {}
    return {
        "event_id": event.get("event_id"),
        "from_state": axis.get("from_state"),
        "to_state": axis.get("to_state"),
        "direction": axis.get("direction"),
        "phase": axis.get("phase"),
        "phase_order": axis.get("phase_order"),
        "transition_path": axis.get("transition_path", []),
        "trajectory_summary": axis.get("trajectory_summary"),
    }


def first_item(value: Any, default: str) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, str) and first:
            return first
    return default


def temporal_cell(
    event: dict[str, Any],
    time_slice: str,
    space_layer: str,
    state: str,
    summary: str,
) -> dict[str, Any]:
    harmony_axis = event.get("harmony_axis", {})
    trajectory_axis = event.get("trajectory_axis", {})
    transition_path = trajectory_axis.get("transition_path", [])
    return {
        "event_id": event.get("event_id"),
        "time_slice": time_slice,
        "space_layer": space_layer,
        "state": state,
        "summary": summary,
        "balance": harmony_axis.get(space_layer) if isinstance(harmony_axis, dict) else None,
        "trajectory_direction": (
            trajectory_axis.get("direction") if isinstance(trajectory_axis, dict) else None
        ),
        "trajectory_phase": (
            trajectory_axis.get("phase") if isinstance(trajectory_axis, dict) else None
        ),
        "transition_path": transition_path if isinstance(transition_path, list) else [],
    }


def temporal_layered_matrix_summary(event: dict[str, Any]) -> dict[str, Any]:
    harmony_axis = event.get("harmony_axis", {})
    trajectory_axis = event.get("trajectory_axis", {})
    subject = event.get("subject", {})
    source = event.get("source", {})

    from_state = (
        trajectory_axis.get("from_state", "UNTRACKED_STATE")
        if isinstance(trajectory_axis, dict)
        else "UNTRACKED_STATE"
    )
    to_state = (
        trajectory_axis.get("to_state", "TRACKED_STATE")
        if isinstance(trajectory_axis, dict)
        else "TRACKED_STATE"
    )
    phase = (
        trajectory_axis.get("phase", "UNKNOWN_PHASE")
        if isinstance(trajectory_axis, dict)
        else "UNKNOWN_PHASE"
    )
    direction = (
        trajectory_axis.get("direction", "UNKNOWN_DIRECTION")
        if isinstance(trajectory_axis, dict)
        else "UNKNOWN_DIRECTION"
    )
    transition_path = (
        trajectory_axis.get("transition_path", [])
        if isinstance(trajectory_axis, dict)
        else []
    )
    chaos_source = (
        first_item(harmony_axis.get("chaos_sources"), "unknown chaos source")
        if isinstance(harmony_axis, dict)
        else "unknown chaos source"
    )
    harmony_mechanism = (
        first_item(harmony_axis.get("harmony_mechanisms"), "unknown harmony mechanism")
        if isinstance(harmony_axis, dict)
        else "unknown harmony mechanism"
    )

    cells = [
        temporal_cell(
            event,
            "t_past",
            "project",
            str(from_state),
            "The risk existed before it was represented as CI memory.",
        ),
        temporal_cell(
            event,
            "t_past",
            "intermediate",
            first_item(transition_path, "DRIFT"),
            "The failure class was still moving through an implicit design gap.",
        ),
        temporal_cell(
            event,
            "t_past",
            "realization",
            chaos_source,
            "The concrete implementation risk was present but not yet guarded.",
        ),
        temporal_cell(
            event,
            "t_more",
            "project",
            str(event.get("event_type")),
            "The failure class was named as an event.",
        ),
        temporal_cell(
            event,
            "t_more",
            "intermediate",
            str(phase),
            "The transition phase became explicit and validated.",
        ),
        temporal_cell(
            event,
            "t_more",
            "realization",
            str(event.get("event_id")),
            "The event was replayed into deterministic artifacts.",
        ),
        temporal_cell(
            event,
            "t_present",
            "project",
            str(to_state),
            "The desired target state is now represented in CI memory.",
        ),
        temporal_cell(
            event,
            "t_present",
            "intermediate",
            str(direction),
            "The system movement is explicit and reviewable.",
        ),
        temporal_cell(
            event,
            "t_present",
            "realization",
            harmony_mechanism,
            "The guardrail mechanism is visible in the report.",
        ),
    ]

    return {
        "event_id": event.get("event_id"),
        "subject_pr": subject.get("pr_number") if isinstance(subject, dict) else None,
        "source_pr": source.get("pr_number") if isinstance(source, dict) else None,
        "time_slices": list(TIME_SLICES),
        "space_layers": list(SPACE_LAYERS),
        "cells": cells,
    }


def matrix_rows(matrix: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    cells = matrix.get("cells", [])
    for time_slice in TIME_SLICES:
        row: dict[str, str] = {"time_slice": time_slice}
        for space_layer in SPACE_LAYERS:
            matching = [
                cell for cell in cells
                if cell.get("time_slice") == time_slice
                and cell.get("space_layer") == space_layer
            ]
            row[space_layer] = str(matching[0].get("state")) if matching else ""
        rows.append(row)
    return rows


def validate_event(event: dict[str, Any]) -> list[str]:
    errors: list[str] = list(event.get("_load_errors", []))
    missing = REQUIRED_EVENT_FIELDS - event.keys()
    if missing:
        errors.append(f"missing fields: {sorted(missing)}")

    if event.get("schema_version") != EVENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EVENT_SCHEMA_VERSION}")

    if not isinstance(event.get("event_id"), str) or not event.get("event_id"):
        errors.append("event_id must be a non-empty string")

    if not isinstance(event.get("event_type"), str) or not event.get("event_type"):
        errors.append("event_type must be a non-empty string")

    if not isinstance(event.get("observed_at"), str) or not event.get("observed_at"):
        errors.append("observed_at must be a non-empty string")
    elif parse_observed_at(event.get("observed_at")) is None:
        errors.append("observed_at must be an ISO-8601 datetime")

    if not isinstance(event.get("observed_in_pr"), int) or event.get("observed_in_pr", 0) <= 0:
        errors.append("observed_in_pr must be a positive integer")

    decision = event.get("decision")
    if decision not in VALID_DECISIONS:
        errors.append(f"decision must be one of {sorted(VALID_DECISIONS)}")

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

    evidence = event.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence must be a list")
    elif not all(isinstance(item, str) and item for item in evidence):
        errors.append("evidence must contain only non-empty strings")

    errors.extend(validate_harmony_axis(event))
    errors.extend(validate_trajectory_axis(event))
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
    ordered_events = sorted(events, key=event_sort_key)
    validation: list[dict[str, Any]] = []
    known_failures: list[dict[str, Any]] = []
    harmony_axis: list[dict[str, Any]] = []
    trajectory_axis: list[dict[str, Any]] = []
    temporal_layered_matrix: list[dict[str, Any]] = []
    event_ids: set[str] = set()

    for index, event in enumerate(ordered_events, start=1):
        errors = validate_event(event)
        event_id = event.get("event_id")
        if isinstance(event_id, str) and event_id in event_ids:
            errors.append(f"duplicate event_id: {event_id}")
        if isinstance(event_id, str):
            event_ids.add(event_id)

        validation.append(
            {
                "event_id": event.get("event_id"),
                "observed_at": event.get("observed_at"),
                "replay_index": index,
                "valid": not errors,
                "errors": errors,
            }
        )
        if not errors:
            harmony_axis.append(harmony_axis_summary(event))
            trajectory_axis.append(trajectory_axis_summary(event))
            temporal_layered_matrix.append(temporal_layered_matrix_summary(event))
        if not errors and is_known_failure(event):
            known_failures.append(event)

    invalid_events_count = sum(1 for item in validation if not item["valid"])
    if invalid_events_count:
        status = "INVALID_EVENTS"
    elif known_failures:
        status = "KNOWN_FAILURE_REPLAYED"
    else:
        status = "CLEAR"

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "events_count": len(ordered_events),
        "valid_events_count": sum(1 for item in validation if item["valid"]),
        "invalid_events_count": invalid_events_count,
        "known_failures_count": len(known_failures),
        "known_failure_ids": [event["event_id"] for event in known_failures],
        "status": status,
        "timeline": [
            {
                "replay_index": index,
                "event_id": event.get("event_id"),
                "event_type": event.get("event_type"),
                "observed_at": event.get("observed_at"),
                "observed_in_pr": event.get("observed_in_pr"),
                "decision": event.get("decision"),
                "harmony_balance": (
                    event.get("harmony_axis", {}).get("balance")
                    if isinstance(event.get("harmony_axis"), dict)
                    else None
                ),
                "trajectory_direction": (
                    event.get("trajectory_axis", {}).get("direction")
                    if isinstance(event.get("trajectory_axis"), dict)
                    else None
                ),
                "trajectory_phase": (
                    event.get("trajectory_axis", {}).get("phase")
                    if isinstance(event.get("trajectory_axis"), dict)
                    else None
                ),
            }
            for index, event in enumerate(ordered_events, start=1)
        ],
        "harmony_axis": harmony_axis,
        "trajectory_axis": trajectory_axis,
        "temporal_layered_matrix": temporal_layered_matrix,
        "validation": validation,
        "known_failures": known_failures,
    }


def write_ndjson(path: Path, events: list[dict[str, Any]]) -> None:
    ordered_events = sorted(events, key=event_sort_key)
    path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in ordered_events),
        encoding="utf-8",
    )


def write_temporal_matrix_markdown(path: Path, matrices: list[dict[str, Any]]) -> None:
    lines = ["# LS CI Memory Temporal Layered Matrix", ""]
    if not matrices:
        lines.append("No valid CI memory events found.")
    for matrix in matrices:
        lines.append(f"## `{matrix['event_id']}`")
        lines.append("")
        lines.append("| Time slice | Project | Intermediate | Realization |")
        lines.append("|---|---|---|---|")
        for row in matrix_rows(matrix):
            lines.append(
                f"| `{row['time_slice']}` | `{row['project']}` | "
                f"`{row['intermediate']}` | `{row['realization']}` |"
            )
        lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# LS CI Memory Report",
        "",
        f"Status: `{report['status']}`",
        "",
        f"Events replayed: `{report['events_count']}`",
        f"Valid events: `{report['valid_events_count']}`",
        f"Invalid events: `{report['invalid_events_count']}`",
        f"Known failures replayed: `{report['known_failures_count']}`",
        "",
        "## Timeline",
        "",
    ]
    if not report["timeline"]:
        lines.append("No CI memory events found.")
    else:
        lines.append("| # | Event | Type | Observed at | PR | Decision | Balance | Direction | Phase |")
        lines.append("|---:|---|---|---|---:|---|---|---|---|")
        for item in report["timeline"]:
            lines.append(
                f"| {item['replay_index']} | `{item['event_id']}` | "
                f"`{item['event_type']}` | `{item['observed_at']}` | "
                f"#{item['observed_in_pr']} | `{item['decision']}` | "
                f"`{item['harmony_balance']}` | `{item['trajectory_direction']}` | "
                f"`{item['trajectory_phase']}` |"
            )
    lines.append("")

    if report["harmony_axis"]:
        lines.extend(["## Harmony / Chaos Axis", ""])
        lines.append("| Event | Balance | Project | Intermediate | Realization | Transition |")
        lines.append("|---|---|---|---|---|---|")
        for item in report["harmony_axis"]:
            lines.append(
                f"| `{item['event_id']}` | `{item['balance']}` | `{item['project']}` | "
                f"`{item['intermediate']}` | `{item['realization']}` | {item['transition']} |"
            )
        lines.append("")
        lines.append("### Chaos sources and harmony mechanisms")
        lines.append("")
        for item in report["harmony_axis"]:
            lines.append(f"#### `{item['event_id']}`")
            lines.append("")
            lines.append("Chaos sources:")
            for source in item["chaos_sources"]:
                lines.append(f"- {source}")
            lines.append("")
            lines.append("Harmony mechanisms:")
            for mechanism in item["harmony_mechanisms"]:
                lines.append(f"- {mechanism}")
            lines.append("")

    if report["trajectory_axis"]:
        lines.extend(["## Trajectory Axis", ""])
        lines.append("| Event | From | To | Direction | Phase | Order |")
        lines.append("|---|---|---|---|---|---:|")
        for item in report["trajectory_axis"]:
            lines.append(
                f"| `{item['event_id']}` | `{item['from_state']}` | `{item['to_state']}` | "
                f"`{item['direction']}` | `{item['phase']}` | `{item['phase_order']}` |"
            )
        lines.append("")
        lines.append("### Transition paths")
        lines.append("")
        for item in report["trajectory_axis"]:
            lines.append(f"#### `{item['event_id']}`")
            lines.append("")
            transition_path = " → ".join(item["transition_path"])
            lines.append(f"Path: `{transition_path}`")
            lines.append("")
            lines.append(item["trajectory_summary"])
            lines.append("")

    if report["temporal_layered_matrix"]:
        lines.extend(["## Temporal Layered Matrix", ""])
        for matrix in report["temporal_layered_matrix"]:
            lines.append(f"### `{matrix['event_id']}`")
            lines.append("")
            lines.append("| Time slice | Project | Intermediate | Realization |")
            lines.append("|---|---|---|---|")
            for row in matrix_rows(matrix):
                lines.append(
                    f"| `{row['time_slice']}` | `{row['project']}` | "
                    f"`{row['intermediate']}` | `{row['realization']}` |"
                )
            lines.append("")

    if report["invalid_events_count"]:
        lines.extend(["## Invalid events", ""])
        lines.append("| Event | Errors |")
        lines.append("|---|---|")
        for item in report["validation"]:
            if not item["valid"]:
                errors = "<br>".join(item["errors"])
                lines.append(f"| `{item['event_id']}` | {errors} |")
        lines.append("")

    lines.extend(["## Known failures", ""])
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
    (out_dir / "ci_memory_temporal_matrix.json").write_text(
        json.dumps(report["temporal_layered_matrix"], indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_markdown(out_dir / "ci_memory_report.md", report)
    write_temporal_matrix_markdown(
        out_dir / "ci_memory_temporal_matrix.md",
        report["temporal_layered_matrix"],
    )
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
    parser.add_argument(
        "--fail-on-invalid-event",
        action="store_true",
        help="Exit non-zero when malformed CI memory events are found.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_ci_memory(Path(args.events_dir), Path(args.out_dir))
    print(
        "CI memory replayed "
        f"{report['events_count']} events; status={report['status']}"
    )
    if args.fail_on_invalid_event and report["status"] == "INVALID_EVENTS":
        return 1
    if args.fail_on_known_failure and report["status"] == "KNOWN_FAILURE_REPLAYED":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
