#!/usr/bin/env python3
"""Deterministic evaluator for LS Relational Temporal Orientation Center v0.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SEVERITY = {"RESUME": 0, "ABSTAIN": 1, "REVALIDATE": 2, "REJECT": 3}

REASON_ORDER = {
    "REJECT": [
        "RELATIONSHIP_ID_MISMATCH",
        "RELATIONSHIP_EPOCH_MISMATCH",
        "ACTOR_RELATIONSHIP_MISMATCH",
        "ROLE_NOT_ACTIVE",
        "AUTHORITY_REVOKED",
        "AUTHORITY_SCOPE_MISMATCH",
        "RELATIONAL_BOUNDARY_VIOLATION",
        "RELATIONAL_EFFECT_ALREADY_COMPLETED",
        "TRUST_REVOKED",
        "ACTION_DIGEST_MISMATCH",
    ],
    "REVALIDATE": [
        "SHARED_INTENT_DRIFT",
        "SHARED_TARGET_STATE_DRIFT",
        "ROLE_CHANGED",
        "AUTHORITY_SUPERSEDED",
        "BOUNDARY_CHANGED",
        "TRUST_DISPUTED",
    ],
    "ABSTAIN": [
        "MISSING_RELATIONSHIP_EVIDENCE",
        "INCOMPLETE_HANDOFF",
        "AMBIGUOUS_RESPONSIBILITY",
        "UNRESOLVED_COMMITMENT_PRECONDITION",
    ],
}


def _result(
    fixture_id: str,
    verdict: str,
    reason_code: str,
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "fixture_id": fixture_id,
        "relationship_version": "relational-temporal-orientation-v0.1",
        "verdict": verdict,
        "reason_code": reason_code,
        "execution_authorized": False,
        "downstream_gates_required": True,
        "checks": checks,
    }


def _choose_fault(faults: list[tuple[str, str]]) -> tuple[str, str]:
    if not faults:
        return "RESUME", "RELATIONAL_ORIENTATION_VALID"

    highest = max(SEVERITY[verdict] for verdict, _ in faults)
    verdict = next(name for name, value in SEVERITY.items() if value == highest)
    reasons = {reason for candidate, reason in faults if candidate == verdict}
    for reason in REASON_ORDER[verdict]:
        if reason in reasons:
            return verdict, reason
    return verdict, sorted(reasons)[0]


def evaluate(case: dict[str, Any]) -> dict[str, Any]:
    fixture_id = case.get("fixture_id", "unknown")
    checks: list[dict[str, Any]] = []
    faults: list[tuple[str, str]] = []

    orientation = case.get("orientation", {})
    relationship = orientation.get("relationship", {})
    frame = orientation.get("temporal_frame", {})
    shared = orientation.get("shared_orientation", {})
    authoritative = case.get("authoritative_state", {})
    action = case.get("proposed_action", {})

    required_paths = [
        ("orientation.relationship.relationship_id", relationship.get("relationship_id")),
        ("orientation.relationship.relationship_epoch", relationship.get("relationship_epoch")),
        ("orientation.relationship.participants", relationship.get("participants")),
        ("orientation.temporal_frame.as_of", frame.get("as_of")),
        ("orientation.shared_orientation.shared_intent_digest", shared.get("shared_intent_digest")),
        ("orientation.shared_orientation.shared_target_state_digest", shared.get("shared_target_state_digest")),
        ("authoritative_state.relationship_id", authoritative.get("relationship_id")),
        ("authoritative_state.relationship_epoch", authoritative.get("relationship_epoch")),
        ("proposed_action.actor_id", action.get("actor_id")),
        ("proposed_action.action_digest", action.get("action_digest")),
    ]
    missing = [path for path, value in required_paths if value in (None, "", [])]
    if missing:
        checks.append({"check": "required_relationship_evidence", "status": "failed", "missing": missing})
        return _result(fixture_id, "ABSTAIN", "MISSING_RELATIONSHIP_EVIDENCE", checks)
    checks.append({"check": "required_relationship_evidence", "status": "passed"})

    def fault(check: str, verdict: str, reason: str, **details: Any) -> None:
        checks.append({"check": check, "status": "failed", **details})
        faults.append((verdict, reason))

    def passed(check: str) -> None:
        checks.append({"check": check, "status": "passed"})

    if relationship["relationship_id"] != authoritative["relationship_id"]:
        fault(
            "relationship_id",
            "REJECT",
            "RELATIONSHIP_ID_MISMATCH",
            observed=relationship["relationship_id"],
            expected=authoritative["relationship_id"],
        )
    else:
        passed("relationship_id")

    if relationship["relationship_epoch"] != authoritative["relationship_epoch"]:
        fault(
            "relationship_epoch",
            "REJECT",
            "RELATIONSHIP_EPOCH_MISMATCH",
            observed=relationship["relationship_epoch"],
            expected=authoritative["relationship_epoch"],
        )
    else:
        passed("relationship_epoch")

    actor_id = action["actor_id"]
    participant = next(
        (item for item in relationship.get("participants", []) if item.get("actor_id") == actor_id),
        None,
    )
    authoritative_role = authoritative.get("active_roles", {}).get(actor_id)

    if participant is None or authoritative_role is None:
        fault("actor_membership", "REJECT", "ACTOR_RELATIONSHIP_MISMATCH", actor_id=actor_id)
    else:
        passed("actor_membership")
        if participant.get("participation_state") != "active":
            fault(
                "role_state",
                "REJECT",
                "ROLE_NOT_ACTIVE",
                observed=participant.get("participation_state"),
                expected="active",
            )
        else:
            passed("role_state")
        if participant.get("role") != authoritative_role:
            fault(
                "role_identity",
                "REVALIDATE",
                "ROLE_CHANGED",
                observed=participant.get("role"),
                expected=authoritative_role,
            )
        else:
            passed("role_identity")

    allowed_actor = orientation.get("next_relational_transition", {}).get("allowed_actor_id")
    if allowed_actor and allowed_actor != actor_id:
        fault(
            "allowed_actor",
            "REJECT",
            "ACTOR_RELATIONSHIP_MISMATCH",
            observed=actor_id,
            expected=allowed_actor,
        )
    else:
        passed("allowed_actor")

    allowed_action = orientation.get("next_relational_transition", {}).get("allowed_action_digest")
    if allowed_action and allowed_action != action["action_digest"]:
        fault(
            "action_digest",
            "REJECT",
            "ACTION_DIGEST_MISMATCH",
            observed=action["action_digest"],
            expected=allowed_action,
        )
    else:
        passed("action_digest")

    if action.get("requires_delegation", False):
        capability = action.get("capability")
        edge = next(
            (
                item
                for item in orientation.get("authority_edges", [])
                if item.get("grantee") == actor_id and item.get("capability") == capability
            ),
            None,
        )
        if edge is None:
            fault("delegation_evidence", "ABSTAIN", "MISSING_RELATIONSHIP_EVIDENCE")
        else:
            if edge.get("state") in {"revoked", "expired"}:
                fault("delegation_state", "REJECT", "AUTHORITY_REVOKED", observed=edge.get("state"))
            elif edge.get("state") == "superseded":
                fault("delegation_state", "REVALIDATE", "AUTHORITY_SUPERSEDED")
            else:
                passed("delegation_state")

            if edge.get("scope_digest") != action.get("scope_digest"):
                fault(
                    "delegation_scope",
                    "REJECT",
                    "AUTHORITY_SCOPE_MISMATCH",
                    observed=action.get("scope_digest"),
                    expected=edge.get("scope_digest"),
                )
            else:
                passed("delegation_scope")

            authoritative_grant = next(
                (
                    item
                    for item in authoritative.get("authority_grants", [])
                    if item.get("grant_id") == edge.get("grant_id")
                ),
                None,
            )
            if authoritative_grant is None:
                fault("authoritative_delegation", "ABSTAIN", "MISSING_RELATIONSHIP_EVIDENCE")
            else:
                state = authoritative_grant.get("state")
                if state in {"revoked", "expired"}:
                    fault("authoritative_delegation_state", "REJECT", "AUTHORITY_REVOKED", observed=state)
                elif state == "superseded":
                    fault("authoritative_delegation_state", "REVALIDATE", "AUTHORITY_SUPERSEDED")
                else:
                    passed("authoritative_delegation_state")
                if authoritative_grant.get("scope_digest") != action.get("scope_digest"):
                    fault(
                        "authoritative_delegation_scope",
                        "REJECT",
                        "AUTHORITY_SCOPE_MISMATCH",
                        observed=action.get("scope_digest"),
                        expected=authoritative_grant.get("scope_digest"),
                    )
                else:
                    passed("authoritative_delegation_scope")
    else:
        passed("delegation_not_required")

    boundary_digest = action.get("boundary_rule_digest")
    if boundary_digest:
        recovered_boundaries = {
            item.get("rule_digest")
            for item in orientation.get("boundaries", [])
            if item.get("state") == "active"
        }
        authoritative_boundaries = set(authoritative.get("active_boundary_rule_digests", []))
        if boundary_digest not in recovered_boundaries:
            fault(
                "boundary_compatibility",
                "REJECT",
                "RELATIONAL_BOUNDARY_VIOLATION",
                observed=boundary_digest,
            )
        elif boundary_digest not in authoritative_boundaries:
            fault(
                "boundary_freshness",
                "REVALIDATE",
                "BOUNDARY_CHANGED",
                observed=boundary_digest,
            )
        else:
            passed("boundary_compatibility")
    else:
        passed("boundary_not_applicable")

    effect_key = action.get("relational_effect_key")
    recovered_completed = set(
        orientation.get("completed_history", {}).get("completed_relational_effect_keys", [])
    )
    authoritative_completed = set(authoritative.get("completed_relational_effect_keys", []))
    if effect_key and effect_key in recovered_completed.union(authoritative_completed):
        fault(
            "relational_effect_replay",
            "REJECT",
            "RELATIONAL_EFFECT_ALREADY_COMPLETED",
            relational_effect_key=effect_key,
        )
    else:
        passed("relational_effect_replay")

    if shared["shared_intent_digest"] != authoritative.get("current_shared_intent_digest"):
        fault(
            "shared_intent",
            "REVALIDATE",
            "SHARED_INTENT_DRIFT",
            observed=shared["shared_intent_digest"],
            expected=authoritative.get("current_shared_intent_digest"),
        )
    else:
        passed("shared_intent")

    if shared["shared_target_state_digest"] != authoritative.get("current_shared_target_state_digest"):
        fault(
            "shared_target_state",
            "REVALIDATE",
            "SHARED_TARGET_STATE_DRIFT",
            observed=shared["shared_target_state_digest"],
            expected=authoritative.get("current_shared_target_state_digest"),
        )
    else:
        passed("shared_target_state")

    recovered_trust = orientation.get("trust", {}).get("state")
    authoritative_trust = authoritative.get("trust_state")
    if recovered_trust == "revoked" or authoritative_trust == "revoked":
        fault("trust_state", "REJECT", "TRUST_REVOKED", observed=authoritative_trust)
    elif recovered_trust == "disputed" or authoritative_trust == "disputed":
        fault("trust_state", "REVALIDATE", "TRUST_DISPUTED", observed=authoritative_trust)
    else:
        passed("trust_state")

    recovered_open = {
        item.get("commitment_id")
        for item in orientation.get("commitments", [])
        if item.get("state") in {"open", "disputed"}
    }
    authoritative_open = set(authoritative.get("open_commitment_ids", []))
    if action.get("requires_no_open_commitments", False) and recovered_open.union(authoritative_open):
        fault(
            "commitment_precondition",
            "ABSTAIN",
            "UNRESOLVED_COMMITMENT_PRECONDITION",
            open_commitment_ids=sorted(recovered_open.union(authoritative_open)),
        )
    else:
        passed("commitment_precondition")

    if action.get("requires_accepted_handoff", False):
        recovered_handoff = orientation.get("handoff", {}).get("state")
        authoritative_handoff = authoritative.get("handoff_state")
        if recovered_handoff != "accepted" or authoritative_handoff != "accepted":
            fault(
                "handoff",
                "ABSTAIN",
                "INCOMPLETE_HANDOFF",
                recovered=recovered_handoff,
                authoritative=authoritative_handoff,
            )
        else:
            passed("handoff")
    else:
        passed("handoff_not_required")

    verdict, reason_code = _choose_fault(faults)
    return _result(fixture_id, verdict, reason_code, checks)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Fixture JSON file or suite containing a cases array")
    parser.add_argument("--check-expected", action="store_true", help="Exit non-zero when expected output differs")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    cases = payload.get("cases", [payload])
    results = []
    failures = []

    for case in cases:
        result = evaluate(case)
        results.append(result)
        expected = case.get("expected", {})
        if args.check_expected and (
            result["verdict"] != expected.get("verdict")
            or result["reason_code"] != expected.get("reason_code")
        ):
            failures.append({
                "fixture_id": case.get("fixture_id"),
                "expected": expected,
                "actual": {
                    "verdict": result["verdict"],
                    "reason_code": result["reason_code"],
                },
            })

    print(json.dumps({"results": results, "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
