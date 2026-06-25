#!/usr/bin/env python3
"""Validate the LS Identity Dashboard review-action contract using stdlib only."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "identity_review_action.schema.json"
EXAMPLE_PATH = ROOT / "schemas" / "identity_review_action.example.json"
OUTPUT_PATH = ROOT / "artifacts" / "identity-review-surface-validation.json"

DIGEST_RE = re.compile(r"^sha256:[a-f0-9]{64}$")
ACTIONS = {
    "approve",
    "reject",
    "rollback",
    "quarantine",
    "request_more_evidence",
    "supersede",
    "annotate",
}
GOVERNANCE_ACTIONS = {
    "approve",
    "reject",
    "quarantine",
    "request_more_evidence",
    "supersede",
}
EVIDENCE_FIELDS = (
    "supporting_refs",
    "failure_refs",
    "contradicting_refs",
    "counterevidence_refs",
    "superseded_refs",
)
FALSE_AUTHORITY_FIELDS = (
    "identity_update_approved",
    "identity_patch_created",
    "identity_update_applied",
    "stable_identity_mutated",
    "execution_authorized",
    "policy_bypass_granted",
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def _is_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _unique_string_list(value: Any, *, non_empty: bool = False) -> bool:
    if not isinstance(value, list):
        return False
    if non_empty and not value:
        return False
    if any(not isinstance(item, str) or not item for item in value):
        return False
    return len(value) == len(set(value))


def _record(checks: dict[str, bool], name: str, value: bool) -> None:
    checks[name] = bool(value)


def validate(action: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    required = {
        "schema_version",
        "action_id",
        "created_at",
        "idempotency_key",
        "actor",
        "snapshot_binding",
        "target",
        "action",
        "reason",
        "provenance_refs",
        "evidence_considered",
        "review_context",
        "rollback_request",
        "supersession_request",
        "authority_effects",
        "ui_context",
    }
    _record(checks, "required_top_level_fields", required.issubset(action))
    _record(checks, "schema_version", action.get("schema_version") == "identity_review_action.v0.1")
    _record(checks, "action_id_present", isinstance(action.get("action_id"), str) and bool(action["action_id"]))
    _record(checks, "created_at_valid", _is_datetime(action.get("created_at")))

    actor = action.get("actor", {})
    _record(
        checks,
        "actor_authenticated",
        isinstance(actor, dict)
        and bool(actor.get("actor_id"))
        and actor.get("actor_type") in {"human", "reviewing_agent"}
        and actor.get("role")
        in {
            "identity_reviewer",
            "relationship_reviewer",
            "system_governance_reviewer",
            "auditor",
        }
        and bool(actor.get("authenticated_session_ref")),
    )

    snapshot = action.get("snapshot_binding", {})
    target = action.get("target", {})
    snapshot_digest = snapshot.get("snapshot_digest")
    target_digest = target.get("target_digest")
    _record(checks, "snapshot_digest_valid", isinstance(snapshot_digest, str) and bool(DIGEST_RE.fullmatch(snapshot_digest)))
    _record(checks, "target_digest_valid", isinstance(target_digest, str) and bool(DIGEST_RE.fullmatch(target_digest)))
    _record(
        checks,
        "snapshot_times_valid",
        _is_datetime(snapshot.get("snapshot_time")) and _is_datetime(snapshot.get("reconstruction_as_of")),
    )
    _record(
        checks,
        "snapshot_ui_binding",
        bool(snapshot.get("snapshot_id"))
        and snapshot.get("snapshot_id") == action.get("ui_context", {}).get("selected_snapshot_id"),
    )

    scope = target.get("scope", {})
    scope_level = scope.get("continuity_level")
    scope_valid = (
        isinstance(scope, dict)
        and scope_level in {"individual", "relational", "shared_memory", "system"}
        and bool(scope.get("actor_ref"))
        and bool(scope.get("target_scope"))
    )
    if scope_level == "relational":
        scope_valid = scope_valid and bool(scope.get("relationship_ref"))
    _record(checks, "target_scope_valid", scope_valid)
    _record(
        checks,
        "target_display_binding",
        bool(target.get("target_ref"))
        and bool(target.get("display_binding", {}).get("snapshot_section")),
    )

    action_name = action.get("action")
    review = action.get("review_context", {})
    rollback = action.get("rollback_request")
    supersession = action.get("supersession_request")
    _record(checks, "action_allowed", action_name in ACTIONS)
    _record(checks, "fresh_revalidation_required", review.get("requires_fresh_revalidation") is True)

    if action_name == "annotate":
        action_semantics = (
            review.get("expected_handoff") == "RECORDED_ONLY"
            and rollback is None
            and supersession is None
        )
    elif action_name == "rollback":
        action_semantics = (
            review.get("expected_handoff") == "ROUTE_TO_ROLLBACK_GOVERNANCE"
            and target.get("target_kind") in {"identity_update_record", "identity_application"}
            and target.get("observed_state") == "active"
            and isinstance(rollback, dict)
            and bool(rollback.get("target_application_ref"))
            and bool(rollback.get("rollback_plan_ref"))
            and rollback.get("expected_new_state") == "rollback_pending"
            and supersession is None
        )
    elif action_name == "supersede":
        action_semantics = (
            review.get("expected_handoff") == "ROUTE_TO_GOVERNANCE"
            and isinstance(supersession, dict)
            and bool(supersession.get("superseding_target_ref"))
            and isinstance(supersession.get("superseding_target_digest"), str)
            and bool(DIGEST_RE.fullmatch(supersession["superseding_target_digest"]))
            and rollback is None
        )
    elif action_name in GOVERNANCE_ACTIONS:
        action_semantics = (
            review.get("expected_handoff") == "ROUTE_TO_GOVERNANCE"
            and target.get("target_kind") == "identity_proposal_candidate"
            and rollback is None
            and supersession is None
        )
    else:
        action_semantics = False
    _record(checks, "action_specific_semantics", action_semantics)

    reason = action.get("reason", {})
    _record(
        checks,
        "structured_reason",
        isinstance(reason, dict)
        and isinstance(reason.get("code"), str)
        and bool(reason.get("code"))
        and isinstance(reason.get("text"), str)
        and len(reason.get("text", "")) >= 8,
    )

    provenance = action.get("provenance_refs")
    _record(checks, "provenance_present", _unique_string_list(provenance, non_empty=True))

    evidence = action.get("evidence_considered", {})
    evidence_lists_valid = isinstance(evidence, dict) and all(
        _unique_string_list(evidence.get(field)) for field in EVIDENCE_FIELDS
    )
    _record(checks, "evidence_lists_valid", evidence_lists_valid)
    if evidence_lists_valid:
        support = set(evidence["supporting_refs"])
        failure = set(evidence["failure_refs"])
        contradiction = set(evidence["contradicting_refs"])
        counter = set(evidence["counterevidence_refs"])
        superseded_refs = set(evidence["superseded_refs"])
        evidence_roles_valid = (
            counter.issubset(contradiction)
            and not support.intersection(failure)
            and not support.intersection(counter)
            and not support.intersection(superseded_refs)
        )
    else:
        evidence_roles_valid = False
    _record(checks, "evidence_roles_preserved", evidence_roles_valid)

    authority = action.get("authority_effects", {})
    authority_valid = isinstance(authority, dict) and all(
        authority.get(field) is False for field in FALSE_AUTHORITY_FIELDS
    ) and authority.get("downstream_governance_required") is True
    _record(checks, "no_direct_authority", authority_valid)

    idempotency = action.get("idempotency_key")
    _record(
        checks,
        "idempotency_bound",
        isinstance(idempotency, str)
        and len(idempotency) >= 16
        and str(snapshot.get("snapshot_id")) in idempotency
        and str(target.get("target_ref")) in idempotency,
    )

    forbidden_top_level = {
        "approval_state",
        "identity_profile_patch",
        "identity_application",
        "applied",
        "active_profile",
    }
    _record(checks, "no_embedded_mutation_state", not forbidden_top_level.intersection(action))

    return checks


def main() -> int:
    schema = _load(SCHEMA_PATH)
    example = _load(EXAMPLE_PATH)
    checks = validate(example)
    report = {
        "profile": "identity-review-surface-v0.1",
        "schema_id": schema.get("$id"),
        "example_action_id": example.get("action_id"),
        "checks": checks,
        "passed": all(checks.values()),
        "boundary": (
            "Dashboard actions are audited review intent only; they do not approve, "
            "patch, apply, activate, or authorize identity directly."
        ),
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
