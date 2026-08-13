#!/usr/bin/env python3
"""Vendor-neutral state projection recovery conformance runner.

The runner operates on synthetic fixture data. It reconstructs derived project/index
state from durable thread + cwd evidence and emits a redaction-safe report.
"""

from __future__ import annotations

import copy
import json
import ntpath
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple


VERDICTS = {
    "RECOVERED_PROJECTION",
    "NO_CHANGES_REQUIRED",
    "BLOCK_STALE_GENERATION",
    "BLOCK_CONTENT_MUTATION",
    "UNRESOLVED_AMBIGUOUS_PROJECT",
    "INCONCLUSIVE_MISSING_DURABLE_EVIDENCE",
}

PROJECTION_KEYS = (
    "local-projects",
    "project-order",
    "thread-project-assignments",
    "thread-writable-roots",
    "projectless-thread-ids",
    "thread-workspace-root-hints",
)


def normalize_windows_path(value: str) -> str:
    """Normalize normal/verbatim Windows paths deterministically."""
    path = value.replace("/", "\\")
    if path.startswith("\\\\?\\"):
        path = path[4:]
    return ntpath.normcase(ntpath.normpath(path)).rstrip("\\")


def discover_capabilities(projection: Mapping[str, Any], live_rows: Iterable[Mapping[str, Any]]) -> Dict[str, bool]:
    capabilities = {
        key.replace("-", "_"): key in projection
        for key in PROJECTION_KEYS
    }
    capabilities["generation_guard"] = isinstance(projection.get("generation"), int)
    capabilities["live_project_id"] = any("project_id" in row for row in live_rows)
    return capabilities


def _normalize_aliases(aliases: Mapping[str, str]) -> Dict[str, str]:
    return {
        normalize_windows_path(source): normalize_windows_path(target)
        for source, target in aliases.items()
    }


def _apply_alias(path: str, aliases: Mapping[str, str]) -> str:
    normalized = normalize_windows_path(path)
    if normalized in aliases:
        return aliases[normalized]
    return normalized


def _project_matches(cwd: str, projects: Iterable[Mapping[str, str]], aliases: Mapping[str, str]) -> List[Tuple[str, str]]:
    normalized_cwd = _apply_alias(cwd, aliases)
    matches: List[Tuple[str, str]] = []
    for project in projects:
        root = _apply_alias(project["root"], aliases)
        if normalized_cwd == root or normalized_cwd.startswith(root + "\\"):
            matches.append((project["id"], root))

    if not matches:
        return []

    # Prefer the deepest matching root, but fail closed if that normalized root
    # corresponds to multiple project identities.
    max_len = max(len(root) for _, root in matches)
    return [(project_id, root) for project_id, root in matches if len(root) == max_len]


def _derive_state(case: Mapping[str, Any]) -> Dict[str, Any]:
    durable_threads = list(case.get("durable_threads", []))
    projects = list(case.get("projects", []))
    aliases = _normalize_aliases(case.get("aliases", {}))

    assignments: Dict[str, str] = {}
    writable_roots: Dict[str, List[str]] = {}
    workspace_hints: Dict[str, str] = {}
    projectless_active: List[str] = []
    archived_unassigned: List[str] = []
    ambiguous = 0

    for thread in durable_threads:
        matches = _project_matches(thread["cwd"], projects, aliases)
        if len(matches) > 1:
            ambiguous += 1
            if thread.get("archived", False):
                archived_unassigned.append(thread["id"])
            else:
                projectless_active.append(thread["id"])
            continue
        if len(matches) == 1:
            project_id, normalized_root = matches[0]
            assignments[thread["id"]] = project_id
            writable_roots[thread["id"]] = [normalized_root]
            workspace_hints[thread["id"]] = normalized_root
        elif thread.get("archived", False):
            archived_unassigned.append(thread["id"])
        else:
            projectless_active.append(thread["id"])

    return {
        "assignments": assignments,
        "writable_roots": writable_roots,
        "workspace_hints": workspace_hints,
        "projectless_active": sorted(projectless_active),
        "archived_unassigned": sorted(archived_unassigned),
        "ambiguous_matches": ambiguous,
    }


def _content_mutation_count(case: Mapping[str, Any]) -> int:
    candidates = case.get("candidate_content_digests", {})
    mutations = 0
    for thread in case.get("durable_threads", []):
        expected = thread.get("content_digest")
        candidate = candidates.get(thread["id"], expected)
        if expected is not None and candidate != expected:
            mutations += 1
    return mutations


def _build_projection_after(case: Mapping[str, Any], derived: Mapping[str, Any], capabilities: Mapping[str, bool]) -> Dict[str, Any]:
    before = copy.deepcopy(case.get("persisted_projection", {}))
    after = copy.deepcopy(before)

    if capabilities.get("local_projects"):
        after["local-projects"] = [
            {"id": project["id"], "root": normalize_windows_path(project["root"])}
            for project in case.get("projects", [])
        ]
    if capabilities.get("project_order"):
        after["project-order"] = [project["id"] for project in case.get("projects", [])]
    if capabilities.get("thread_project_assignments"):
        after["thread-project-assignments"] = dict(sorted(derived["assignments"].items()))
    if capabilities.get("thread_writable_roots"):
        after["thread-writable-roots"] = dict(sorted(derived["writable_roots"].items()))
    if capabilities.get("projectless_thread_ids"):
        after["projectless-thread-ids"] = derived["projectless_active"]
    if capabilities.get("thread_workspace_root_hints"):
        after["thread-workspace-root-hints"] = dict(sorted(derived["workspace_hints"].items()))

    changed_without_generation = any(after.get(key) != before.get(key) for key in PROJECTION_KEYS if key in before)
    if capabilities.get("generation_guard") and changed_without_generation:
        after["generation"] = before["generation"] + 1

    return after


def _hydrate_live(case: Mapping[str, Any], assignments: Mapping[str, str]) -> List[Dict[str, Any]]:
    rows = copy.deepcopy(case.get("live_projection", []))
    for row in rows:
        if "project_id" in row:
            row["project_id"] = assignments.get(row.get("thread_id"))
    return rows


def _semantic_change_count(before: Mapping[str, Any], after: Mapping[str, Any], live_before: List[Mapping[str, Any]], live_after: List[Mapping[str, Any]]) -> int:
    count = 0
    keys = set(before) | set(after)
    for key in keys:
        if before.get(key) != after.get(key):
            count += 1
    if live_before != live_after:
        count += 1
    return count


def _evaluate_once(case: Mapping[str, Any]) -> Dict[str, Any]:
    durable_threads = list(case.get("durable_threads", []))
    persisted = copy.deepcopy(case.get("persisted_projection", {}))
    live_before = copy.deepcopy(case.get("live_projection", []))
    capabilities = discover_capabilities(persisted, live_before)

    if not durable_threads:
        return {
            "status": "INCONCLUSIVE_MISSING_DURABLE_EVIDENCE",
            "capabilities": capabilities,
            "semantic_changes": 0,
            "conversation_content_mutations": 0,
            "ambiguous_matches": 0,
            "projection_after": persisted,
            "live_after": live_before,
            "derived": {
                "assignments": {},
                "projectless_active": [],
                "archived_unassigned": [],
            },
        }

    mutation_count = _content_mutation_count(case)
    if mutation_count:
        return {
            "status": "BLOCK_CONTENT_MUTATION",
            "capabilities": capabilities,
            "semantic_changes": 0,
            "conversation_content_mutations": mutation_count,
            "ambiguous_matches": 0,
            "projection_after": persisted,
            "live_after": live_before,
            "derived": _derive_state(case),
        }

    incoming = case.get("incoming_projection")
    if (
        isinstance(incoming, Mapping)
        and isinstance(incoming.get("generation"), int)
        and isinstance(persisted.get("generation"), int)
        and incoming["generation"] < persisted["generation"]
    ):
        return {
            "status": "BLOCK_STALE_GENERATION",
            "capabilities": capabilities,
            "semantic_changes": 0,
            "conversation_content_mutations": 0,
            "ambiguous_matches": 0,
            "projection_after": persisted,
            "live_after": live_before,
            "derived": _derive_state(case),
        }

    derived = _derive_state(case)
    if derived["ambiguous_matches"]:
        return {
            "status": "UNRESOLVED_AMBIGUOUS_PROJECT",
            "capabilities": capabilities,
            "semantic_changes": 0,
            "conversation_content_mutations": 0,
            "ambiguous_matches": derived["ambiguous_matches"],
            "projection_after": persisted,
            "live_after": live_before,
            "derived": derived,
        }

    projection_after = _build_projection_after(case, derived, capabilities)
    live_after = _hydrate_live(case, derived["assignments"])
    semantic_changes = _semantic_change_count(persisted, projection_after, live_before, live_after)

    return {
        "status": "RECOVERED_PROJECTION" if semantic_changes else "NO_CHANGES_REQUIRED",
        "capabilities": capabilities,
        "semantic_changes": semantic_changes,
        "conversation_content_mutations": 0,
        "ambiguous_matches": 0,
        "projection_after": projection_after,
        "live_after": live_after,
        "derived": derived,
    }


def evaluate(case: Mapping[str, Any]) -> Dict[str, Any]:
    first = _evaluate_once(case)

    second_run_changes: Optional[int] = None
    if first["status"] in {"RECOVERED_PROJECTION", "NO_CHANGES_REQUIRED"}:
        second_case = copy.deepcopy(case)
        second_case["persisted_projection"] = first["projection_after"]
        second_case["live_projection"] = first["live_after"]
        second_case.pop("incoming_projection", None)
        second = _evaluate_once(second_case)
        second_run_changes = second["semantic_changes"]

    persisted = case.get("persisted_projection", {})
    assignments_before = len(persisted.get("thread-project-assignments", {}))
    projects_before = len(persisted.get("local-projects", []))
    assignments_after = len(first["derived"].get("assignments", {}))
    projects_after = len(case.get("projects", []))

    report = {
        "schema": "ls.state-projection-recovery-report.v0.1",
        "case_id": case.get("case_id", "unknown"),
        "status": first["status"],
        "capabilities": first["capabilities"],
        "durable_thread_count": len(case.get("durable_threads", [])),
        "projects_before": projects_before,
        "projects_after": projects_after,
        "assignments_before": assignments_before,
        "assignments_after": assignments_after,
        "projectless_active": len(first["derived"].get("projectless_active", [])),
        "archived_unassigned": len(first["derived"].get("archived_unassigned", [])),
        "conversation_content_mutations": first["conversation_content_mutations"],
        "ambiguous_matches": first["ambiguous_matches"],
        "semantic_changes": first["semantic_changes"],
        "second_run_semantic_changes": second_run_changes,
    }
    assert report["status"] in VERDICTS
    return report


def run_cases(path: Path) -> List[Dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload["cases"] if isinstance(payload, dict) else payload
    return [evaluate(case) for case in cases]


def main(argv: List[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <cases.json>", file=sys.stderr)
        return 2
    reports = run_cases(Path(argv[1]))
    print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
