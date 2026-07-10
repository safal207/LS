#!/usr/bin/env python3
"""Deterministic semantic validator for LS Causal Phase Trail V0."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
PHASES = {
    "IDEA",
    "CANDIDATE",
    "UNSTABLE",
    "UNDER_REVIEW",
    "RISK_DISCOVERED",
    "CORRECTED",
    "EVIDENCE_ACCUMULATING",
    "STABLE",
    "MERGE_READY",
    "MERGED",
}
RELATIONS = {
    "PRECEDED",
    "CAUSED",
    "DETECTED",
    "BLOCKED",
    "RESOLVED",
    "INVALIDATED",
    "CONFIRMED",
    "ENABLED",
    "REJECTED",
}
NODE_KINDS = {
    "EVENT",
    "STATE",
    "EVIDENCE",
    "CAUSE",
    "PHASE_TRANSITION",
    "DECISION",
    "ROUTE",
    "OUTCOME",
}
CLAIM_ROLES = {
    "DETECTOR",
    "IMMEDIATE_CAUSE",
    "ROOT_CAUSE",
    "AMPLIFYING_CONDITION",
    "CORRECTIVE_ACTION",
    "OTHER",
}
EVIDENCE_STATUSES = {"FRESH", "STALE", "NOT_APPLICABLE"}
SPACE_KINDS = {
    "REPOSITORY",
    "PULL_REQUEST",
    "ARTIFACT",
    "COMPONENT",
    "SURFACE",
    "VIEWPORT",
    "BROWSER_CAPABILITY",
    "AGENT",
    "GATE",
    "EVIDENCE",
}


class TrailValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise TrailValidationError(message)


def require_object(value: Any, name: str) -> dict[str, Any]:
    require(isinstance(value, dict), f"{name} must be an object")
    return value


def require_list(value: Any, name: str) -> list[Any]:
    require(isinstance(value, list), f"{name} must be an array")
    return value


def exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    require(set(value) == expected, f"{name} contains missing or unknown fields")


def parse_time(value: Any, name: str) -> datetime:
    require(isinstance(value, str), f"{name} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TrailValidationError(f"{name} must be an RFC3339 date-time") from exc
    require(parsed.tzinfo is not None, f"{name} must include a timezone offset")
    return parsed


def require_sha(value: Any, name: str) -> None:
    require(isinstance(value, str) and bool(SHA_RE.fullmatch(value)), f"{name} must be a full lowercase SHA")


def require_id(value: Any, name: str) -> None:
    require(isinstance(value, str) and bool(ID_RE.fullmatch(value)), f"{name} is invalid")


def unique_index(items: list[dict[str, Any]], key: str, name: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        require_object(item, f"{name}[{index}]")
        item_id = item.get(key)
        require_id(item_id, f"{name}[{index}].{key}")
        require(item_id not in result, f"duplicate {name} id: {item_id}")
        result[item_id] = item
    return result


def route_score(components: dict[str, Any]) -> int:
    return (
        components["riskReduction"]
        + components["evidenceConfidence"]
        + components["reversibility"]
        - components["implementationCost"]
        - components["scopeExpansion"]
        - components["staleEvidenceCost"]
    )


def validate_trail(trail: dict[str, Any]) -> None:
    exact_keys(
        trail,
        {
            "schemaVersion",
            "trailId",
            "authority",
            "observedAt",
            "subject",
            "spaces",
            "nodes",
            "edges",
            "phaseHistory",
            "routes",
            "decision",
        },
        "trail",
    )
    require(trail["schemaVersion"] == "ls.causal-phase-trail.v0", "unsupported schemaVersion")
    require(isinstance(trail["trailId"], str) and trail["trailId"].startswith("CPT-"), "trailId is invalid")
    require(trail["authority"] == "EVIDENCE_ONLY", "trail must remain evidence-only")
    trail_observed_at = parse_time(trail["observedAt"], "observedAt")

    subject = require_object(trail["subject"], "subject")
    exact_keys(subject, {"repository", "pullRequest", "baseHead", "currentHead"}, "subject")
    require(isinstance(subject["repository"], str) and "/" in subject["repository"], "subject.repository is invalid")
    require(isinstance(subject["pullRequest"], int) and subject["pullRequest"] > 0, "subject.pullRequest is invalid")
    require_sha(subject["baseHead"], "subject.baseHead")
    require_sha(subject["currentHead"], "subject.currentHead")
    require(subject["baseHead"] != subject["currentHead"], "baseHead and currentHead must differ")

    spaces = require_list(trail["spaces"], "spaces")
    require(spaces, "spaces must not be empty")
    space_index = unique_index(spaces, "id", "spaces")
    for space_id, space in space_index.items():
        exact_keys(space, {"id", "kind", "value"}, f"space {space_id}")
        require(space["kind"] in SPACE_KINDS, f"space {space_id} kind is invalid")
        require(isinstance(space["value"], str) and space["value"], f"space {space_id} value is invalid")

    nodes = require_list(trail["nodes"], "nodes")
    require(nodes, "nodes must not be empty")
    node_index = unique_index(nodes, "id", "nodes")
    node_times: dict[str, datetime] = {}
    for node_id, node in node_index.items():
        exact_keys(
            node,
            {
                "id",
                "kind",
                "label",
                "eventTime",
                "observedAt",
                "validFromHead",
                "validUntilHead",
                "spaceRefs",
                "agent",
                "claimRole",
                "evidenceStatus",
                "blocking",
                "binding",
                "source",
            },
            f"node {node_id}",
        )
        require(node["kind"] in NODE_KINDS, f"node {node_id} kind is invalid")
        require(isinstance(node["label"], str) and node["label"], f"node {node_id} label is invalid")
        event_time = parse_time(node["eventTime"], f"node {node_id}.eventTime")
        observed_at = parse_time(node["observedAt"], f"node {node_id}.observedAt")
        require(event_time <= observed_at, f"node {node_id} cannot be observed before it exists")
        require(observed_at <= trail_observed_at, f"node {node_id} is observed after the trail snapshot")
        node_times[node_id] = event_time
        require_sha(node["validFromHead"], f"node {node_id}.validFromHead")
        if node["validUntilHead"] is not None:
            require_sha(node["validUntilHead"], f"node {node_id}.validUntilHead")
            require(node["validUntilHead"] != node["validFromHead"], f"node {node_id} validity interval is empty")
        refs = require_list(node["spaceRefs"], f"node {node_id}.spaceRefs")
        require(refs, f"node {node_id} must reference at least one space")
        require(len(refs) == len(set(refs)), f"node {node_id} has duplicate spaceRefs")
        for ref in refs:
            require(ref in space_index, f"node {node_id} references unknown space {ref}")
        require(node["agent"] is None or isinstance(node["agent"], str), f"node {node_id}.agent is invalid")
        require(node["claimRole"] in CLAIM_ROLES, f"node {node_id}.claimRole is invalid")
        require(node["evidenceStatus"] in EVIDENCE_STATUSES, f"node {node_id}.evidenceStatus is invalid")
        require(isinstance(node["blocking"], bool), f"node {node_id}.blocking must be boolean")
        require(isinstance(node["binding"], bool), f"node {node_id}.binding must be boolean")
        require(isinstance(node["source"], str) and node["source"], f"node {node_id}.source is invalid")
        if node["kind"] == "EVIDENCE" and node["binding"] and node["evidenceStatus"] == "FRESH":
            require(node["validFromHead"] == subject["currentHead"], f"fresh binding evidence {node_id} must bind currentHead")
            require(node["validUntilHead"] is None, f"fresh evidence {node_id} cannot have validUntilHead")
        if node["evidenceStatus"] == "STALE":
            require(node["validUntilHead"] is not None, f"stale node {node_id} must record validUntilHead")
        if node["claimRole"] in {"IMMEDIATE_CAUSE", "ROOT_CAUSE", "AMPLIFYING_CONDITION"}:
            require(node["kind"] == "CAUSE", f"causal claim node {node_id} must use kind CAUSE")
        if node["claimRole"] == "DETECTOR":
            require(node["kind"] in {"EVENT", "EVIDENCE"}, f"detector {node_id} must be event or evidence")

    edges = require_list(trail["edges"], "edges")
    require(edges, "edges must not be empty")
    edge_index = unique_index(edges, "id", "edges")
    for edge_id, edge in edge_index.items():
        exact_keys(edge, {"id", "from", "to", "relation", "binding", "explanation"}, f"edge {edge_id}")
        require(edge["from"] in node_index, f"edge {edge_id} has unknown from node")
        require(edge["to"] in node_index, f"edge {edge_id} has unknown to node")
        require(edge["from"] != edge["to"], f"edge {edge_id} cannot self-reference")
        require(edge["relation"] in RELATIONS, f"edge {edge_id} relation is invalid")
        require(isinstance(edge["binding"], bool), f"edge {edge_id}.binding must be boolean")
        require(isinstance(edge["explanation"], str) and edge["explanation"], f"edge {edge_id} explanation is invalid")
        if edge["relation"] == "PRECEDED":
            require(not edge["binding"], f"temporal edge {edge_id} cannot be binding causation")
            require(node_times[edge["from"]] <= node_times[edge["to"]], f"temporal edge {edge_id} reverses event time")
        if edge["relation"] == "DETECTED":
            require(node_index[edge["from"]]["claimRole"] == "DETECTOR", f"DETECTED edge {edge_id} must originate from a detector")
        if edge["relation"] == "INVALIDATED":
            target = node_index[edge["to"]]
            require(target["evidenceStatus"] == "STALE", f"INVALIDATED edge {edge_id} must target stale evidence")
        if edge["relation"] == "RESOLVED":
            require(node_index[edge["from"]]["claimRole"] == "CORRECTIVE_ACTION", f"RESOLVED edge {edge_id} must originate from corrective action")

    closed_blocker_ids = {
        edge["to"]
        for edge in edges
        if edge["binding"] and edge["relation"] in {"RESOLVED", "INVALIDATED"}
    }

    phase_history = require_list(trail["phaseHistory"], "phaseHistory")
    require(phase_history, "phaseHistory must not be empty")
    prior_time: datetime | None = None
    for index, entry in enumerate(phase_history):
        entry = require_object(entry, f"phaseHistory[{index}]")
        exact_keys(entry, {"phase", "enteredAt", "triggerNodeId", "transitionKind", "guards"}, f"phaseHistory[{index}]")
        require(entry["phase"] in PHASES, f"phaseHistory[{index}].phase is invalid")
        entered_at = parse_time(entry["enteredAt"], f"phaseHistory[{index}].enteredAt")
        if prior_time is not None:
            require(prior_time <= entered_at, "phaseHistory must be chronological")
        prior_time = entered_at
        trigger_id = entry["triggerNodeId"]
        require(trigger_id in node_index, f"phaseHistory[{index}] trigger is unknown")
        require(
            node_times[trigger_id] <= entered_at,
            f"phaseHistory[{index}] cannot enter before trigger event {trigger_id}",
        )
        require(entry["transitionKind"] in {"FORWARD", "REGRESSION"}, f"phaseHistory[{index}].transitionKind is invalid")
        guards = require_list(entry["guards"], f"phaseHistory[{index}].guards")
        require(guards, f"phaseHistory[{index}] must contain guards")
        has_unsatisfied = False
        for guard_index, guard in enumerate(guards):
            guard = require_object(guard, f"phaseHistory[{index}].guards[{guard_index}]")
            exact_keys(guard, {"name", "satisfied", "evidenceNodeIds"}, f"phase guard {index}:{guard_index}")
            require(isinstance(guard["name"], str) and guard["name"], f"phase guard {index}:{guard_index} name is invalid")
            require(isinstance(guard["satisfied"], bool), f"phase guard {index}:{guard_index} satisfied must be boolean")
            has_unsatisfied = has_unsatisfied or not guard["satisfied"]
            evidence_ids = require_list(guard["evidenceNodeIds"], f"phase guard {index}:{guard_index}.evidenceNodeIds")
            require(len(evidence_ids) == len(set(evidence_ids)), f"phase guard {index}:{guard_index} duplicates evidence")
            for evidence_id in evidence_ids:
                require(evidence_id in node_index, f"phase guard {index}:{guard_index} references unknown node {evidence_id}")
        if entry["transitionKind"] == "REGRESSION":
            require(entry["phase"] == "RISK_DISCOVERED", "V0 regressions must return to RISK_DISCOVERED")
            require(has_unsatisfied, "phase regression requires at least one unsatisfied guard")

    routes = require_list(trail["routes"], "routes")
    require(len(routes) >= 2, "at least two routes are required")
    route_index = unique_index(routes, "routeId", "routes")
    selected_routes: list[str] = []
    for route_id, route in route_index.items():
        exact_keys(route, {"routeId", "title", "selected", "components", "score", "explanation", "rejectedReason"}, f"route {route_id}")
        require(isinstance(route["title"], str) and route["title"], f"route {route_id} title is invalid")
        require(isinstance(route["selected"], bool), f"route {route_id}.selected must be boolean")
        components = require_object(route["components"], f"route {route_id}.components")
        exact_keys(
            components,
            {"riskReduction", "evidenceConfidence", "reversibility", "implementationCost", "scopeExpansion", "staleEvidenceCost"},
            f"route {route_id}.components",
        )
        for name, value in components.items():
            require(isinstance(value, int) and 0 <= value <= 5, f"route {route_id}.{name} must be 0..5")
        require(route["score"] == route_score(components), f"route {route_id} score does not match components")
        require(isinstance(route["explanation"], str) and route["explanation"], f"route {route_id} explanation is required")
        if route["selected"]:
            selected_routes.append(route_id)
            require(route["rejectedReason"] is None, f"selected route {route_id} cannot have rejectedReason")
        else:
            require(isinstance(route["rejectedReason"], str) and route["rejectedReason"], f"rejected route {route_id} needs a reason")
    require(len(selected_routes) == 1, "exactly one route must be selected")

    decision = require_object(trail["decision"], "decision")
    exact_keys(
        decision,
        {
            "currentPhase",
            "bestRouteId",
            "rootCauseNodeId",
            "detectorNodeIds",
            "unresolvedBlockerNodeIds",
            "nextLegalTransitions",
            "summary",
        },
        "decision",
    )
    require(decision["currentPhase"] in PHASES, "decision.currentPhase is invalid")
    require(decision["currentPhase"] == phase_history[-1]["phase"], "currentPhase must equal the last phase entry")
    require(decision["bestRouteId"] == selected_routes[0], "bestRouteId must reference the selected route")
    root_id = decision["rootCauseNodeId"]
    require(root_id in node_index, "rootCauseNodeId is unknown")
    require(node_index[root_id]["claimRole"] == "ROOT_CAUSE", "rootCauseNodeId must point to a ROOT_CAUSE node")
    detectors = require_list(decision["detectorNodeIds"], "decision.detectorNodeIds")
    require(detectors, "at least one detector is required")
    require(len(detectors) == len(set(detectors)), "detectorNodeIds must be unique")
    for detector_id in detectors:
        require(detector_id in node_index, f"unknown detector node {detector_id}")
        require(node_index[detector_id]["claimRole"] == "DETECTOR", f"node {detector_id} is not a detector")
        require(detector_id != root_id, "a detector cannot also be the root cause")
    causal_outgoing = [
        edge for edge in edges
        if edge["from"] == root_id and edge["relation"] == "CAUSED" and edge["binding"]
    ]
    require(causal_outgoing, "root cause requires at least one binding CAUSED edge")

    blockers = require_list(decision["unresolvedBlockerNodeIds"], "decision.unresolvedBlockerNodeIds")
    require(len(blockers) == len(set(blockers)), "unresolvedBlockerNodeIds must be unique")

    active_blocker_ids: set[str] = set()
    for node_id, node in node_index.items():
        if not node["blocking"] or node["validUntilHead"] is not None or node_id in closed_blocker_ids:
            continue
        if node["kind"] == "EVIDENCE" and not (
            node["evidenceStatus"] == "FRESH"
            and node["validFromHead"] == subject["currentHead"]
        ):
            continue
        active_blocker_ids.add(node_id)

    require(
        set(blockers) == active_blocker_ids,
        "unresolvedBlockerNodeIds must exactly match active blocking nodes",
    )

    for blocker_id in blockers:
        require(blocker_id in node_index, f"unknown blocker node {blocker_id}")
        require(node_index[blocker_id]["blocking"], f"node {blocker_id} is not marked blocking")
        if node_index[blocker_id]["kind"] == "EVIDENCE":
            require(node_index[blocker_id]["evidenceStatus"] == "FRESH", f"blocking evidence {blocker_id} must be fresh")
            require(node_index[blocker_id]["validFromHead"] == subject["currentHead"], f"blocking evidence {blocker_id} must bind currentHead")
    if blockers:
        require(decision["currentPhase"] == "RISK_DISCOVERED", "unresolved blockers require RISK_DISCOVERED")
    if decision["currentPhase"] in {"MERGE_READY", "MERGED"}:
        phase = decision["currentPhase"]
        require(not blockers, f"{phase} cannot contain unresolved blockers")
        require(
            all(guard["satisfied"] for guard in phase_history[-1]["guards"]),
            f"{phase} guards must all be satisfied",
        )

    next_phases = require_list(decision["nextLegalTransitions"], "decision.nextLegalTransitions")
    require(len(next_phases) == len(set(next_phases)), "nextLegalTransitions must be unique")
    for phase in next_phases:
        require(phase in PHASES, f"unknown next phase {phase}")
        require(phase != decision["currentPhase"], "nextLegalTransitions cannot repeat currentPhase")
    require(isinstance(decision["summary"], str) and decision["summary"], "decision.summary is required")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trail", type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.trail.read_text(encoding="utf-8"))
        require_object(payload, "trail")
        validate_trail(payload)
    except (OSError, json.JSONDecodeError, TrailValidationError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {payload['trailId']} -> {payload['decision']['currentPhase']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
