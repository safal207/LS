from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, MutableSet

PROFILE_ID = "vtl-tool-dispatch-v0.7"
SCHEMA_VERSION = "vtl.tool-dispatch-receipt/v0.7"
FIXTURE_SCHEMA_VERSION = "vtl.tool-dispatch-fixture/v0.7"


@dataclass(frozen=True)
class ActionEnvelope:
    runtime_surface: str
    transition_id: str
    occurrence_id: str
    action: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ActionGrantBinding:
    binding_id: str
    profile_id: str
    schema_version: str
    authorization_decision_id: str
    use_id: str
    transition_id: str
    proposal_digest: str
    action_id: str
    action_envelope_digest: str
    executor_id: str
    execution_nonce: str
    occurrence_id: str
    context_digest: str
    policy_ref: str | None
    bound_at_ms: int


@dataclass(frozen=True)
class ToolDispatchReceipt:
    receipt_id: str
    profile_id: str
    schema_version: str
    authorization_decision_id: str
    use_id: str
    grant_binding_id: str
    transition_id: str
    proposal_digest: str
    authorized_action_id: str
    dispatched_action_id: str
    action_envelope_digest: str
    executor_id: str
    execution_nonce: str
    occurrence_id: str
    context_digest: str
    policy_ref: str | None
    dispatch_ref: str
    observed_outcome_ref: str
    observed_outcome_digest: str
    dispatched_at_ms: int
    observed_at_ms: int


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    reason_codes: tuple[str, ...]


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{_digest(value)[:24]}"


def _pick(value: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: value.get(key) for key in keys}


def action_envelope_digest(envelope: Mapping[str, Any]) -> str:
    return _digest(dict(envelope))


def action_id(envelope: Mapping[str, Any]) -> str:
    return _stable_id("action", dict(envelope))


def observed_outcome_digest(outcome: Mapping[str, Any]) -> str:
    return _digest(dict(outcome))


_AUTH_KEYS = (
    "transition_id", "intent_id", "verdict", "reason_codes", "verifier_id",
    "executor_id", "proposal_digest", "evidence_digest", "source_ref",
    "policy_ref", "approval_ref", "approval_valid_until_ms",
)
_USE_KEYS = (
    "authorization_decision_id", "transition_id", "verdict", "reason_codes",
    "executor_id", "proposal_digest", "context_digest", "execution_nonce",
    "checked_at_ms",
)
_GRANT_KEYS = (
    "profile_id", "schema_version", "authorization_decision_id", "use_id",
    "transition_id", "proposal_digest", "action_id", "action_envelope_digest",
    "executor_id", "execution_nonce", "occurrence_id", "context_digest",
    "policy_ref", "bound_at_ms",
)
_DISPATCH_KEYS = (
    "profile_id", "schema_version", "authorization_decision_id", "use_id",
    "grant_binding_id", "transition_id", "proposal_digest",
    "authorized_action_id", "dispatched_action_id", "action_envelope_digest",
    "executor_id", "execution_nonce", "occurrence_id", "context_digest",
    "policy_ref", "dispatch_ref", "observed_outcome_ref",
    "observed_outcome_digest", "dispatched_at_ms", "observed_at_ms",
)


def verify_serialized_authorization_receipt(receipt: Mapping[str, Any]) -> bool:
    return receipt.get("decision_id") == _stable_id("auth", _pick(receipt, _AUTH_KEYS))


def verify_serialized_use_time_receipt(receipt: Mapping[str, Any]) -> bool:
    return receipt.get("use_id") == _stable_id("use", _pick(receipt, _USE_KEYS))


def compute_action_grant_binding_id(binding: Mapping[str, Any]) -> str:
    return _stable_id("grant", _pick(binding, _GRANT_KEYS))


def verify_action_grant_binding_integrity(binding: Mapping[str, Any]) -> bool:
    return binding.get("binding_id") == compute_action_grant_binding_id(binding)


def compute_dispatch_receipt_id(receipt: Mapping[str, Any]) -> str:
    return _stable_id("dispatch", _pick(receipt, _DISPATCH_KEYS))


def verify_dispatch_receipt_integrity(receipt: Mapping[str, Any]) -> bool:
    return receipt.get("receipt_id") == compute_dispatch_receipt_id(receipt)


def build_action_grant_binding(
    *,
    proposal: Mapping[str, Any],
    authorization: Mapping[str, Any],
    use_time: Mapping[str, Any],
    action_envelope: Mapping[str, Any],
    bound_at_ms: int,
) -> ActionGrantBinding:
    envelope = dict(action_envelope)
    payload = {
        "profile_id": PROFILE_ID,
        "schema_version": SCHEMA_VERSION,
        "authorization_decision_id": authorization["decision_id"],
        "use_id": use_time["use_id"],
        "transition_id": proposal["transition_id"],
        "proposal_digest": use_time["proposal_digest"],
        "action_id": action_id(envelope),
        "action_envelope_digest": action_envelope_digest(envelope),
        "executor_id": use_time["executor_id"],
        "execution_nonce": use_time["execution_nonce"],
        "occurrence_id": envelope["occurrence_id"],
        "context_digest": use_time["context_digest"],
        "policy_ref": authorization.get("policy_ref"),
        "bound_at_ms": bound_at_ms,
    }
    return ActionGrantBinding(binding_id=_stable_id("grant", payload), **payload)


def _mapping(value: Mapping[str, Any] | ActionGrantBinding) -> dict[str, Any]:
    return asdict(value) if isinstance(value, ActionGrantBinding) else dict(value)


def build_tool_dispatch_receipt(
    *,
    proposal: Mapping[str, Any],
    authorization: Mapping[str, Any],
    use_time: Mapping[str, Any],
    grant_binding: Mapping[str, Any] | ActionGrantBinding,
    action_envelope: Mapping[str, Any],
    observed_outcome: Mapping[str, Any],
    dispatch_ref: str,
    observed_outcome_ref: str,
    dispatched_at_ms: int,
    observed_at_ms: int,
    dispatched_action_id: str | None = None,
) -> ToolDispatchReceipt:
    envelope, binding = dict(action_envelope), _mapping(grant_binding)
    payload = {
        "profile_id": PROFILE_ID,
        "schema_version": SCHEMA_VERSION,
        "authorization_decision_id": authorization["decision_id"],
        "use_id": use_time["use_id"],
        "grant_binding_id": binding["binding_id"],
        "transition_id": proposal["transition_id"],
        "proposal_digest": use_time["proposal_digest"],
        "authorized_action_id": binding["action_id"],
        "dispatched_action_id": dispatched_action_id or action_id(envelope),
        "action_envelope_digest": action_envelope_digest(envelope),
        "executor_id": use_time["executor_id"],
        "execution_nonce": use_time["execution_nonce"],
        "occurrence_id": envelope["occurrence_id"],
        "context_digest": use_time["context_digest"],
        "policy_ref": authorization.get("policy_ref"),
        "dispatch_ref": dispatch_ref,
        "observed_outcome_ref": observed_outcome_ref,
        "observed_outcome_digest": observed_outcome_digest(observed_outcome),
        "dispatched_at_ms": dispatched_at_ms,
        "observed_at_ms": observed_at_ms,
    }
    return ToolDispatchReceipt(receipt_id=_stable_id("dispatch", payload), **payload)


def transcript_to_dict(
    *,
    proposal: Mapping[str, Any],
    authorization: Mapping[str, Any],
    use_time: Mapping[str, Any],
    action_envelope: Mapping[str, Any],
    grant_binding: Mapping[str, Any] | ActionGrantBinding,
    dispatch_receipt: Mapping[str, Any] | ToolDispatchReceipt,
    observed_outcome: Mapping[str, Any],
) -> dict[str, Any]:
    dispatch = (
        asdict(dispatch_receipt)
        if isinstance(dispatch_receipt, ToolDispatchReceipt)
        else dict(dispatch_receipt)
    )
    return {
        "profile_id": PROFILE_ID,
        "schema_version": SCHEMA_VERSION,
        "proposal": copy.deepcopy(dict(proposal)),
        "authorization": copy.deepcopy(dict(authorization)),
        "use_time": copy.deepcopy(dict(use_time)),
        "action_envelope": copy.deepcopy(dict(action_envelope)),
        "grant_binding": copy.deepcopy(_mapping(grant_binding)),
        "dispatch_receipt": copy.deepcopy(dispatch),
        "observed_outcome": copy.deepcopy(dict(observed_outcome)),
    }


def _add(reasons: list[str], reason: str, condition: bool) -> None:
    if condition and reason not in reasons:
        reasons.append(reason)


def verify_dispatch_transcript(
    transcript: Mapping[str, Any],
    *,
    seen_use_ids: MutableSet[str] | None = None,
) -> VerificationResult:
    reasons: list[str] = []
    _add(reasons, "PROFILE_ID_MISMATCH", transcript.get("profile_id") != PROFILE_ID)
    _add(
        reasons, "SCHEMA_VERSION_MISMATCH",
        transcript.get("schema_version") != SCHEMA_VERSION,
    )

    names = (
        "proposal", "authorization", "use_time", "action_envelope",
        "grant_binding", "dispatch_receipt", "observed_outcome",
    )
    for name in names:
        _add(
            reasons, f"SECTION_INVALID:{name}",
            not isinstance(transcript.get(name), Mapping),
        )
    if reasons:
        return VerificationResult(False, tuple(reasons))

    proposal = dict(transcript["proposal"])
    auth = dict(transcript["authorization"])
    use = dict(transcript["use_time"])
    envelope = dict(transcript["action_envelope"])
    grant = dict(transcript["grant_binding"])
    dispatch = dict(transcript["dispatch_receipt"])
    outcome = dict(transcript["observed_outcome"])

    _add(reasons, "AUTHORIZATION_RECEIPT_INVALID", not verify_serialized_authorization_receipt(auth))
    _add(reasons, "AUTHORIZATION_NOT_GRANTED", auth.get("verdict") != "AUTHORIZE")
    _add(reasons, "USE_TIME_RECEIPT_INVALID", not verify_serialized_use_time_receipt(use))
    _add(reasons, "USE_TIME_NOT_EXECUTABLE", use.get("verdict") != "EXECUTE")

    proposal_digest = _digest(proposal)
    _add(reasons, "AUTHORIZATION_PROPOSAL_DIGEST_MISMATCH", auth.get("proposal_digest") != proposal_digest)
    _add(reasons, "USE_TIME_PROPOSAL_DIGEST_MISMATCH", use.get("proposal_digest") != proposal_digest)
    transition_id = proposal.get("transition_id")
    _add(
        reasons, "TRANSITION_BINDING_MISMATCH",
        any(value != transition_id for value in (
            auth.get("transition_id"), use.get("transition_id"),
            envelope.get("transition_id"), grant.get("transition_id"),
            dispatch.get("transition_id"), outcome.get("transition_id"),
        )),
    )
    _add(reasons, "INTENT_BINDING_MISMATCH", auth.get("intent_id") != proposal.get("intent_id"))
    _add(reasons, "USE_AUTHORIZATION_BINDING_MISMATCH", use.get("authorization_decision_id") != auth.get("decision_id"))

    _add(reasons, "GRANT_PROFILE_ID_MISMATCH", grant.get("profile_id") != PROFILE_ID)
    _add(reasons, "GRANT_SCHEMA_VERSION_MISMATCH", grant.get("schema_version") != SCHEMA_VERSION)
    _add(reasons, "GRANT_BINDING_INVALID", not verify_action_grant_binding_integrity(grant))
    _add(reasons, "GRANT_AUTHORIZATION_BINDING_MISMATCH", grant.get("authorization_decision_id") != auth.get("decision_id"))
    _add(reasons, "GRANT_USE_BINDING_MISMATCH", grant.get("use_id") != use.get("use_id"))

    _add(reasons, "DISPATCH_PROFILE_ID_MISMATCH", dispatch.get("profile_id") != PROFILE_ID)
    _add(reasons, "DISPATCH_SCHEMA_VERSION_MISMATCH", dispatch.get("schema_version") != SCHEMA_VERSION)
    _add(reasons, "DISPATCH_RECEIPT_INVALID", not verify_dispatch_receipt_integrity(dispatch))
    _add(reasons, "DISPATCH_AUTHORIZATION_BINDING_MISMATCH", dispatch.get("authorization_decision_id") != auth.get("decision_id"))
    _add(reasons, "DISPATCH_USE_BINDING_MISMATCH", dispatch.get("use_id") != use.get("use_id"))
    _add(reasons, "DISPATCH_GRANT_BINDING_MISMATCH", dispatch.get("grant_binding_id") != grant.get("binding_id"))

    executor = auth.get("executor_id")
    _add(
        reasons, "EXECUTOR_BINDING_MISMATCH",
        any(value != executor for value in (
            use.get("executor_id"), grant.get("executor_id"), dispatch.get("executor_id"),
        )),
    )
    _add(reasons, "GRANT_PROPOSAL_DIGEST_MISMATCH", grant.get("proposal_digest") != proposal_digest)
    _add(reasons, "DISPATCH_PROPOSAL_DIGEST_MISMATCH", dispatch.get("proposal_digest") != proposal_digest)
    _add(reasons, "GRANT_CONTEXT_DIGEST_MISMATCH", grant.get("context_digest") != use.get("context_digest"))
    _add(reasons, "CONTEXT_DIGEST_MISMATCH", dispatch.get("context_digest") != use.get("context_digest"))
    _add(reasons, "GRANT_EXECUTION_NONCE_MISMATCH", grant.get("execution_nonce") != use.get("execution_nonce"))
    _add(reasons, "EXECUTION_NONCE_MISMATCH", dispatch.get("execution_nonce") != use.get("execution_nonce"))
    _add(reasons, "GRANT_POLICY_REF_MISMATCH", grant.get("policy_ref") != auth.get("policy_ref"))
    _add(reasons, "POLICY_REF_MISMATCH", dispatch.get("policy_ref") != auth.get("policy_ref"))

    occurrence = envelope.get("occurrence_id")
    _add(reasons, "OCCURRENCE_ID_INVALID", not isinstance(occurrence, str) or not occurrence)
    _add(reasons, "GRANT_OCCURRENCE_BINDING_MISMATCH", grant.get("occurrence_id") != occurrence)
    _add(reasons, "OCCURRENCE_BINDING_MISMATCH", dispatch.get("occurrence_id") != occurrence)
    _add(reasons, "ACTION_PROPOSAL_BINDING_MISMATCH", envelope.get("action") != proposal.get("action"))

    envelope_digest, derived_action = action_envelope_digest(envelope), action_id(envelope)
    _add(reasons, "GRANT_ACTION_ENVELOPE_DIGEST_MISMATCH", grant.get("action_envelope_digest") != envelope_digest)
    _add(reasons, "GRANT_ACTION_ID_MISMATCH", grant.get("action_id") != derived_action)
    _add(reasons, "ACTION_ENVELOPE_DIGEST_MISMATCH", dispatch.get("action_envelope_digest") != envelope_digest)
    _add(reasons, "AUTHORIZED_ACTION_ID_MISMATCH", dispatch.get("authorized_action_id") != grant.get("action_id"))
    _add(reasons, "SIBLING_CAPABILITY_SUBSTITUTION", dispatch.get("dispatched_action_id") != dispatch.get("authorized_action_id"))

    _add(reasons, "OUTCOME_REF_MISMATCH", dispatch.get("observed_outcome_ref") != outcome.get("outcome_ref"))
    _add(reasons, "OUTCOME_DIGEST_MISMATCH", dispatch.get("observed_outcome_digest") != observed_outcome_digest(outcome))

    times = (
        use.get("checked_at_ms"), grant.get("bound_at_ms"),
        dispatch.get("dispatched_at_ms"), dispatch.get("observed_at_ms"),
    )
    if not all(isinstance(value, int) for value in times):
        _add(reasons, "TIMESTAMP_INVALID", True)
    else:
        checked, bound, dispatched, observed = times
        _add(reasons, "GRANT_BINDING_PRECEDES_USE_CHECK", bound < checked)
        _add(reasons, "DISPATCH_PRECEDES_GRANT_BINDING", dispatched < bound)
        _add(reasons, "OUTCOME_PRECEDES_DISPATCH", observed < dispatched)

    for key in ("dispatch_ref", "observed_outcome_ref"):
        value = dispatch.get(key)
        _add(reasons, f"{key.upper()}_INVALID", not isinstance(value, str) or not value)

    use_id_value = use.get("use_id")
    if seen_use_ids is not None and isinstance(use_id_value, str):
        if use_id_value in seen_use_ids:
            _add(reasons, "GRANT_REPLAYED", True)
        elif not reasons:
            seen_use_ids.add(use_id_value)

    return VerificationResult(not reasons, tuple(reasons))


def _set_path(document: dict[str, Any], path: str, value: Any) -> None:
    parts, cursor = path.split("."), document
    if not parts or any(not part for part in parts):
        raise ValueError(f"invalid mutation path: {path!r}")
    for part in parts[:-1]:
        if not isinstance(cursor, dict) or part not in cursor:
            raise ValueError(f"mutation path not found: {path}")
        cursor = cursor[part]
    if not isinstance(cursor, dict) or parts[-1] not in cursor:
        raise ValueError(f"mutation path not found: {path}")
    cursor[parts[-1]] = copy.deepcopy(value)


def _materialize_case(base: Mapping[str, Any], case: Mapping[str, Any]) -> dict[str, Any]:
    transcript = copy.deepcopy(dict(base))
    for mutation in case.get("mutations", []):
        _set_path(transcript, mutation["path"], mutation["value"])
    recompute = set(case.get("recompute", []))
    if "outcome_digest" in recompute:
        transcript["dispatch_receipt"]["observed_outcome_digest"] = observed_outcome_digest(
            transcript["observed_outcome"]
        )
    if "grant_binding_id" in recompute:
        transcript["grant_binding"]["binding_id"] = compute_action_grant_binding_id(
            transcript["grant_binding"]
        )
    if "dispatch_receipt_id" in recompute:
        transcript["dispatch_receipt"]["receipt_id"] = compute_dispatch_receipt_id(
            transcript["dispatch_receipt"]
        )
    return transcript


def validate_fixture_shape(fixture: Mapping[str, Any]) -> None:
    if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise ValueError("fixture schema_version mismatch")
    if fixture.get("profile_id") != PROFILE_ID:
        raise ValueError("fixture profile_id mismatch")
    if not isinstance(fixture.get("base_transcript"), Mapping):
        raise ValueError("fixture base_transcript missing")
    cases = fixture.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("fixture cases must be a non-empty list")
    allowed_recompute = {"outcome_digest", "grant_binding_id", "dispatch_receipt_id"}
    for case in cases:
        if not isinstance(case, Mapping) or not isinstance(case.get("id"), str):
            raise ValueError("fixture case id missing")
        for mutation in case.get("mutations", []):
            if not isinstance(mutation, Mapping) or not isinstance(mutation.get("path"), str) or "value" not in mutation:
                raise ValueError(f"fixture case {case['id']} mutation invalid")
        recompute = case.get("recompute", [])
        if not isinstance(recompute, list) or not set(recompute).issubset(allowed_recompute):
            raise ValueError(f"fixture case {case['id']} recompute invalid")
        expected = case.get("expected")
        if not isinstance(expected, Mapping) or not isinstance(expected.get("valid"), bool):
            raise ValueError(f"fixture case {case['id']} expected.valid missing")
        reasons = expected.get("reason_codes", [])
        if not isinstance(reasons, list) or not all(isinstance(reason, str) for reason in reasons):
            raise ValueError(f"fixture case {case['id']} expected.reason_codes invalid")
        preconsumed = case.get("preconsumed_use_ids", [])
        if not isinstance(preconsumed, list) or not all(isinstance(use_id, str) for use_id in preconsumed):
            raise ValueError(f"fixture case {case['id']} preconsumed_use_ids invalid")


def load_fixture(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_fixture_shape(data)
    return data


def run_fixture(fixture: Mapping[str, Any]) -> dict[str, Any]:
    validate_fixture_shape(fixture)
    results = []
    for case in fixture["cases"]:
        transcript = _materialize_case(fixture["base_transcript"], case)
        seen = {
            transcript["use_time"]["use_id"] if use_id == "@use_id" else use_id
            for use_id in case.get("preconsumed_use_ids", [])
        }
        result = verify_dispatch_transcript(transcript, seen_use_ids=seen)
        expected = case["expected"]
        expected_reasons = tuple(expected.get("reason_codes", []))
        passed = result.valid is expected["valid"] and result.reason_codes == expected_reasons
        results.append({
            "id": case["id"],
            "passed": passed,
            "actual": {"valid": result.valid, "reason_codes": list(result.reason_codes)},
            "expected": {"valid": expected["valid"], "reason_codes": list(expected_reasons)},
        })
    passed_count = sum(item["passed"] for item in results)
    return {
        "profile_id": PROFILE_ID,
        "schema_version": FIXTURE_SCHEMA_VERSION,
        "cases": results,
        "summary": {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
            "all_passed": passed_count == len(results),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detached verifier for VTL ToolDispatchReceipt transcripts."
    )
    parser.add_argument("path", help="JSON transcript or v0.7 fixture file")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.path).read_text(encoding="utf-8"))
    if data.get("schema_version") == FIXTURE_SCHEMA_VERSION:
        result = run_fixture(data)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["summary"]["all_passed"] else 1
    result = verify_dispatch_transcript(data)
    print(json.dumps({
        "profile_id": PROFILE_ID,
        "schema_version": SCHEMA_VERSION,
        "valid": result.valid,
        "reason_codes": list(result.reason_codes),
    }, indent=2, sort_keys=True))
    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
