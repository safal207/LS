#!/usr/bin/env python3
"""Verify frozen LS write-time coherence fixtures and deterministic verdicts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "write-time-coherence"
OUTPUT_PATH = ROOT / "artifacts" / "write-time-coherence-conformance-result.json"

ENVELOPE_VERSION = "ls-write-time-coherence-v0.1"
OUTCOMES = {"RESUME", "REVALIDATE", "REJECT", "ABSTAIN"}
ALLOWED_CONFIRMATION_BASES = {
    "human_review",
    "deterministic_test",
    "external_anchor",
    "independent_agent",
}

FROZEN_FIXTURES = {
    "cross_session_contradiction": "5838ab283af50ae44fe738c4caaebac94bd19dc2c772b6902396c68f77567093",
    "synthesized_chain_with_provenance": "9518035df885cf9470d67b9c4c8ac16814538208bf2dcf2a64e0c7a254dc4e03",
    "lossy_synthesis": "2b93b7c7034b7d1ef72f71be7895e9a4a63949b82e6118b68af503de5b3da808",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
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


def _read_pin(path: Path, expected_filename: str) -> str:
    parts = path.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2:
        raise ValueError(f"Malformed digest pin: {path}")
    digest, filename = parts
    digest = digest.removeprefix("sha256:")
    if filename != expected_filename:
        raise ValueError(
            f"Digest pin targets {filename}, expected {expected_filename}"
        )
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"Digest pin is not lowercase SHA-256: {path}")
    return digest


def _source_map(fixture: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event in fixture.get("source_events", []):
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Every source event must have a non-empty event_id")
        if event_id in result:
            raise ValueError(f"Duplicate source event id: {event_id}")
        result[event_id] = event
    return result


def _source_integrity(
    fixture: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> bool:
    candidate = fixture["candidate"]
    referenced_ids = candidate.get("source_event_ids", [])
    digest_map = candidate.get("source_digests", {})
    if not isinstance(referenced_ids, list) or not isinstance(digest_map, dict):
        return False
    if len(referenced_ids) != len(set(referenced_ids)):
        return False
    if set(referenced_ids) != set(digest_map):
        return False

    for event_id in referenced_ids:
        event = sources.get(event_id)
        if event is None or event.get("immutable") is not True:
            return False
        if digest_map.get(event_id) != _canonical_digest(event):
            return False

    payload = candidate.get("synthesis_payload", {})
    for claim in payload.get("claims", []):
        supported_by = claim.get("supported_by", [])
        if not supported_by or not set(supported_by).issubset(set(referenced_ids)):
            return False
    return True


def _contradiction_state(fixture: dict[str, Any]) -> tuple[bool, bool]:
    relations = fixture.get("relations", [])
    candidate_refs = set(fixture["candidate"].get("contradiction_refs", []))
    material = [
        relation
        for relation in relations
        if relation.get("type") == "contradicts"
        and relation.get("material") is True
    ]
    visible = all(
        relation.get("relation_id") in candidate_refs
        for relation in material
    )
    unresolved = any(relation.get("resolved") is False for relation in material)
    return visible, unresolved


def _dependency_chain_complete(
    fixture: dict[str, Any],
    sources: dict[str, dict[str, Any]],
) -> bool:
    candidate = fixture["candidate"]
    required = set(fixture.get("required_dependency_roles", []))
    declared = set(candidate.get("dependency_roles", []))
    referenced = set(candidate.get("source_event_ids", []))
    evidenced = {
        event.get("bindings", {}).get("chain_role")
        for event_id, event in sources.items()
        if event_id in referenced
    }
    return required.issubset(declared) and required.issubset(evidenced)


def _bindings_current(fixture: dict[str, Any]) -> bool:
    expected = fixture.get("query_context", {})
    observed = fixture["candidate"].get("bindings", {})
    fields = (
        "trajectory_id",
        "continuation_id",
        "intent_digest",
        "target_state_digest",
    )
    return all(observed.get(field) == expected.get(field) for field in fields)


def _confirmer_independent(fixture: dict[str, Any]) -> bool:
    candidate = fixture["candidate"]
    confirmer = candidate.get("confirmer", {})
    return (
        isinstance(confirmer, dict)
        and bool(confirmer.get("id"))
        and confirmer.get("id") != candidate.get("asserted_by")
        and confirmer.get("basis") in ALLOWED_CONFIRMATION_BASES
    )


def _synthesis_digest_valid(fixture: dict[str, Any]) -> bool:
    candidate = fixture["candidate"]
    return candidate.get("synthesis_digest") == _canonical_digest(
        candidate.get("synthesis_payload", {})
    )


def _safety_defaults_preserved(fixture: dict[str, Any]) -> bool:
    candidate = fixture["candidate"]
    return (
        candidate.get("stable_identity_update_allowed") is False
        and candidate.get("execution_authorized") is False
        and candidate.get("downstream_gates_required") is True
    )


def _confirmation_verified(fixture: dict[str, Any]) -> bool:
    return fixture["candidate"].get("confirmation_state") == "verified"


def _observed_checks(fixture: dict[str, Any]) -> dict[str, bool]:
    sources = _source_map(fixture)
    contradiction_visible, unresolved = _contradiction_state(fixture)
    return {
        "source_integrity": _source_integrity(fixture, sources),
        "contradiction_visible": contradiction_visible,
        "unresolved_material_contradiction": unresolved,
        "dependency_chain_complete": _dependency_chain_complete(fixture, sources),
        "bindings_current": _bindings_current(fixture),
        "confirmer_independent": _confirmer_independent(fixture),
        "confirmation_verified": _confirmation_verified(fixture),
        "synthesis_digest_valid": _synthesis_digest_valid(fixture),
        "safety_defaults_preserved": _safety_defaults_preserved(fixture),
    }


def _verdict(checks: dict[str, bool]) -> str:
    if not checks["safety_defaults_preserved"]:
        return "REJECT"
    if not checks["bindings_current"]:
        return "REVALIDATE"
    if checks["unresolved_material_contradiction"]:
        return "ABSTAIN"

    required_for_resume = (
        "source_integrity",
        "contradiction_visible",
        "dependency_chain_complete",
        "confirmer_independent",
        "confirmation_verified",
        "synthesis_digest_valid",
    )
    if not all(checks[name] for name in required_for_resume):
        return "ABSTAIN"
    return "RESUME"


def _evaluate_fixture(fixture_id: str, frozen_digest: str) -> dict[str, Any]:
    filename = f"{fixture_id}.json"
    fixture_path = FIXTURE_DIR / filename
    pin_path = FIXTURE_DIR / f"{fixture_id}.sha256"

    actual_digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    pinned_digest = _read_pin(pin_path, filename)
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

    observed_checks = _observed_checks(fixture)
    expected_checks = fixture["expected"]["checks"]
    observed_verdict = _verdict(observed_checks)
    expected_verdict = fixture["expected"]["ls_verdict"]

    if observed_verdict not in OUTCOMES:
        raise ValueError(f"{fixture_id}: invalid verdict {observed_verdict}")

    return {
        "fixture_id": fixture_id,
        "sha256": actual_digest,
        "boundary_invariant": fixture["scoring"]["boundary_invariant"],
        "observed": {
            "checks": observed_checks,
            "ls_verdict": observed_verdict,
        },
        "expected": {
            "checks": expected_checks,
            "ls_verdict": expected_verdict,
        },
        "passed": (
            observed_checks == expected_checks
            and observed_verdict == expected_verdict
        ),
    }


def main() -> int:
    fixtures = [
        _evaluate_fixture(fixture_id, digest)
        for fixture_id, digest in FROZEN_FIXTURES.items()
    ]
    verdicts = sorted(
        {fixture["observed"]["ls_verdict"] for fixture in fixtures}
    )
    report = {
        "profile": "ls-write-time-coherence-v0.1",
        "envelope_version": ENVELOPE_VERSION,
        "continuity_rule": "Remember the influence. Never fabricate the presence.",
        "resume_semantics": (
            "RESUME means the write-time coherence invariant passed; "
            "it is not truth authority, stable identity mutation, "
            "or global execution authorization."
        ),
        "fixtures": fixtures,
        "verdicts_covered": verdicts,
        "passed": all(fixture["passed"] for fixture in fixtures),
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
