#!/usr/bin/env python3
"""Verify the RAMR v0.3.0 canonical fixture suite and LS verdicts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "operational-continuity" / "shared-envelope"
OUTPUT_PATH = ROOT / "artifacts" / "ramr-ls-fixture-suite-result.json"

CANONICAL_REPOSITORY = "DanceNitra/ramr"
CANONICAL_COMMIT = "35de7d3a1641e3ba9401aa2d1ea50171cd5cc86d"
ENVELOPE_VERSION = "ramr-ls-evidence-v0.1"
OUTCOMES = {"RESUME", "REVALIDATE", "REJECT", "ABSTAIN"}

FIXTURES = {
    "duplicate_successful_outcome": {
        "sha256": "bb28e8a390f0cae50f49b5befa0b903b8459aeaa0edc7dc199113f75dabf48ce",
        "ramr_key": "ramr_recovered_side_effect",
    },
    "superseded_approval": {
        "sha256": "ecd3cb375b8a6ea0abf0ec4594d666a1f65c135010af3274b67227ff9209ac2e",
        "ramr_key": "ramr_recovered_current_approval",
    },
    "incomplete_dependency_chain": {
        "sha256": "092edf5a3ff589366fcd894d62369cb07efff96222c83d88d6d85933d421e60a",
        "ramr_key": "ramr_full_chain_recovered",
    },
    "target_state_drift": {
        "sha256": "e920c0c7790733404d3e1d46d8977238a7489b6d1071b0f27cbc3b63e60dedee",
        "ramr_key": "ramr_target_current",
    },
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _read_pin(path: Path, expected_filename: str) -> str:
    parts = path.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2:
        raise ValueError(f"Malformed digest pin: {path}")
    token, filename = parts
    digest = token.removeprefix("sha256:")
    if filename != expected_filename:
        raise ValueError(f"Digest pin targets {filename}, expected {expected_filename}")
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError(f"Digest pin is not lowercase SHA-256: {path}")
    return digest


def _evidence(case: dict[str, Any]) -> list[dict[str, Any]]:
    return list(case.get("recovered_evidence", []))


def _score_duplicate(fixture: dict[str, Any], case: dict[str, Any]) -> bool:
    ledger = fixture["authoritative_state"]["completion_ledger"][0]
    context = fixture["query_context"]
    fields = (
        "side_effect_key",
        "continuation_id",
        "intent_digest",
        "target_state_digest",
        "approval_id",
    )
    for item in _evidence(case):
        bindings = item.get("bindings", {})
        if item.get("evidence_type") != "completion_record":
            continue
        if item.get("scope", {}).get("workspace_id") != context["workspace_id"]:
            continue
        if all(bindings.get(field) == ledger.get(field) for field in fields):
            return True
    return False


def _verdict_duplicate(fixture: dict[str, Any], case: dict[str, Any]) -> str:
    del case
    ledger = fixture["authoritative_state"].get("completion_ledger", [])
    return "REJECT" if any(item.get("status") == "completed" for item in ledger) else "ABSTAIN"


def _score_superseded(fixture: dict[str, Any], case: dict[str, Any]) -> bool:
    del fixture
    return any(
        item.get("evidence_type") == "approval_record"
        and item.get("invalidated_at") is not None
        for item in _evidence(case)
    )


def _verdict_superseded(fixture: dict[str, Any], case: dict[str, Any]) -> str:
    del case
    acting_id = fixture["query_context"].get("_acting_under_approval")
    for record in fixture["authoritative_state"].get("approval_ledger", []):
        if record.get("approval_id") == acting_id and record.get("status") == "superseded":
            return "REJECT"
    return "ABSTAIN"


def _score_chain(fixture: dict[str, Any], case: dict[str, Any]) -> bool:
    required = set(fixture["authoritative_state"]["required_chain"])
    recovered = {
        item.get("bindings", {}).get("chain_role")
        for item in _evidence(case)
    }
    return required.issubset(recovered)


def _verdict_chain(fixture: dict[str, Any], case: dict[str, Any]) -> str:
    return "RESUME" if _score_chain(fixture, case) else "ABSTAIN"


def _score_target(fixture: dict[str, Any], case: dict[str, Any]) -> bool:
    expected_target = fixture["query_context"]["target_state_digest"]
    evidence = _evidence(case)
    return bool(evidence) and all(
        item.get("bindings", {}).get("target_state_digest") == expected_target
        for item in evidence
    )


def _verdict_target(fixture: dict[str, Any], case: dict[str, Any]) -> str:
    return "RESUME" if _score_target(fixture, case) else "REVALIDATE"


SCORERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], bool]] = {
    "duplicate_successful_outcome": _score_duplicate,
    "superseded_approval": _score_superseded,
    "incomplete_dependency_chain": _score_chain,
    "target_state_drift": _score_target,
}

VERDICTS: dict[str, Callable[[dict[str, Any], dict[str, Any]], str]] = {
    "duplicate_successful_outcome": _verdict_duplicate,
    "superseded_approval": _verdict_superseded,
    "incomplete_dependency_chain": _verdict_chain,
    "target_state_drift": _verdict_target,
}


def _evaluate_fixture(fixture_id: str, config: dict[str, str]) -> dict[str, Any]:
    filename = f"{fixture_id}.json"
    fixture_path = FIXTURE_DIR / filename
    pin_path = FIXTURE_DIR / f"{fixture_id}.sha256"

    actual_digest = hashlib.sha256(fixture_path.read_bytes()).hexdigest()
    pinned_digest = _read_pin(pin_path, filename)
    expected_digest = config["sha256"]
    if actual_digest != pinned_digest or pinned_digest != expected_digest:
        raise ValueError(
            f"{fixture_id}: digest mismatch "
            f"(actual={actual_digest}, pin={pinned_digest}, expected={expected_digest})"
        )

    fixture = _load_json(fixture_path)
    if fixture.get("fixture_id") != fixture_id:
        raise ValueError(f"{fixture_id}: fixture_id mismatch")
    if fixture.get("envelope_version") != ENVELOPE_VERSION:
        raise ValueError(f"{fixture_id}: unsupported envelope version")

    metric_key = config["ramr_key"]
    results = []
    for case in fixture.get("cases", []):
        expected = case["expected"]
        observed_metric = SCORERS[fixture_id](fixture, case)
        observed_verdict = VERDICTS[fixture_id](fixture, case)
        if observed_verdict not in OUTCOMES:
            raise ValueError(f"{fixture_id}: invalid verdict {observed_verdict}")
        results.append(
            {
                "case": case["case"],
                "observed": {
                    metric_key: observed_metric,
                    "ls_verdict": observed_verdict,
                },
                "expected": {
                    metric_key: expected[metric_key],
                    "ls_verdict": expected["ls_verdict"],
                },
                "passed": (
                    observed_metric == expected[metric_key]
                    and observed_verdict == expected["ls_verdict"]
                ),
            }
        )

    return {
        "fixture_id": fixture_id,
        "canonical_path": f"fixtures/ramr_ls/{filename}",
        "sha256": actual_digest,
        "boundary_invariant": fixture["scoring"]["boundary_invariant"],
        "cases": results,
        "passed": all(item["passed"] for item in results),
    }


def main() -> int:
    fixtures = [
        _evaluate_fixture(fixture_id, config)
        for fixture_id, config in FIXTURES.items()
    ]
    verdicts = sorted(
        {
            case["observed"]["ls_verdict"]
            for fixture in fixtures
            for case in fixture["cases"]
        }
    )
    report = {
        "profile": "ls-ramr-operational-continuity-interop-v0.3.0",
        "canonical_source": {
            "repository": CANONICAL_REPOSITORY,
            "commit": CANONICAL_COMMIT,
        },
        "envelope_version": ENVELOPE_VERSION,
        "resume_semantics": (
            "RESUME means the tested continuation invariant passed; "
            "it is not global execution authorization."
        ),
        "fixtures": fixtures,
        "verdicts_covered": verdicts,
        "passed": (
            all(fixture["passed"] for fixture in fixtures)
            and set(verdicts) == OUTCOMES
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
