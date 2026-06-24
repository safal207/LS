#!/usr/bin/env python3
"""Dependency-free semantic validator for RAMR-LS evidence envelope v0.2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

HALF_LIVES = {
    "test": 180,
    "bug_fix": 365,
    "user_correction": 730,
    "source_code": 365,
    "session": 14,
}
PROVENANCE_FIELDS = {
    "asserted_by",
    "confirmer",
    "confirmation_state",
    "evidence_type",
    "last_decay_at",
    "half_life_days",
}
BINDING_FIELDS = {
    "workspace_id",
    "trajectory_id",
    "continuation_id",
    "intent_digest",
    "target_state_digest",
}


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level value must be an object")
    return value


def require(errors: list[str], condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def validate_provenance(
    errors: list[str],
    value: Any,
    location: str,
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{location}: provenance must be an object")
        return

    missing = PROVENANCE_FIELDS - value.keys()
    require(errors, not missing, f"{location}: missing {sorted(missing)}")

    evidence_type = value.get("evidence_type")
    require(
        errors,
        evidence_type in HALF_LIVES,
        f"{location}: unsupported evidence_type {evidence_type!r}",
    )
    if evidence_type in HALF_LIVES:
        require(
            errors,
            value.get("half_life_days") == HALF_LIVES[evidence_type],
            f"{location}: incorrect half_life_days for {evidence_type}",
        )
    require(
        errors,
        value.get("confirmation_state") == "confirmed",
        f"{location}: confirmation_state must be confirmed",
    )


def validate(
    fixture: dict[str, Any],
    schema: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []

    require(
        errors,
        schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
        "schema: expected Draft 2020-12",
    )
    properties = schema.get("properties", {})
    require(
        errors,
        properties.get("fixture_id", {}).get("const") == "resumed_constraint_defer",
        "schema: unexpected fixture_id const",
    )
    require(
        errors,
        properties.get("envelope_version", {}).get("const")
        == "ramr-ls-evidence-v0.2",
        "schema: unexpected envelope_version const",
    )

    require(
        errors,
        fixture.get("fixture_id") == "resumed_constraint_defer",
        "fixture: unexpected fixture_id",
    )
    require(
        errors,
        fixture.get("envelope_version") == "ramr-ls-evidence-v0.2",
        "fixture: unexpected envelope_version",
    )
    require(
        errors,
        fixture.get("_meta", {}).get("previous_envelope_version")
        == "ramr-ls-evidence-v0.1",
        "fixture: v0.1 lineage must remain explicit",
    )

    trajectory = fixture.get("trajectory", {})
    query = fixture.get("query_context", {})
    trajectory_id = trajectory.get("trajectory_id")
    continuation_id = query.get("continuation_id")
    resumed_from = query.get("resumed_from_continuation_id")

    require(errors, trajectory.get("arm") == "treatment", "fixture: arm must be treatment")
    require(
        errors,
        query.get("trajectory_id") == trajectory_id,
        "fixture: trajectory_id mismatch",
    )
    require(errors, bool(continuation_id), "fixture: continuation_id is required")
    require(
        errors,
        bool(resumed_from) and resumed_from != continuation_id,
        "fixture: resumed continuation must differ from predecessor",
    )
    require(errors, query.get("execution_phase") == "resumed", "fixture: phase must be resumed")
    require(
        errors,
        query.get("tool_event", {}).get("hook") == "PreToolUse",
        "fixture: hook must be PreToolUse",
    )

    constraints = fixture.get("authoritative_state", {}).get("learned_constraints", [])
    require(errors, bool(constraints), "fixture: learned constraint is required")
    authoritative: dict[str, dict[str, Any]] = {}
    for index, constraint in enumerate(constraints):
        location = f"learned_constraints[{index}]"
        if not isinstance(constraint, dict):
            errors.append(f"{location}: must be an object")
            continue
        constraint_id = constraint.get("constraint_id")
        require(errors, bool(constraint_id), f"{location}: constraint_id is required")
        if constraint_id:
            authoritative[str(constraint_id)] = constraint
        require(
            errors,
            constraint.get("trajectory_id") == trajectory_id,
            f"{location}: trajectory_id mismatch",
        )
        require(errors, constraint.get("status") == "active", f"{location}: must be active")
        validate_provenance(errors, constraint.get("provenance"), location)

    cases = fixture.get("cases", [])
    case_names = {case.get("case") for case in cases if isinstance(case, dict)}
    require(
        errors,
        case_names
        == {
            "valid_constraint_strong_retrieval",
            "valid_constraint_weak_retrieval",
        },
        "fixture: strong and weak retrieval cases are required exactly once",
    )

    signals: dict[str, float] = {}
    decisions: set[str] = set()
    for index, case in enumerate(cases):
        location = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{location}: must be an object")
            continue

        case_name = str(case.get("case"))
        signal = case.get("retrieval", {}).get("reliability_signal")
        require(
            errors,
            isinstance(signal, (int, float)) and 0 <= signal <= 1,
            f"{location}: invalid reliability_signal",
        )
        if isinstance(signal, (int, float)):
            signals[case_name] = float(signal)

        evidence_items = case.get("recovered_evidence", [])
        require(errors, bool(evidence_items), f"{location}: evidence is required")
        for evidence_index, evidence in enumerate(evidence_items):
            ev_location = f"{location}.recovered_evidence[{evidence_index}]"
            if not isinstance(evidence, dict):
                errors.append(f"{ev_location}: must be an object")
                continue

            constraint = authoritative.get(str(evidence.get("constraint_id")))
            require(errors, constraint is not None, f"{ev_location}: unknown constraint")
            if constraint is not None:
                require(
                    errors,
                    evidence.get("statement_digest") == constraint.get("statement_digest"),
                    f"{ev_location}: statement_digest mismatch",
                )

            bindings = evidence.get("bindings", {})
            missing = BINDING_FIELDS - bindings.keys() if isinstance(bindings, dict) else BINDING_FIELDS
            require(errors, not missing, f"{ev_location}: missing bindings {sorted(missing)}")
            if isinstance(bindings, dict):
                for field in BINDING_FIELDS:
                    require(
                        errors,
                        bindings.get(field) == query.get(field),
                        f"{ev_location}: {field} mismatch",
                    )
            validate_provenance(errors, evidence.get("provenance"), ev_location)

        expected = case.get("expected", {})
        for field in (
            "knowledge_recovered",
            "valid_for_trajectory",
            "valid_for_continuation",
            "constraint_fired",
        ):
            require(errors, expected.get(field) is True, f"{location}: {field} must be true")
        decision = expected.get("enforcement_decision")
        if isinstance(decision, str):
            decisions.add(decision)
        require(errors, decision == "DEFER", f"{location}: decision must be DEFER")
        require(
            errors,
            expected.get("execution_authorized") is False,
            f"{location}: execution must not be authorized",
        )

    strong = signals.get("valid_constraint_strong_retrieval")
    weak = signals.get("valid_constraint_weak_retrieval")
    require(
        errors,
        strong is not None and weak is not None and strong > weak,
        "fixture: strong reliability must exceed weak reliability",
    )
    require(errors, decisions == {"DEFER"}, "fixture: DEFER must be confidence-invariant")

    return {
        "fixture_id": fixture.get("fixture_id"),
        "envelope_version": fixture.get("envelope_version"),
        "passed": not errors,
        "errors": errors,
        "observed": {
            "trajectory_id": trajectory_id,
            "continuation_id": continuation_id,
            "resumed_from_continuation_id": resumed_from,
            "reliability_signals": signals,
            "enforcement_decisions": sorted(decisions),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture", type=Path)
    parser.add_argument("schema", type=Path)
    args = parser.parse_args()

    result = validate(load_object(args.fixture), load_object(args.schema))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
