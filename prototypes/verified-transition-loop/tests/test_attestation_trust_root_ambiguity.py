import copy
from pathlib import Path

from verified_transition_loop.attestation import load_fixture, verify_attested_dispatch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "attested-dispatch-v0.8.json"
NOW = 1_800_000_001_000


def test_duplicate_signer_key_id_fails_closed_without_order_dependence():
    fixture = load_fixture(FIXTURE)
    envelope = copy.deepcopy(fixture["base_envelope"])
    trust_root = copy.deepcopy(fixture["trust_root"])

    duplicate = copy.deepcopy(trust_root["keys"][0])
    duplicate["public_key_base64"] = "gTl3Dqh9F19Wo1Rmw0x+zMuNipG07jeiXfYPW4/Js5Q="
    trust_root["keys"].append(duplicate)

    result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)

    assert result.valid is False
    assert result.integrity_valid is True
    assert result.signature_valid is False
    assert result.trusted_current_authority is False
    assert result.reason_codes == ("SIGNER_KEY_AMBIGUOUS",)

    # Reversing the ambiguous entries must not make one silently win.
    trust_root["keys"].reverse()
    reversed_result = verify_attested_dispatch(envelope, trust_root, now_ms=NOW)
    assert reversed_result.valid is False
    assert reversed_result.reason_codes == ("SIGNER_KEY_AMBIGUOUS",)
