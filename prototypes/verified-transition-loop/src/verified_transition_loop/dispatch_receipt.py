from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, MutableSet

PROFILE_ID = "vtl-tool-dispatch-v0.7"
SCHEMA_VERSION = "vtl.tool-dispatch-receipt/v0.7"
FIXTURE_SCHEMA_VERSION = "vtl.tool-dispatch-fixture/v0.7"


def _reject_duplicate_json_members(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON member name: {key}")
        value[key] = item
    return value


def _reject_nonfinite_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _load_json(path: str | Path) -> Any:
    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_json_members,
        parse_constant=_reject_nonfinite_json_constant,
    )


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
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
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


def _non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def _string(value: Any) -> bool:
    return isinstance(value, str)


def _integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nullable_string(value: Any) -> bool:
    return value is None or isinstance(value, str)


def _nullable_integer(value: Any) -> bool:
    return value is None or _integer(value)


def _hex64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _string_list(value: Any) -> bool:
    # JSON input can only supply lists. Tuples are also accepted for direct
    # in-memory transcripts produced from frozen dataclasses before JSON encoding.
    return isinstance(value, (list, tuple)) and all(
        isinstance(item, str) for item in value
    )


def _object(value: Any) -> bool:
    return isinstance(value, Mapping)


def _json_compatible(value: Any) -> bool:
    if value is None or isinstance(value, (bool, int, str)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, (list, tuple)):
        return all(_json_compatible(item) for item in value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and _json_compatible(item)
            for key, item in value.items()
        )
    return False


def _enum(*allowed: str):
    return lambda value: isinstance(value, str) and value in allowed


_TRANSCRIPT_REQUIRED_FIELDS: dict[str, dict[str, Any]] = {
    "proposal": {
        "transition_id": _non_empty_string,
        "intent_id": _non_empty_string,
        "pre_state": _string,
        "action": _non_empty_string,
        "expected_post_state": _string,
        "invariants": _string_list,
    },
    "authorization": {
        "decision_id": _non_empty_string,
        "transition_id": _non_empty_string,
        "intent_id": _non_empty_string,
        "verdict": _enum("AUTHORIZE", "HOLD", "BLOCK"),
        "reason_codes": _string_list,
        "verifier_id": _non_empty_string,
        "executor_id": _non_empty_string,
        "proposal_digest": _hex64,
        "evidence_digest": _hex64,
        "source_ref": _nullable_string,
        "policy_ref": _nullable_string,
        "approval_ref": _nullable_string,
        "approval_valid_until_ms": _nullable_integer,
    },
    "use_time": {
        "use_id": _non_empty_string,
        "authorization_decision_id": _non_empty_string,
        "transition_id": _non_empty_string,
        "verdict": _enum("EXECUTE", "HOLD", "BLOCK"),
        "reason_codes": _string_list,
        "executor_id": _non_empty_string,
        "proposal_digest": _hex64,
        "context_digest": _hex64,
        "execution_nonce": _string,
        "checked_at_ms": _integer,
    },
    "action_envelope": {
        "runtime_surface": _non_empty_string,
        "transition_id": _non_empty_string,
        "occurrence_id": _non_empty_string,
        "action": _non_empty_string,
        "payload": _object,
    },
    "grant_binding": {
        "binding_id": _non_empty_string,
        "profile_id": lambda value: value == PROFILE_ID,
        "schema_version": lambda value: value == SCHEMA_VERSION,
        "authorization_decision_id": _non_empty_string,
        "use_id": _non_empty_string,
        "transition_id": _non_empty_string,
        "proposal_digest": _hex64,
        "action_id": _non_empty_string,
        "action_envelope_digest": _hex64,
        "executor_id": _non_empty_string,
        "execution_nonce": _string,
        "occurrence_id": _non_empty_string,
        "context_digest": _hex64,
        "policy_ref": _nullable_string,
        "bound_at_ms": _integer,
    },
    "dispatch_receipt": {
        "receipt_id": _non_empty_string,
        "profile_id": lambda value: value == PROFILE_ID,
        "schema_version": lambda value: value == SCHEMA_VERSION,
        "authorization_decision_id": _non_empty_string,
        "use_id": _non_empty_string,
        "grant_binding_id": _non_empty_string,
        "transition_id": _non_empty_string,
        "proposal_digest": _hex64,
        "authorized_action_id": _non_empty_string,
        "dispatched_action_id": _non_empty_string,
        "action_envelope_digest": _hex64,
        "executor_id": _non_empty_string,
        "execution_nonce": _string,
        "occurrence_id": _non_empty_string,
        "context_digest": _hex64,
        "policy_ref": _nullable_string,
        "dispatch_ref": _non_empty_string,
        "observed_outcome_ref": _non_empty_string,
        "observed_outcome_digest": _hex64,
        "dispatched_at_ms": _integer,
        "observed_at_ms": _integer,
    },
    "observed_outcome": {
        "outcome_ref": _non_empty_string,
        "transition_id": _non_empty_string,
    },
}

def validate_transcript_shape(transcript: Any) -> tuple[str, ...]:
    """Mirror the published transcript schema before any binding comparison.

    This remains dependency-free by enforcing the schema's required fields and
    field types directly. Missing fields never become matching ``None`` values.
    """

    if not isinstance(transcript, Mapping):
        return ("TRANSCRIPT_ROOT_INVALID",)
    if not _json_compatible(transcript):
        return ("TRANSCRIPT_CANONICALIZATION_INVALID",)

    reasons: list[str] = []
    _add(reasons, "PROFILE_ID_MISMATCH", transcript.get("profile_id") != PROFILE_ID)
    _add(
        reasons,
        "SCHEMA_VERSION_MISMATCH",
        transcript.get("schema_version") != SCHEMA_VERSION,
    )

    for section_name, field_specs in _TRANSCRIPT_REQUIRED_FIELDS.items():
        section = transcript.get(section_name)
        if not isinstance(section, Mapping):
            _add(reasons, f"SECTION_INVALID:{section_name}", True)
            continue
        for field_name, predicate in field_specs.items():
            if field_name not in section or not predicate(section[field_name]):
                _add(
                    reasons,
                    f"TRANSCRIPT_SCHEMA_INVALID:{section_name}.{field_name}",
                    True,
                )

    return tuple(reasons)


def verify_dispatch_transcript(
    transcript: Any,
    *,
    seen_use_ids: MutableSet[str] | None = None,
) -> VerificationResult:
    reasons = list(validate_transcript_shape(transcript))
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
    _add(
        reasons,
        "VERIFIER_EXECUTOR_COLLISION",
        auth.get("verifier_id") == auth.get("executor_id"),
    )
    for field_name, reason in (
        ("source_ref", "SOURCE_REF_MISSING"),
        ("policy_ref", "POLICY_REF_MISSING"),
        ("approval_ref", "APPROVAL_REF_MISSING"),
    ):
        _add(reasons, reason, not _non_empty_string(auth.get(field_name)))
    _add(reasons, "USE_TIME_RECEIPT_INVALID", not verify_serialized_use_time_receipt(use))
    _add(reasons, "USE_TIME_NOT_EXECUTABLE", use.get("verdict") != "EXECUTE")
    execution_nonce = use.get("execution_nonce")
    _add(
        reasons,
        "EXECUTION_NONCE_INVALID",
        not _non_empty_string(execution_nonce)
        or any(character.isspace() for character in execution_nonce),
    )

    approval_expiry = auth.get("approval_valid_until_ms")
    checked_at = use.get("checked_at_ms")
    _add(reasons, "APPROVAL_EXPIRY_MISSING", approval_expiry is None)
    if _integer(approval_expiry) and _integer(checked_at):
        _add(
            reasons,
            "APPROVAL_EXPIRED_AT_USE",
            checked_at >= approval_expiry,
        )

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
    if not all(_integer(value) for value in times):
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


def validate_fixture_shape(fixture: Any) -> None:
    if not isinstance(fixture, Mapping):
        raise ValueError("fixture root must be an object")
    if fixture.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise ValueError("fixture schema_version mismatch")
    if fixture.get("profile_id") != PROFILE_ID:
        raise ValueError("fixture profile_id mismatch")
    base_transcript = fixture.get("base_transcript")
    if not isinstance(base_transcript, Mapping):
        raise ValueError("fixture base_transcript missing")
    base_errors = validate_transcript_shape(base_transcript)
    if base_errors:
        raise ValueError(
            "fixture base_transcript schema invalid: " + ", ".join(base_errors)
        )
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
    data = _load_json(path)
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
    data = _load_json(args.path)
    if isinstance(data, Mapping) and data.get("schema_version") == FIXTURE_SCHEMA_VERSION:
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
