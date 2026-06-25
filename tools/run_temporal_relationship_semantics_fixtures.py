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

        edge_ids: set[str] = set()
        for edge in vector["edges"]:
            edge_id = edge["edge_id"]
            if edge_id in edge_ids:
                raise ValueError(f"{fixture_id}: duplicate edge id {edge_id}")
            edge_ids.add(edge_id)
            if edge["relation_type"] not in document["relation_policies"]:
                raise ValueError(
                    f"{fixture_id}: missing policy for relation {edge['relation_type']}"
                )
            if edge["valid_until"] is not None:
                if _parse_time(edge["valid_until"]) < _parse_time(edge["valid_from"]):
                    raise ValueError(f"{fixture_id}: valid_until precedes valid_from")


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
        "historical_edge_ids": sorted(historical),
        "reason_codes": reasons,
        "selected_edge_ids": sorted(selected),
        "suppressed_edge_ids": sorted(suppressed),
    }


def _is_temporally_current(edge: dict[str, Any], now: datetime) -> bool:
    if edge["status"] in {"SUPERSEDED", "EXPIRED", "REVOKED"}:
        return False
    if _parse_time(edge["valid_from"]) > now:
        return False
    valid_until = edge.get("valid_until")
    return valid_until is None or _parse_time(valid_until) > now


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

    unauthorized_promotions = [
        edge
        for edge in matching
        if SCOPE_RANK[edge["scope"]] > SCOPE_RANK[edge["source_scope"]]
        and not edge.get("promotion_authorization_ref")
    ]
    if unauthorized_promotions:
        return _result(
            "REJECT",
            [],
            [],
            [edge["edge_id"] for edge in unauthorized_promotions],
            ["SCOPE_PROMOTION_UNAUTHORIZED"],
        )

    revoked = [
        edge
        for edge in matching
        if edge["status"] == "REVOKED"
        and policy.get("authority_sensitive") is True
    ]
    if revoked:
        return _result(
            "REJECT",
            [],
            [edge["edge_id"] for edge in revoked],
            [],
            ["DELEGATION_REVOKED"],
        )

    historical = [
        edge
        for edge in matching
        if not _is_temporally_current(edge, now)
    ]
    current = [
        edge
        for edge in matching
        if _is_temporally_current(edge, now)
    ]
    historical_ids = [edge["edge_id"] for edge in historical]

    if not current:
        return _result(
            "RETURN_HISTORICAL",
            [],
            historical_ids,
            [],
            ["RELATIONSHIP_NOT_CURRENT"],
        )

    disputed = [edge for edge in current if edge["status"] == "DISPUTED"]
    if disputed:
        return _result(
            "ABSTAIN",
            [],
            historical_ids,
            [edge["edge_id"] for edge in disputed],
            ["RELATIONSHIP_DISPUTED"],
        )

    mention_only = [
        edge
        for edge in current
        if edge["evidence_kind"] == "mention"
    ]
    if mention_only:
        return _result(
            "ABSTAIN",
            [],
            historical_ids,
            [edge["edge_id"] for edge in mention_only],
            ["MENTION_ONLY"],
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
            [edge["edge_id"] for edge in current],
            ["NO_VISIBLE_SCOPE"],
        )

    winners = [edge for edge in current if edge["scope"] == winning_scope]
    suppressed = [
        edge["edge_id"]
        for edge in current
        if edge["scope"] != winning_scope
    ]

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
        targets = {edge["target_entity_id"] for edge in winners}
        if len(targets) > 1:
            return _result(
                "CONFLICTED",
                [],
                historical_ids,
                suppressed,
                ["UNRESOLVED_CURRENT_CONTRADICTION"],
            )

    selected_ids = [edge["edge_id"] for edge in winners]
    ratified = all(edge["status"] == "RATIFIED" for edge in winners)

    if historical_ids:
        reasons = ["SUPERSEDED_HISTORY_RETAINED"]
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
