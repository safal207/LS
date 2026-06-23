from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from modules.trusted_runtime.adapters.pythia import (
    PythiaLabsConfig,
    PythiaLabsEvidenceAdapter,
)
from modules.trusted_runtime.authorization import (
    AuthorizationExpiredError,
    AuthorizationMismatchError,
    AuthorizationReplayError,
    InMemoryNonceStore,
    ProofPathAuthorizationBundleAdapter,
    authorization_bundle_event,
    verify_authorization_bundle_files,
)
from modules.trusted_runtime.contracts import DecisionCode
from modules.trusted_runtime.evidence import (
    DeterministicEvidenceGateAdapter,
    EvidenceArtifactMismatchError,
    EvidenceDecisionNotAllow,
    EvidenceGateDisabledError,
    MalformedEvidenceDecisionResponseError,
    evidence_decision_event,
    evidence_decision_ref,
)


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "python/tests/fixtures/trusted-runtime/evidence"
BUNDLE_SCHEMA = ROOT / "schemas/trusted_runtime/authorization_bundle.schema.json"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _allow_request() -> dict:
    return _load("allow.json")["request"]


def _intent_from_request(
    request: dict,
    *,
    nonce: str = "nonce-valid-001",
    issued_at: str = "2026-06-23T08:00:00Z",
    expires_at: str = "2026-06-23T09:00:00Z",
) -> dict:
    return {
        "intent_id": request["intent_ref"],
        "task_id": request["task_id"],
        "trail_id": request["trail_id"],
        "actor": request["actor"],
        "action_ref": "artifact:write:review-summary",
        "scope": request["scope"],
        "issued_at": issued_at,
        "expires_at": expires_at,
        "nonce": nonce,
        "policy_version": request["policy_version"],
        "evidence_refs": request["evidence_refs"],
        "evidence_digest": request["artifact_digest"],
        "causal_audit_refs": [request["causal_audit_ref"]],
        "parent_cause": request["causal_audit_ref"],
        "metadata": {},
    }


def _allow_decision():
    return DeterministicEvidenceGateAdapter().decide(_allow_request())


def _bundle(intent: dict | None = None):
    request = _allow_request()
    return ProofPathAuthorizationBundleAdapter().build(
        _allow_decision(),
        intent or _intent_from_request(request),
    )


@pytest.mark.parametrize(
    ("fixture_name", "expected"),
    [
        ("allow.json", DecisionCode.ALLOW),
        ("hold.json", DecisionCode.HOLD),
        ("block.json", DecisionCode.BLOCK),
        ("escalate.json", DecisionCode.ESCALATE),
    ],
)
def test_deterministic_gate_covers_all_decisions(
    fixture_name: str,
    expected: DecisionCode,
) -> None:
    fixture = _load(fixture_name)

    decision = DeterministicEvidenceGateAdapter().decide(fixture["request"])

    assert decision.decision is expected
    assert decision.decision.value == fixture["expected_decision"]
    assert decision.parent_cause == fixture["request"]["causal_audit_ref"]


def test_evidence_decision_has_stable_reference_and_trail_event() -> None:
    decision = _allow_decision()

    first_ref = evidence_decision_ref(decision)
    second_ref = evidence_decision_ref(decision)
    event = evidence_decision_event(decision)

    assert first_ref == second_ref
    assert first_ref.startswith("decision:sha256:")
    assert event.payload["decision_ref"] == first_ref
    assert event.parent_cause == "event-causal-audit-001"
    assert event.evidence_refs == ("evidence:review-001",)


def test_pythia_adapter_is_disabled_by_default() -> None:
    with pytest.raises(EvidenceGateDisabledError):
        PythiaLabsEvidenceAdapter().decide(_allow_request())


def test_pythia_normalizes_current_accepted_artifact_shape() -> None:
    request = _allow_request()

    def runner(payload):
        assert payload["causal_authorization_allowed"] is True
        return {
            "status": "accepted",
            "stop_reason": "review_evidence_accepted",
            "digest": payload["artifact_digest"],
            "verification_status": "verified",
            "evidence_refs": payload["evidence_refs"],
            "policy_version": payload["policy_version"],
        }

    decision = PythiaLabsEvidenceAdapter(
        PythiaLabsConfig(enabled=True),
        runner=runner,
    ).decide(request)

    assert decision.decision is DecisionCode.ALLOW
    assert decision.reason == "review_evidence_accepted"
    assert decision.parent_cause == request["causal_audit_ref"]


def test_pythia_normalizes_rejected_to_block() -> None:
    def runner(payload):
        return {
            "status": "rejected",
            "stop_reason": "policy_check_failed",
        }

    decision = PythiaLabsEvidenceAdapter(
        PythiaLabsConfig(enabled=True),
        runner=runner,
    ).decide(_allow_request())

    assert decision.decision is DecisionCode.BLOCK


def test_pythia_allow_rejects_digest_mismatch() -> None:
    def runner(payload):
        return {
            "decision": "ALLOW",
            "reason": "claimed_allow",
            "digest": "different-digest",
            "verification_status": "verified",
        }

    adapter = PythiaLabsEvidenceAdapter(
        PythiaLabsConfig(enabled=True),
        runner=runner,
    )
    with pytest.raises(EvidenceArtifactMismatchError, match="digest"):
        adapter.decide(_allow_request())


def test_model_output_alone_cannot_authorize() -> None:
    request = dict(_allow_request())
    request["evidence_refs"] = []
    request["artifact_digest"] = ""
    request["artifact_verified"] = False

    def runner(payload):
        return {
            "decision": "ALLOW",
            "reason": "model_claimed_allow",
            "verification_status": "verified",
            "digest": "model-generated-digest",
        }

    adapter = PythiaLabsEvidenceAdapter(
        PythiaLabsConfig(enabled=True),
        runner=runner,
    )
    with pytest.raises(EvidenceArtifactMismatchError):
        adapter.decide(request)


def test_pythia_rejects_unknown_decision_vocabulary() -> None:
    def runner(payload):
        return {"decision": "MAYBE", "reason": "not stable"}

    adapter = PythiaLabsEvidenceAdapter(
        PythiaLabsConfig(enabled=True),
        runner=runner,
    )
    with pytest.raises(MalformedEvidenceDecisionResponseError):
        adapter.decide(_allow_request())


@pytest.mark.parametrize("fixture_name", ["hold.json", "block.json", "escalate.json"])
def test_non_allow_decisions_never_build_authorization(fixture_name: str) -> None:
    fixture = _load(fixture_name)
    decision = DeterministicEvidenceGateAdapter().decide(fixture["request"])
    intent = _intent_from_request(_allow_request())

    with pytest.raises(EvidenceDecisionNotAllow):
        ProofPathAuthorizationBundleAdapter().build(decision, intent)


def test_proofpath_bundle_is_portable_and_schema_valid() -> None:
    bundle = _bundle()
    schema = json.loads(BUNDLE_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    assert list(validator.iter_errors(bundle.to_dict())) == []
    assert set(bundle.files) == {
        "manifest.json",
        "decisions.jsonl",
        "hash-chain.json",
        "verifier-result.json",
        "privacy-report.json",
        "README.md",
    }
    assert len(bundle.file_hashes) == 6
    assert bundle.decision_ref.startswith("decision:sha256:")
    assert bundle.authorization_ref.startswith("authorization-record:sha256:")


def test_saved_bundle_verifies_without_rerunning_models() -> None:
    bundle = _bundle()

    result = verify_authorization_bundle_files(
        bundle.to_files(),
        now="2026-06-23T08:30:00Z",
    )

    assert result.valid is True
    assert result.bundle_id == bundle.bundle_id
    assert result.chain_head == bundle.chain_head
    assert result.authorization_ref == bundle.authorization_ref


def test_expired_authorization_is_blocked() -> None:
    fixture = _load("expired_intent.json")
    bundle = _bundle(fixture["intent"])

    with pytest.raises(AuthorizationExpiredError, match="authorization_expired"):
        verify_authorization_bundle_files(
            bundle.to_files(),
            now=fixture["verify_at"],
        )


def test_duplicate_nonce_is_blocked_deterministically() -> None:
    fixture = _load("replay_attempt.json")
    bundle = _bundle(fixture["intent"])
    store = InMemoryNonceStore()

    first = verify_authorization_bundle_files(
        bundle.to_files(),
        now=fixture["verify_at"],
        nonce_store=store,
        consume_nonce=True,
    )
    assert first.valid is True

    with pytest.raises(AuthorizationReplayError, match="already consumed"):
        verify_authorization_bundle_files(
            bundle.to_files(),
            now=fixture["verify_at"],
            nonce_store=store,
            consume_nonce=True,
        )


def test_bundle_tampering_breaks_manifest_verification() -> None:
    files = _bundle().to_files()
    files["decisions.jsonl"] = files["decisions.jsonl"].replace(
        '"decision":"ALLOW"',
        '"decision":"BLOCK"',
        1,
    )

    with pytest.raises(Exception, match="manifest_hash_mismatch"):
        verify_authorization_bundle_files(
            files,
            now="2026-06-23T08:30:00Z",
        )


def test_mismatched_policy_is_rejected_before_bundle_creation() -> None:
    intent = _intent_from_request(_allow_request())
    intent["policy_version"] = "policy.other.v1"

    with pytest.raises(AuthorizationMismatchError, match="policy"):
        ProofPathAuthorizationBundleAdapter().build(_allow_decision(), intent)


def test_authorization_event_descends_from_evidence_decision_event() -> None:
    bundle = _bundle()
    event = authorization_bundle_event(bundle)

    assert event.event_type.value == "AUTHORIZATION_ISSUED"
    assert event.payload["bundle_id"] == bundle.bundle_id
    assert event.evidence_refs == bundle.evidence_refs
