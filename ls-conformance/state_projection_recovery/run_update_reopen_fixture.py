#!/usr/bin/env python3
"""Conformance oracle for update/reopen projection regressions.

This module models a startup transition between a trusted committed projection and
an update/reopen candidate. It is intentionally vendor-neutral.

Per-case reports are returned to tests in-process. The CLI intentionally emits only
an aggregate verdict summary so fixture/user-derived values can never cross the
logging/artifact boundary.

The key distinction is that some projection state is derivable from durable
thread metadata (for example project membership), while other state such as pins
is user-authored and must be preserved rather than synthesized from cwd/path data.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Set


VERDICTS = {
    "ACCEPT_CANDIDATE",
    "BLOCK_STALE_GENERATION",
    "BLOCK_REGRESSIVE_PROJECTION",
    "BLOCK_CONTENT_MUTATION",
}


def _durable_thread_ids(case: Mapping[str, Any]) -> Set[str]:
    return {str(thread["id"]) for thread in case.get("durable_threads", [])}


def _active_thread_ids(case: Mapping[str, Any]) -> Set[str]:
    return {
        str(thread["id"])
        for thread in case.get("durable_threads", [])
        if not bool(thread.get("archived", False))
    }


def _project_ids(projection: Mapping[str, Any]) -> Set[str]:
    project_ids: Set[str] = set()
    for item in projection.get("local-projects", []):
        if isinstance(item, Mapping) and item.get("id") is not None:
            project_ids.add(str(item["id"]))
        elif isinstance(item, str):
            project_ids.add(item)
    return project_ids


def _assignments(projection: Mapping[str, Any]) -> Dict[str, str]:
    raw = projection.get("thread-project-assignments", {})
    if not isinstance(raw, Mapping):
        return {}
    return {str(thread_id): str(project_id) for thread_id, project_id in raw.items()}


def _pins(projection: Mapping[str, Any]) -> Set[str]:
    raw = projection.get("pinned-thread-ids", [])
    if not isinstance(raw, list):
        return set()
    return {str(thread_id) for thread_id in raw}


def _content_mutation_count(case: Mapping[str, Any]) -> int:
    candidates = case.get("candidate_content_digests", {})
    if not isinstance(candidates, Mapping):
        return 0

    mutations = 0
    for thread in case.get("durable_threads", []):
        thread_id = str(thread["id"])
        expected = thread.get("content_digest")
        candidate = candidates.get(thread_id, expected)
        if expected is not None and candidate != expected:
            mutations += 1
    return mutations


def _regression_counts(case: Mapping[str, Any]) -> Dict[str, int]:
    trusted = case.get("trusted_projection", {})
    candidate = case.get("candidate_projection", {})
    active_ids = _active_thread_ids(case)
    durable_ids = _durable_thread_ids(case)

    trusted_assignments = _assignments(trusted)
    candidate_assignments = _assignments(candidate)

    supported_trusted_assignments = {
        thread_id: project_id
        for thread_id, project_id in trusted_assignments.items()
        if thread_id in active_ids
    }

    missing_project_memberships = sum(
        1
        for thread_id, trusted_project_id in supported_trusted_assignments.items()
        if candidate_assignments.get(thread_id) != trusted_project_id
    )

    supported_project_ids = set(supported_trusted_assignments.values())
    missing_projects = len(supported_project_ids - _project_ids(candidate))

    trusted_pins = _pins(trusted) & durable_ids
    candidate_pins = _pins(candidate)
    dropped_pins = len(trusted_pins - candidate_pins)

    return {
        "missing_projects": missing_projects,
        "missing_project_memberships": missing_project_memberships,
        "dropped_pins": dropped_pins,
    }


def _accepted_projection(case: Mapping[str, Any], status: str) -> Mapping[str, Any]:
    if status == "ACCEPT_CANDIDATE":
        return case.get("candidate_projection", {})
    return case.get("trusted_projection", {})


def evaluate(case: Mapping[str, Any]) -> Dict[str, Any]:
    trusted = case.get("trusted_projection", {})
    candidate = case.get("candidate_projection", {})
    transition = case.get("transition", {})

    trusted_generation = trusted.get("generation")
    candidate_generation = candidate.get("generation")
    explicit_user_mutation = bool(transition.get("explicit_user_mutation", False))

    content_mutations = _content_mutation_count(case)
    regressions = _regression_counts(case)

    if content_mutations:
        status = "BLOCK_CONTENT_MUTATION"
    elif (
        isinstance(trusted_generation, int)
        and isinstance(candidate_generation, int)
        and candidate_generation < trusted_generation
    ):
        status = "BLOCK_STALE_GENERATION"
    elif not explicit_user_mutation and any(regressions.values()):
        status = "BLOCK_REGRESSIVE_PROJECTION"
    else:
        status = "ACCEPT_CANDIDATE"

    accepted = _accepted_projection(case, status)
    accepted_assignments = _assignments(accepted)
    accepted_pins = _pins(accepted)

    report = {
        "schema": "ls.update-reopen-projection-report.v0.1",
        "case_id": case.get("case_id", "unknown"),
        "trigger": transition.get("trigger", "unknown"),
        "status": status,
        "explicit_user_mutation": explicit_user_mutation,
        "durable_thread_count": len(case.get("durable_threads", [])),
        "trusted_generation": trusted_generation,
        "candidate_generation": candidate_generation,
        "accepted_generation": accepted.get("generation"),
        "trusted_project_memberships": len(_assignments(trusted)),
        "candidate_project_memberships": len(_assignments(candidate)),
        "accepted_project_memberships": len(accepted_assignments),
        "trusted_pins": len(_pins(trusted)),
        "candidate_pins": len(_pins(candidate)),
        "accepted_pins": len(accepted_pins),
        "missing_projects": regressions["missing_projects"],
        "missing_project_memberships": regressions["missing_project_memberships"],
        "dropped_pins": regressions["dropped_pins"],
        "conversation_content_mutations": content_mutations,
    }
    assert status in VERDICTS
    return report


def run_cases(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases: Iterable[Mapping[str, Any]] = payload["cases"] if isinstance(payload, dict) else payload
    return [evaluate(case) for case in cases]


def summarize_reports(reports: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
    """Return an allowlisted aggregate safe for stdout and CI artifacts."""
    materialized = list(reports)
    verdict_counts = {
        verdict: sum(1 for report in materialized if report.get("status") == verdict)
        for verdict in sorted(VERDICTS)
    }
    return {
        "schema": "ls.update-reopen-projection-summary.v0.1",
        "case_count": len(materialized),
        "verdict_counts": verdict_counts,
    }


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print("usage: run_update_reopen_fixture.py <fixture-file>", file=sys.stderr)
        return 2
    reports = run_cases(Path(argv[1]))
    print(json.dumps(summarize_reports(reports), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
