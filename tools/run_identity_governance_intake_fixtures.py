#!/usr/bin/env python3
"""Verify frozen IdentityProposalCandidate governance-intake fixtures."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "identity-governance-intake"
OUTPUT_PATH = ROOT / "artifacts" / "identity-governance-intake-conformance-result.json"

ENVELOPE_VERSION = "ls-identity-governance-intake-v0.1"
OUTCOMES = {
    "ACCEPT_FOR_REVIEW",
    "REQUEST_MORE_EVIDENCE",
    "REJECT",
    "QUARANTINE",
    "EXPIRE",
    "SUPERSEDE",
}
FROZEN_FIXTURES = {
    "ready_candidate": "5d697b7755c3f535dd3b0601666964d15a133825ce84df23d75bfbf169bc49fe",
    "insufficient_evidence": "fc2d0ddd94a2b69e7371dc63998660785b31ce8b523f28b65e6ccd20ec61c3f5",
    "omitted_counterevidence": "b881e5af686968b74eb49ac3752f855ddd4624e2e282da315e10ed46250b98a9",
    "scope_inflation": "816a818cbbb7f51f7f14df491ffe9607562e4624b8a1e7ceba55bc5317b0e73b",
    "expired_candidate": "fcedc115a69027a73c848569b6aa1d48aba5797d1390fd99d2d61453f631ccc0",
    "superseded_candidate": "51f15244a132b2dc5bcfbedd1190215c14d2f721fea163719038cb6743201d5c",
    "self_approval_attempt": "01bc348d77ffaa1ddee5964ff24be2a5a3b90079a8705e904e08498ecca6989c"
}
REQUIRED_ADAPTER_FIELDS = [
    "candidate_ref",
    "candidate_digest",
    "source_aggregation_ref",
    "source_aggregation_digest",
    "track_identity",
    "supporting_episode_refs",
    "failure_episode_refs",
    "contradicting_episode_refs",
    "counterevidence_episode_refs",
    "superseded_episode_refs",
    "confidence_snapshot_ref",
    "evidence_quality_summary",
    "proposed_identity_influence",
    "governance_reason",
    "expires_at",
    "revalidate_if",
    "rollback_plan_ref",
    "authority_effects"
]
LEVEL_RANK = {"individual": 0, "relational": 1, "system": 2}
BOUNDARY_FLAGS = {
    "identity_update_approved": False,
    "identity_patch_created": False,
    "identity_update_applied": False,
    "stable_identity_mutated": False,
    "execution_authorized": False,
    "downstream_governance_required": True
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _candidate_material(candidate: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in candidate.items() if key != "candidate_digest"}


def _read_pin(path: Path, expected_filename: str) -> str:
    parts = path.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2:
        raise ValueError(f"Malformed digest pin: {path}")
    digest, filename = parts
    digest = digest.removeprefix("sha256:")
    if filename != expected_filename:
        raise ValueError(f"Digest pin targets {filename}, expected {expected_filename}")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"Digest pin is not lowercase SHA-256: {path}")
    return digest


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _refs_unique(candidate: dict[str, Any]) -> bool:
    fields = (
        "supporting_episode_refs",
        "failure_episode_refs",
        "contradicting_episode_refs",
        "counterevidence_episode_refs",
        "superseded_episode_refs",
    )
    lists = [candidate.get(field, []) for field in fields]
    if any(not isinstance(items, list) or len(items) != len(set(items)) for items in lists):
        return False
    support, failure, contradiction, counter, superseded = map(set, lists)
    return (
        not support.intersection(failure)
        and not support.intersection(counter)
        and not support.intersection(superseded)
        and counter.issubset(contradiction)
    )


def _observed_checks(fixture: dict[str, Any]) -> dict[str, bool]:
    source = fixture["source_aggregation"]
    candidate = fixture["candidate"]
    governance = candidate["governance"]
    lifecycle = candidate["lifecycle"]
    runtime = candidate["runtime_state"]

    source_binding_valid = (
        candidate.get("source_aggregation_record_ref") == source.get("aggregation_id")
        and candidate.get("source_aggregation_digest") == _canonical_digest(source)
    )
    candidate_digest_valid = (
        candidate.get("candidate_digest") == _canonical_digest(_candidate_material(candidate))
    )

    source_refs = set(
        source.get("supporting_episode_refs", [])
        + source.get("failure_episode_refs", [])
        + source.get("contradicting_episode_refs", [])
        + source.get("counterevidence_episode_refs", [])
        + source.get("superseded_episode_refs", [])
    )
    not_single_episode = len(source_refs) > 1

    evidence_fields = (
        "supporting_episode_refs",
        "failure_episode_refs",
        "contradicting_episode_refs",
        "counterevidence_episode_refs",
        "superseded_episode_refs",
    )
    evidence_preserved = all(
        set(candidate.get(field, [])) == set(source.get(field, []))
        for field in evidence_fields
    )
    counterevidence_preserved = (
        set(candidate.get("contradicting_episode_refs", []))
        == set(source.get("contradicting_episode_refs", []))
        and set(candidate.get("counterevidence_episode_refs", []))
        == set(source.get("counterevidence_episode_refs", []))
    )
    evidence_refs_unique = _refs_unique(candidate)
    evidence_summary_bound = (
        candidate.get("confidence_snapshot_ref") == source.get("confidence_snapshot_ref")
        and candidate.get("evidence_quality_summary") == source.get("evidence_quality_summary")
    )

    source_level = source.get("continuity_level")
    candidate_level = candidate.get("track_identity", {}).get("continuity_level")
    influence_level = candidate.get("proposed_identity_influence", {}).get("scope")
    scope_preserved = (
        source_level in LEVEL_RANK
        and candidate_level in LEVEL_RANK
        and LEVEL_RANK[candidate_level] <= LEVEL_RANK[source_level]
        and influence_level == candidate_level
        and candidate.get("track_identity", {}).get("actor_ref") == source.get("actor_ref")
        and candidate.get("track_identity", {}).get("target_scope") == source.get("target_scope")
    )

    lifecycle_ready = (
        bool(lifecycle.get("rollback_plan_ref"))
        and isinstance(lifecycle.get("revalidate_if"), list)
        and bool(lifecycle.get("revalidate_if"))
    )
    self_approval_absent = (
        governance.get("reviewer_id") != candidate.get("created_by")
        and runtime.get("approval_state") != "APPROVED"
    )
    authority_clean = (
        isinstance(candidate.get("authority_effects"), dict)
        and bool(candidate.get("authority_effects"))
        and all(value is False for value in candidate["authority_effects"].values())
    )
    runtime_unapplied = (
        runtime.get("approval_state") == "PENDING"
        and runtime.get("identity_patch_ref") is None
        and runtime.get("application_ref") is None
        and runtime.get("active_profile") is False
    )
    adapter_preserves_required = set(REQUIRED_ADAPTER_FIELDS).issubset(
        set(candidate.get("adapter_preserved_fields", []))
    )

    expires_at = lifecycle.get("expires_at")
    expired = bool(expires_at) and _parse_time(fixture["as_of"]) >= _parse_time(expires_at)
    superseded = bool(lifecycle.get("superseded_by"))
    evidence_sufficient = (
        source.get("evidence_state") == "sufficient"
        and source.get("evidence_quality_summary", {}).get("trusted_supporting_count", 0) >= 2
    )
    candidate_state = governance.get("candidate_state")
    candidate_state_consistent = (
        (superseded and candidate_state == "SUPERSEDED")
        or (
            not superseded
            and not evidence_sufficient
            and candidate_state == "MORE_EVIDENCE_REQUIRED"
        )
        or (
            not superseded
            and evidence_sufficient
            and candidate_state == "READY_FOR_GOVERNANCE"
        )
    )
    governance_review_required = governance.get("governance_review_required") is True

    return {
        "source_binding_valid": source_binding_valid,
        "candidate_digest_valid": candidate_digest_valid,
        "not_single_episode": not_single_episode,
        "evidence_preserved": evidence_preserved,
        "counterevidence_preserved": counterevidence_preserved,
        "evidence_refs_unique": evidence_refs_unique,
        "evidence_summary_bound": evidence_summary_bound,
        "scope_preserved": scope_preserved,
        "lifecycle_ready": lifecycle_ready,
        "self_approval_absent": self_approval_absent,
        "authority_clean": authority_clean,
        "runtime_unapplied": runtime_unapplied,
        "adapter_preserves_required": adapter_preserves_required,
        "candidate_state_consistent": candidate_state_consistent,
        "governance_review_required": governance_review_required,
        "expired": expired,
        "superseded": superseded,
        "evidence_sufficient": evidence_sufficient,
    }


def _outcome(checks: dict[str, bool]) -> str:
    reject_checks = (
        "source_binding_valid",
        "candidate_digest_valid",
        "not_single_episode",
        "evidence_preserved",
        "counterevidence_preserved",
        "evidence_refs_unique",
        "evidence_summary_bound",
        "lifecycle_ready",
        "self_approval_absent",
        "authority_clean",
        "runtime_unapplied",
        "adapter_preserves_required",
        "candidate_state_consistent",
        "governance_review_required",
    )
    if not all(checks[name] for name in reject_checks):
        return "REJECT"
    if not checks["scope_preserved"]:
        return "QUARANTINE"
    if checks["superseded"]:
        return "SUPERSEDE"
    if checks["expired"]:
        return "EXPIRE"
    if not checks["evidence_sufficient"]:
        return "REQUEST_MORE_EVIDENCE"
    return "ACCEPT_FOR_REVIEW"


def _evaluate(fixture_id: str, frozen_digest: str) -> dict[str, Any]:
    filename = f"{fixture_id}.json"
    fixture_path = FIXTURE_DIR / filename
    actual_digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    pinned_digest = _read_pin(FIXTURE_DIR / f"{fixture_id}.sha256", filename)
    if actual_digest != pinned_digest or pinned_digest != frozen_digest:
        raise ValueError(
            f"{fixture_id}: digest mismatch "
            f"(actual={actual_digest}, pin={pinned_digest}, frozen={frozen_digest})"
        )

    fixture = _load_json(fixture_path)
    if fixture.get("fixture_id") != fixture_id:
        raise ValueError(f"{fixture_id}: fixture_id mismatch")
    if fixture.get("envelope_version") != ENVELOPE_VERSION:
        raise ValueError(f"{fixture_id}: unsupported envelope version")

    checks = _observed_checks(fixture)
    outcome = _outcome(checks)
    expected = fixture["expected"]["intake_outcome"]
    if outcome not in OUTCOMES:
        raise ValueError(f"{fixture_id}: invalid outcome {outcome}")

    boundary_flags = dict(BOUNDARY_FLAGS)
    boundary_flags["may_construct_review_only_identity_update_proposal"] = (
        outcome == "ACCEPT_FOR_REVIEW"
    )

    return {
        "fixture_id": fixture_id,
        "sha256": actual_digest,
        "candidate_digest": fixture["candidate"]["candidate_digest"],
        "boundary_invariant": fixture["scoring"]["boundary_invariant"],
        "observed": {
            "checks": checks,
            "intake_outcome": outcome,
            "boundary_flags": boundary_flags,
        },
        "expected": {"intake_outcome": expected},
        "passed": outcome == expected and boundary_flags["downstream_governance_required"],
    }


def main() -> int:
    fixtures = [
        _evaluate(fixture_id, digest)
        for fixture_id, digest in FROZEN_FIXTURES.items()
    ]
    outcomes = sorted({item["observed"]["intake_outcome"] for item in fixtures})
    report = {
        "profile": ENVELOPE_VERSION,
        "core_invariant": (
            "Experience may influence continuity, but only governed continuity "
            "may reposition the identity center."
        ),
        "accept_semantics": (
            "ACCEPT_FOR_REVIEW permits only independent review-only proposal construction; "
            "it is not approval, patch creation, application, stable identity mutation, "
            "or execution authorization."
        ),
        "fixtures": fixtures,
        "outcomes_covered": outcomes,
        "passed": (
            all(item["passed"] for item in fixtures)
            and set(outcomes) == OUTCOMES
        ),
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
