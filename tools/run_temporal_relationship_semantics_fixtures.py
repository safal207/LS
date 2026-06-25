#!/usr/bin/env python3
"""Run engine-neutral temporal relationship semantics conformance fixtures."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "temporal-relationship-semantics"
SCHEMA_PATH = FIXTURE_DIR / "schema-v0.1.json"
PINS_PATH = FIXTURE_DIR / "pins-v0.1.json"
VECTOR_GLOB = "vectors-*.json"
OUTPUT_PATH = ROOT / "artifacts" / "temporal-relationship-semantics-conformance.json"

PROFILE = "temporal-relationship-semantics-v0.1"
SCHEMA_VERSION = "temporal-relationship-semantics-fixtures-v0.1"
SCOPE_RANK = {"private": 0, "group": 1, "global": 2}
HISTORICAL_STATUSES = {"SUPERSEDED", "EXPIRED", "REVOKED"}
AUTHORITY_DEFAULTS = {
    "may_authorize_execution": False,
    "may_establish_consent": False,
    "may_establish_mutuality": False,
    "may_establish_truth": False,
    "may_grant_permissions": False,
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {path}")
    return value


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _verify_pins() -> dict[str, str]:
    pins = _load_json(PINS_PATH)
    expected = pins.get("sha256")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("missing fixture digest pins")

    paths = sorted(FIXTURE_DIR.glob(VECTOR_GLOB))
    observed_names = {path.name for path in paths}
    if observed_names != set(expected):
        raise ValueError(
            f"fixture set mismatch: observed={sorted(observed_names)} "
            f"pinned={sorted(expected)}"
        )

    actual: dict[str, str] = {}
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != expected[path.name]:
            raise ValueError(
                f"{path.name}: digest mismatch actual={digest} "
                f"pinned={expected[path.name]}"
            )
        actual[path.name] = digest
    return actual


def _validate_document(document: dict[str, Any], schema: dict[str, Any]) -> None:
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).validate(document)

    if document.get("profile") != PROFILE:
        raise ValueError("unsupported profile")
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported schema version")
    if document.get("authority_defaults") != AUTHORITY_DEFAULTS:
        raise ValueError("authority defaults must remain all false")

    fixture_ids: set[str] = set()
    for vector in document["vectors"]:
        fixture_id = vector["fixture_id"]
        if fixture_id in fixture_ids:
            raise ValueError(f"duplicate fixture id: {fixture_id}")
        fixture_ids.add(fixture_id)

        query_relation = vector["query"]["relation_type"]
        if query_relation not in document["relation_policies"]:
            raise ValueError(f"{fixture_id}: missing policy for query relation")

        edge_by_id: dict[str, dict[str, Any]] = {}
        for edge in vector["edges"]:
            edge_id = edge["edge_id"]
            if edge_id in edge_by_id:
                raise ValueError(f"{fixture_id}: duplicate edge id {edge_id}")
            edge_by_id[edge_id] = edge

            if edge["relation_type"] not in document["relation_policies"]:
                raise ValueError(
                    f"{fixture_id}: missing policy for relation {edge['relation_type']}"
                )
            if edge["valid_until"] is not None:
                if _parse_time(edge["valid_until"]) < _parse_time(edge["valid_from"]):
                    raise ValueError(f"{fixture_id}: valid_until precedes valid_from")
            if edge["status"] == "RATIFIED" and not edge.get("ratification_ref"):
                raise ValueError(f"{fixture_id}: RATIFIED edge lacks ratification_ref")

        for edge in vector["edges"]:
            prior_id = edge.get("supersedes")
            if prior_id is None:
                continue
            prior = edge_by_id.get(prior_id)
            if prior is None:
                raise ValueError(
                    f"{fixture_id}: supersedes references unknown edge {prior_id}"
                )
            if prior["status"] != "SUPERSEDED":
                raise ValueError(
                    f"{fixture_id}: superseded edge {prior_id} is not SUPERSEDED"
                )
            if (
                prior["source_entity_id"] != edge["source_entity_id"]
                or prior["relation_type"] != edge["relation_type"]
            ):
                raise ValueError(
                    f"{fixture_id}: supersession changes source or relation type"
                )
            if _parse_time(edge["valid_from"]) < _parse_time(prior["valid_from"]):
                raise ValueError(
                    f"{fixture_id}: superseding edge predates superseded edge"
                )

        expected = vector["expected"]
        expected_ids = set(
            expected["selected_edge_ids"]
            + expected["historical_edge_ids"]
            + expected["suppressed_edge_ids"]
        )
        if not expected_ids.issubset(edge_by_id):
            raise ValueError(f"{fixture_id}: expected result references unknown edge")
        result_sets = [
            set(expected["selected_edge_ids"]),
            set(expected["historical_edge_ids"]),
            set(expected["suppressed_edge_ids"]),
        ]
        if any(
            result_sets[left].intersection(result_sets[right])
            for left in range(len(result_sets))
            for right in range(left + 1, len(result_sets))
        ):
            raise ValueError(f"{fixture_id}: expected edge classifications overlap")


def _result(
    decision: str,
    selected: list[str],
    historical: list[str],
    suppressed: list[str],
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "authority_effects": dict(AUTHORITY_DEFAULTS),
        "decision": decision,
        "historical_edge_ids": sorted(set(historical)),
        "reason_codes": reasons,
        "selected_edge_ids": sorted(set(selected)),
        "suppressed_edge_ids": sorted(set(suppressed)),
    }


def _temporal_state(edge: dict[str, Any], now: datetime) -> str:
    valid_from = _parse_time(edge["valid_from"])
    if valid_from > now:
        return "future"
    if edge["status"] in HISTORICAL_STATUSES:
        return "historical"
    valid_until = edge.get("valid_until")
    if valid_until is not None and _parse_time(valid_until) <= now:
        return "historical"
    return "current"


def _history_reason(historical: list[dict[str, Any]]) -> str:
    statuses = {edge["status"] for edge in historical}
    if "REVOKED" in statuses:
        return "REVOKED_HISTORY_RETAINED"
    if "SUPERSEDED" in statuses:
        return "SUPERSEDED_HISTORY_RETAINED"
    return "HISTORICAL_CONTEXT_RETAINED"


def _evaluate(
    vector: dict[str, Any],
    relation_policies: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    query = vector["query"]
    now = _parse_time(query["now"])
    policy = relation_policies[query["relation_type"]]

    matching = [
        edge
        for edge in vector["edges"]
        if edge["source_entity_id"] == query["source_entity_id"]
        and edge["relation_type"] == query["relation_type"]
    ]

    if not matching:
        return _result("ABSTAIN", [], [], [], ["NO_RELATIONSHIP_EVIDENCE"])

    temporal = {
        edge["edge_id"]: _temporal_state(edge, now)
        for edge in matching
    }
    historical = [
        edge for edge in matching if temporal[edge["edge_id"]] == "historical"
    ]
    current = [
        edge for edge in matching if temporal[edge["edge_id"]] == "current"
    ]
    future = [
        edge for edge in matching if temporal[edge["edge_id"]] == "future"
    ]
    historical_ids = [edge["edge_id"] for edge in historical]
    future_ids = [edge["edge_id"] for edge in future]

    unauthorized_promotions = [
        edge
        for edge in current
        if SCOPE_RANK[edge["scope"]] > SCOPE_RANK[edge["source_scope"]]
        and not edge.get("promotion_authorization_ref")
    ]
    if unauthorized_promotions:
        return _result(
            "REJECT",
            [],
            historical_ids,
            future_ids + [edge["edge_id"] for edge in unauthorized_promotions],
            ["SCOPE_PROMOTION_UNAUTHORIZED"],
        )

    revoked = [
        edge
        for edge in historical
        if edge["status"] == "REVOKED"
        and policy.get("authority_sensitive") is True
    ]
    if revoked and current:
        revocation_conflicts = []
        for revoked_edge in revoked:
            revocation_time = (
                _parse_time(revoked_edge["valid_until"])
                if revoked_edge.get("valid_until")
                else now
            )
            for current_edge in current:
                if (
                    current_edge["target_entity_id"]
                    == revoked_edge["target_entity_id"]
                    and _parse_time(current_edge["valid_from"]) < revocation_time
                ):
                    revocation_conflicts.extend([revoked_edge, current_edge])
        if revocation_conflicts:
            return _result(
                "REJECT",
                [],
                historical_ids,
                future_ids + [edge["edge_id"] for edge in revocation_conflicts],
                ["DELEGATION_REVOCATION_CONFLICT"],
            )

    if not current:
        if revoked:
            return _result(
                "REJECT",
                [],
                historical_ids,
                future_ids,
                ["DELEGATION_REVOKED"],
            )
        if historical:
            return _result(
                "RETURN_HISTORICAL",
                [],
                historical_ids,
                future_ids,
                ["RELATIONSHIP_NOT_CURRENT"],
            )
        return _result(
            "ABSTAIN",
            [],
            [],
            future_ids,
            ["RELATIONSHIP_NOT_YET_VALID"],
        )

    winning_scope: Optional[str] = next(
        (
            scope
            for scope in query["scope_precedence"]
            if any(edge["scope"] == scope for edge in current)
        ),
        None,
    )
    if winning_scope is None:
        return _result(
            "ABSTAIN",
            [],
            historical_ids,
            future_ids + [edge["edge_id"] for edge in current],
            ["NO_VISIBLE_SCOPE"],
        )

    winners = [edge for edge in current if edge["scope"] == winning_scope]
    suppressed = future_ids + [
        edge["edge_id"]
        for edge in current
        if edge["scope"] != winning_scope
    ]

    disputed = [edge for edge in winners if edge["status"] == "DISPUTED"]
    if disputed:
        return _result(
            "ABSTAIN",
            [],
            historical_ids,
            suppressed + [edge["edge_id"] for edge in winners],
            ["RELATIONSHIP_DISPUTED"],
        )

    mentions = [edge for edge in winners if edge["evidence_kind"] == "mention"]
    substantive = [edge for edge in winners if edge["evidence_kind"] != "mention"]
    if not substantive:
        return _result(
            "ABSTAIN",
            [],
            historical_ids,
            suppressed + [edge["edge_id"] for edge in winners],
            ["MENTION_ONLY"],
        )
    suppressed.extend(edge["edge_id"] for edge in mentions)

    resolved: list[dict[str, Any]] = []
    targets: list[str] = []
    for edge in substantive:
        target = edge["target_entity_id"]
        if target not in targets:
            targets.append(target)
    for target in targets:
        target_edges = [
            edge for edge in substantive if edge["target_entity_id"] == target
        ]
        ratified_edges = [
            edge for edge in target_edges if edge["status"] == "RATIFIED"
        ]
        if ratified_edges:
            resolved.extend(ratified_edges)
            suppressed.extend(
                edge["edge_id"]
                for edge in target_edges
                if edge["status"] != "RATIFIED"
            )
        else:
            resolved.extend(target_edges)
    winners = resolved

    mutuality_required = (
        query["requires_mutual"]
        or policy.get("mutuality") == "required"
    )
    if mutuality_required:
        missing_reciprocity = []
        for edge in winners:
            participants = {
                edge["source_entity_id"],
                edge["target_entity_id"],
            }
            if (
                edge["directionality"] != "symmetric"
                or not participants.issubset(set(edge["confirmed_by"]))
                or not edge.get("ratification_ref")
            ):
                missing_reciprocity.append(edge)
        if missing_reciprocity:
            return _result(
                "ABSTAIN",
                [],
                historical_ids,
                suppressed + [edge["edge_id"] for edge in missing_reciprocity],
                ["RECIPROCITY_MISSING"],
            )

    if policy.get("cardinality") == "one":
        current_targets = {edge["target_entity_id"] for edge in winners}
        if len(current_targets) > 1:
            return _result(
                "CONFLICTED",
                [],
                historical_ids,
                suppressed,
                ["UNRESOLVED_CURRENT_CONTRADICTION"],
            )

    selected_ids = [edge["edge_id"] for edge in winners]
    ratified = all(edge["status"] == "RATIFIED" for edge in winners)

    if historical:
        reasons = [_history_reason(historical)]
    elif ratified:
        reasons = ["CURRENT_RELATIONSHIP_CONTEXT_ONLY"]
    else:
        reasons = ["UNRATIFIED_RELATIONSHIP_CLAIM"]

    return _result(
        "RETURN_CURRENT" if ratified else "RETURN_CLAIM",
        selected_ids,
        historical_ids,
        suppressed,
        reasons,
    )


def main() -> int:
    digests = _verify_pins()
    schema = _load_json(SCHEMA_PATH)

    documents = [
        _load_json(FIXTURE_DIR / filename)
        for filename in sorted(digests)
    ]
    for document in documents:
        _validate_document(document, schema)

    baseline_policies = documents[0]["relation_policies"]
    for document in documents[1:]:
        if document["relation_policies"] != baseline_policies:
            raise ValueError("relation policies drifted across fixture suites")

    results = []
    for document in documents:
        for vector in document["vectors"]:
            observed = _evaluate(vector, baseline_policies)
            expected = {
                **vector["expected"],
                "authority_effects": dict(AUTHORITY_DEFAULTS),
            }
            results.append(
                {
                    "fixture_id": vector["fixture_id"],
                    "expected": expected,
                    "observed": observed,
                    "passed": observed == expected,
                }
            )

    fixture_ids = [result["fixture_id"] for result in results]
    if len(fixture_ids) != len(set(fixture_ids)):
        raise ValueError("duplicate fixture id across suites")

    report = {
        "profile": PROFILE,
        "schema_version": SCHEMA_VERSION,
        "vector_sha256": digests,
        "boundary": (
            "Relationship memory may describe context and history. "
            "It does not create mutuality, consent, permission, truth, "
            "or execution authority."
        ),
        "results": results,
        "passed": all(result["passed"] for result in results),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
