import copy
import json
from pathlib import Path

from verified_transition_loop.dispatch_receipt import (
    action_envelope_digest,
    action_id,
    compute_action_grant_binding_id,
    compute_dispatch_receipt_id,
    main,
    verify_dispatch_transcript,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "tool-dispatch-receipt-v0.7.json"


def base_transcript():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return copy.deepcopy(fixture["base_transcript"])


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


def test_cli_rejects_non_object_json_root(tmp_path):
    path = tmp_path / "invalid-root.json"
    path.write_text("[]", encoding="utf-8")

    assert main([str(path)]) == 1
