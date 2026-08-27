import copy
import json
from pathlib import Path

import pytest

import verified_transition_loop.dispatch_receipt as dispatch_receipt
from verified_transition_loop.dispatch_receipt import (
    action_envelope_digest,
    action_id,
    compute_action_grant_binding_id,
    compute_dispatch_receipt_id,
    load_fixture,
    main,
    verify_dispatch_transcript,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tool-dispatch-receipt-v0.7.json"


def base_transcript():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(fixture["base_transcript"])


def resign_transcript(transcript):
    authorization = transcript["authorization"]
    authorization["decision_id"] = dispatch_receipt._stable_id(
        "auth",
        dispatch_receipt._pick(authorization, dispatch_receipt._AUTH_KEYS),
    )
    use_time = transcript["use_time"]
    use_time["authorization_decision_id"] = authorization["decision_id"]
    use_time["use_id"] = dispatch_receipt._stable_id(
        "use",
        dispatch_receipt._pick(use_time, dispatch_receipt._USE_KEYS),
    )
    grant = transcript["grant_binding"]
    grant["authorization_decision_id"] = authorization["decision_id"]
    grant["use_id"] = use_time["use_id"]
    grant["binding_id"] = compute_action_grant_binding_id(grant)
    receipt = transcript["dispatch_receipt"]
    receipt["authorization_decision_id"] = authorization["decision_id"]
    receipt["use_id"] = use_time["use_id"]
    receipt["grant_binding_id"] = grant["binding_id"]
    receipt["receipt_id"] = compute_dispatch_receipt_id(receipt)


def test_non_object_transcript_root_fails_closed_without_get_access():
    result = verify_dispatch_transcript([])

    assert result.valid is False
    assert result.reason_codes == ("TRANSCRIPT_ROOT_INVALID",)


def test_self_consistent_missing_required_payload_is_rejected_by_schema_gate():
    transcript = base_transcript()
    envelope = transcript["action_envelope"]
    del envelope["payload"]

    # Recompute every action-dependent binding so the transcript is otherwise
    # self-consistent. Before the schema gate, this shape could validate because
    # the missing required field was not compared semantically.
    envelope_digest = action_envelope_digest(envelope)
    derived_action_id = action_id(envelope)

    grant = transcript["grant_binding"]
    grant["action_envelope_digest"] = envelope_digest
    grant["action_id"] = derived_action_id
    grant["binding_id"] = compute_action_grant_binding_id(grant)

    dispatch = transcript["dispatch_receipt"]
    dispatch["grant_binding_id"] = grant["binding_id"]
    dispatch["authorized_action_id"] = derived_action_id
    dispatch["dispatched_action_id"] = derived_action_id
    dispatch["action_envelope_digest"] = envelope_digest
    dispatch["receipt_id"] = compute_dispatch_receipt_id(dispatch)

    result = verify_dispatch_transcript(transcript)

    assert result.valid is False
    assert result.reason_codes == (
        "TRANSCRIPT_SCHEMA_INVALID:action_envelope.payload",
    )


def test_self_consistent_empty_execution_nonce_is_rejected():
    transcript = base_transcript()
    transcript["use_time"]["execution_nonce"] = ""
    transcript["grant_binding"]["execution_nonce"] = ""
    transcript["dispatch_receipt"]["execution_nonce"] = ""
    resign_transcript(transcript)

    result = verify_dispatch_transcript(transcript)

    assert result.valid is False
    assert result.reason_codes == ("EXECUTION_NONCE_INVALID",)


def test_self_consistent_verifier_executor_collision_is_rejected():
    transcript = base_transcript()
    transcript["authorization"]["verifier_id"] = transcript["authorization"][
        "executor_id"
    ]
    resign_transcript(transcript)

    result = verify_dispatch_transcript(transcript)

    assert result.valid is False
    assert result.reason_codes == ("VERIFIER_EXECUTOR_COLLISION",)


def test_self_consistent_approval_at_expiry_boundary_is_rejected():
    transcript = base_transcript()
    transcript["authorization"]["approval_valid_until_ms"] = transcript[
        "use_time"
    ]["checked_at_ms"]
    resign_transcript(transcript)

    result = verify_dispatch_transcript(transcript)

    assert result.valid is False
    assert result.reason_codes == ("APPROVAL_EXPIRED_AT_USE",)


def test_missing_authority_binding_is_rejected_before_integrity_checks():
    transcript = base_transcript()
    del transcript["authorization"]["source_ref"]

    result = verify_dispatch_transcript(transcript)

    assert result.valid is False
    assert result.reason_codes == (
        "TRANSCRIPT_SCHEMA_INVALID:authorization.source_ref",
    )


@pytest.mark.parametrize(
    "second_name",
    ("profile_id", r"profile\u005fid"),
)
def test_fixture_loader_rejects_duplicate_json_member_names(tmp_path, second_name):
    raw = FIXTURE.read_text(encoding="utf-8")
    ambiguous = raw.replace(
        '"profile_id": "vtl-tool-dispatch-v0.7",',
        (
            '"profile_id": "wrong",\n'
            f'  "{second_name}": "vtl-tool-dispatch-v0.7",'
        ),
        1,
    )
    path = tmp_path / "ambiguous.json"
    path.write_text(ambiguous, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON member name: profile_id"):
        load_fixture(path)


def test_non_finite_fixture_value_is_rejected_as_non_json(tmp_path):
    raw = FIXTURE.read_text(encoding="utf-8")
    ambiguous = raw.replace(
        (
            '"description": "Detached ToolDispatchReceipt conformance vectors '
            'for exact grant consumption and outcome binding.",'
        ),
        '"description": NaN,',
        1,
    )
    path = tmp_path / "non-finite.json"
    path.write_text(ambiguous, encoding="utf-8")

    with pytest.raises(ValueError, match="non-finite JSON constant: NaN"):
        load_fixture(path)


def test_cli_rejects_non_object_json_root(tmp_path):
    path = tmp_path / "invalid-root.json"
    path.write_text("[]", encoding="utf-8")

    assert main([str(path)]) == 1
