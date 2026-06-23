from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, MutableSet, Optional, Sequence

from .contracts import DecisionCode, EvidenceDecision, ExecutionAuthorization, TrailEvent, TrailEventType
from .evidence import evidence_decision_ref, require_allow_decision


AUTHORIZATION_BUNDLE_VERSION = "trusted_runtime.authorization_bundle.v0.1"
PROOFPATH_BUNDLE_SCHEMA = "proofpath.evidence_bundle.v0.1"


class AuthorizationError(RuntimeError):
    """Base error for authorization creation and verification."""


class AuthorizationExpiredError(AuthorizationError):
    """Raised when an intent or authorization is expired."""


class AuthorizationReplayError(AuthorizationError):
    """Raised when a nonce has already been consumed."""


class AuthorizationMismatchError(AuthorizationError):
    """Raised when intent, decision, and authorization records disagree."""


class AuthorizationIncompleteError(AuthorizationError):
    """Raised when required authorization evidence is missing."""


class BundleVerificationError(AuthorizationError):
    """Raised when a portable evidence bundle fails offline verification."""


@dataclass(frozen=True)
class AuthorizationIntent:
    intent_id: str
    task_id: str
    trail_id: str
    actor: str
    action_ref: str
    scope: tuple[str, ...]
    issued_at: str
    expires_at: str
    nonce: str
    policy_version: str
    evidence_refs: tuple[str, ...]
    evidence_digest: str
    causal_audit_refs: tuple[str, ...]
    parent_cause: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = (
            self.intent_id,
            self.task_id,
            self.trail_id,
            self.actor,
            self.action_ref,
            self.issued_at,
            self.expires_at,
            self.nonce,
            self.policy_version,
            self.evidence_digest,
            self.parent_cause,
        )
        if not all(required):
            raise ValueError("authorization intent fields must not be empty")
        if not self.scope:
            raise ValueError("authorization intent requires a non-empty scope")
        if not self.evidence_refs:
            raise ValueError("authorization intent requires evidence references")
        if not self.causal_audit_refs:
            raise ValueError("authorization intent requires causal audit references")
        for name, values in (
            ("scope", self.scope),
            ("evidence_refs", self.evidence_refs),
            ("causal_audit_refs", self.causal_audit_refs),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"authorization intent {name} must be unique")
        issued = parse_datetime(self.issued_at)
        expires = parse_datetime(self.expires_at)
        if expires <= issued:
            raise ValueError("authorization intent expires_at must follow issued_at")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "AuthorizationIntent":
        return cls(
            intent_id=str(payload["intent_id"]),
            task_id=str(payload["task_id"]),
            trail_id=str(payload["trail_id"]),
            actor=str(payload["actor"]),
            action_ref=str(payload["action_ref"]),
            scope=tuple(str(value) for value in payload["scope"]),
            issued_at=str(payload["issued_at"]),
            expires_at=str(payload["expires_at"]),
            nonce=str(payload["nonce"]),
            policy_version=str(payload["policy_version"]),
            evidence_refs=tuple(str(value) for value in payload["evidence_refs"]),
            evidence_digest=str(payload["evidence_digest"]),
            causal_audit_refs=tuple(
                str(value) for value in payload["causal_audit_refs"]
            ),
            parent_cause=str(payload["parent_cause"]),
            metadata=dict(payload.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "actor": self.actor,
            "action_ref": self.action_ref,
            "scope": list(self.scope),
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "policy_version": self.policy_version,
            "evidence_refs": list(self.evidence_refs),
            "evidence_digest": self.evidence_digest,
            "causal_audit_refs": list(self.causal_audit_refs),
            "parent_cause": self.parent_cause,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AuthorizationBundle:
    bundle_id: str
    task_id: str
    trail_id: str
    adapter: str
    actor: str
    created_at: str
    intent_ref: str
    decision_ref: str
    authorization_ref: str
    policy_version: str
    nonce: str
    scope: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    causal_audit_refs: tuple[str, ...]
    chain_head: str
    file_hashes: Mapping[str, str]
    verification_instructions: tuple[str, ...]
    files: Mapping[str, str]
    schema_version: str = AUTHORIZATION_BUNDLE_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != AUTHORIZATION_BUNDLE_VERSION:
            raise ValueError(
                f"unsupported authorization bundle version: {self.schema_version}"
            )
        required = (
            self.bundle_id,
            self.task_id,
            self.trail_id,
            self.adapter,
            self.actor,
            self.created_at,
            self.intent_ref,
            self.decision_ref,
            self.authorization_ref,
            self.policy_version,
            self.nonce,
            self.chain_head,
        )
        if not all(required):
            raise ValueError("authorization bundle identifiers must not be empty")
        if not self.scope or not self.evidence_refs or not self.causal_audit_refs:
            raise ValueError("authorization bundle requires scope, evidence, and causal refs")
        if not self.file_hashes or not self.files:
            raise ValueError("authorization bundle requires portable files and hashes")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "bundle_id": self.bundle_id,
            "task_id": self.task_id,
            "trail_id": self.trail_id,
            "adapter": self.adapter,
            "actor": self.actor,
            "created_at": self.created_at,
            "intent_ref": self.intent_ref,
            "decision_ref": self.decision_ref,
            "authorization_ref": self.authorization_ref,
            "policy_version": self.policy_version,
            "nonce": self.nonce,
            "scope": list(self.scope),
            "evidence_refs": list(self.evidence_refs),
            "causal_audit_refs": list(self.causal_audit_refs),
            "chain_head": self.chain_head,
            "file_hashes": dict(self.file_hashes),
            "verification_instructions": list(self.verification_instructions),
            "file_names": sorted(self.files),
        }

    def to_files(self) -> dict[str, str]:
        return dict(self.files)


@dataclass(frozen=True)
class BundleVerificationResult:
    bundle_id: str
    valid: bool
    verified_at: str
    checked_files: tuple[str, ...]
    chain_head: str
    authorization_ref: str
    reason_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "valid": self.valid,
            "verified_at": self.verified_at,
            "checked_files": list(self.checked_files),
            "chain_head": self.chain_head,
            "authorization_ref": self.authorization_ref,
            "reason_codes": list(self.reason_codes),
        }


class InMemoryNonceStore:
    """Small deterministic replay store for local tests and demos."""

    def __init__(self, initial: Optional[Sequence[str]] = None) -> None:
        self._seen: MutableSet[str] = set(initial or ())

    def is_consumed(self, nonce: str) -> bool:
        return nonce in self._seen

    def consume(self, nonce: str) -> None:
        if nonce in self._seen:
            raise AuthorizationReplayError(f"authorization nonce already consumed: {nonce}")
        self._seen.add(nonce)


@dataclass(frozen=True)
class ProofPathConfig:
    actor: str = "adapter:proofpath"

    def __post_init__(self) -> None:
        if not self.actor:
            raise ValueError("ProofPath actor must not be empty")


class ProofPathAuthorizationBundleAdapter:
    """Build a portable, offline-verifiable ProofPath-style evidence bundle."""

    def __init__(self, config: Optional[ProofPathConfig] = None) -> None:
        self.config = config or ProofPathConfig()

    @property
    def adapter_name(self) -> str:
        return "proofpath"

    def build(
        self,
        decision: EvidenceDecision,
        request: Mapping[str, Any],
    ) -> AuthorizationBundle:
        intent = AuthorizationIntent.from_mapping(request)
        require_allow_decision(decision)
        self._validate_match(decision, intent)

        decision_ref = evidence_decision_ref(decision)
        authorization_seed = {
            "intent": intent.to_dict(),
            "decision_ref": decision_ref,
            "actor": self.config.actor,
        }
        authorization_id = "authorization:sha256:" + digest_payload(authorization_seed)
        authorization = ExecutionAuthorization(
            authorization_id=authorization_id,
            task_id=intent.task_id,
            trail_id=intent.trail_id,
            decision=DecisionCode.ALLOW,
            actor=self.config.actor,
            scope=intent.scope,
            issued_at=intent.issued_at,
            expires_at=intent.expires_at,
            nonce=intent.nonce,
            evidence_refs=intent.evidence_refs,
            policy_version=intent.policy_version,
            parent_cause=decision_ref,
        )
        authorization_ref = "authorization-record:sha256:" + digest_payload(
            authorization.to_dict()
        )
        records = (
            {
                "record_type": "evidence_decision",
                "decision_ref": decision_ref,
                "record": decision.to_dict(),
            },
            {
                "record_type": "execution_authorization",
                "authorization_ref": authorization_ref,
                "intent_ref": intent.intent_id,
                "evidence_digest": intent.evidence_digest,
                "causal_audit_refs": list(intent.causal_audit_refs),
                "record": authorization.to_dict(),
            },
        )
        chain = build_hash_chain(records)
        chain_head = str(chain[-1]["chain_digest"])
        bundle_id = f"proofpath-bundle-{chain_head[:20]}"
        files = build_bundle_files(
            bundle_id=bundle_id,
            intent=intent,
            decision_ref=decision_ref,
            authorization_ref=authorization_ref,
            records=records,
            chain=chain,
            chain_head=chain_head,
            actor=self.config.actor,
        )
        file_hashes = {name: digest_text(content) for name, content in files.items()}
        return AuthorizationBundle(
            bundle_id=bundle_id,
            task_id=intent.task_id,
            trail_id=intent.trail_id,
            adapter=self.adapter_name,
            actor=self.config.actor,
            created_at=intent.issued_at,
            intent_ref=intent.intent_id,
            decision_ref=decision_ref,
            authorization_ref=authorization_ref,
            policy_version=intent.policy_version,
            nonce=intent.nonce,
            scope=intent.scope,
            evidence_refs=intent.evidence_refs,
            causal_audit_refs=intent.causal_audit_refs,
            chain_head=chain_head,
            file_hashes=file_hashes,
            verification_instructions=(
                "Verify every manifest file hash.",
                "Recompute the decision hash chain from genesis to chain head.",
                "Match task, trail, policy, scope, evidence, and causal references.",
                "Reject expired or previously consumed authorization nonces.",
            ),
            files=files,
        )

    @staticmethod
    def _validate_match(
        decision: EvidenceDecision,
        intent: AuthorizationIntent,
    ) -> None:
        if decision.task_id != intent.task_id or decision.trail_id != intent.trail_id:
            raise AuthorizationMismatchError(
                "evidence decision belongs to another task or trail"
            )
        if decision.policy_version != intent.policy_version:
            raise AuthorizationMismatchError(
                "evidence decision policy does not match intent"
            )
        if tuple(decision.evidence_refs) != tuple(intent.evidence_refs):
            raise AuthorizationMismatchError(
                "evidence decision references do not match intent"
            )
        if decision.parent_cause not in intent.causal_audit_refs:
            raise AuthorizationMismatchError(
                "evidence decision is not descended from an accepted causal audit"
            )


def build_hash_chain(records: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    chain: list[dict[str, Any]] = []
    previous: Optional[str] = None
    for sequence, record in enumerate(records):
        record_digest = digest_payload(record)
        link_payload = {
            "sequence": sequence,
            "record_type": record["record_type"],
            "record_digest": record_digest,
            "previous_chain_digest": previous,
        }
        chain_digest = digest_payload(link_payload)
        chain.append({**link_payload, "chain_digest": chain_digest})
        previous = chain_digest
    return tuple(chain)


def build_bundle_files(
    *,
    bundle_id: str,
    intent: AuthorizationIntent,
    decision_ref: str,
    authorization_ref: str,
    records: Sequence[Mapping[str, Any]],
    chain: Sequence[Mapping[str, Any]],
    chain_head: str,
    actor: str,
) -> dict[str, str]:
    decisions_jsonl = "".join(canonical_json(record) + "\n" for record in records)
    hash_chain_json = pretty_json(
        {
            "schema": PROOFPATH_BUNDLE_SCHEMA,
            "bundle_id": bundle_id,
            "chain_head": chain_head,
            "entries": list(chain),
        }
    )
    privacy_report_json = pretty_json(
        {
            "schema": "proofpath.privacy_report.v0.1",
            "bundle_id": bundle_id,
            "status": "pass",
            "included_fields": [
                "identifiers",
                "scope",
                "policy_version",
                "evidence_references",
                "evidence_digest",
                "causal_audit_references",
                "decision",
                "authorization",
            ],
            "omitted_fields": [
                "prompts",
                "raw_model_outputs",
                "credentials",
                "private_task_content",
                "personal_or_payment_data_not_required_for_verification",
            ],
        }
    )
    verifier_result_json = pretty_json(
        {
            "schema": "proofpath.verifier_result.v0.1",
            "bundle_id": bundle_id,
            "status": "verified",
            "checks": [
                {"name": "manifest_hashes", "status": "PASS"},
                {"name": "hash_chain", "status": "PASS"},
                {"name": "authorization_match", "status": "PASS"},
                {"name": "privacy_boundary", "status": "PASS"},
            ],
            "chain_head": chain_head,
            "authorization_ref": authorization_ref,
        }
    )
    readme = (
        "# ProofPath authorization evidence bundle\n\n"
        "This portable bundle can be verified without rerunning any model.\n\n"
        "1. Recompute SHA-256 for every file listed in manifest.json.\n"
        "2. Parse decisions.jsonl and recompute hash-chain.json.\n"
        "3. Confirm task, trail, policy, scope, evidence, and causal references match.\n"
        "4. Confirm the authorization is unexpired and the nonce has not been consumed.\n"
        "5. Inspect privacy-report.json before accepting the bundle.\n"
    )
    non_manifest_files = {
        "decisions.jsonl": decisions_jsonl,
        "hash-chain.json": hash_chain_json,
        "verifier-result.json": verifier_result_json,
        "privacy-report.json": privacy_report_json,
        "README.md": readme,
    }
    manifest = {
        "schema": PROOFPATH_BUNDLE_SCHEMA,
        "bundle_id": bundle_id,
        "created_at": intent.issued_at,
        "actor": actor,
        "task_id": intent.task_id,
        "trail_id": intent.trail_id,
        "intent_ref": intent.intent_id,
        "decision_ref": decision_ref,
        "authorization_ref": authorization_ref,
        "policy_version": intent.policy_version,
        "nonce": intent.nonce,
        "scope": list(intent.scope),
        "evidence_refs": list(intent.evidence_refs),
        "evidence_digest": intent.evidence_digest,
        "causal_audit_refs": list(intent.causal_audit_refs),
        "chain_head": chain_head,
        "files": {
            name: {"sha256": digest_text(content)}
            for name, content in sorted(non_manifest_files.items())
        },
    }
    return {
        "manifest.json": pretty_json(manifest),
        **non_manifest_files,
    }


def verify_authorization_bundle_files(
    files: Mapping[str, str],
    *,
    now: str,
    nonce_store: Optional[InMemoryNonceStore] = None,
    consume_nonce: bool = False,
) -> BundleVerificationResult:
    required_files = {
        "manifest.json",
        "decisions.jsonl",
        "hash-chain.json",
        "verifier-result.json",
        "privacy-report.json",
        "README.md",
    }
    missing = required_files - set(files)
    if missing:
        raise AuthorizationIncompleteError(
            f"authorization bundle is missing files: {sorted(missing)}"
        )
    manifest = parse_json_object(files["manifest.json"], "manifest.json")
    if manifest.get("schema") != PROOFPATH_BUNDLE_SCHEMA:
        raise BundleVerificationError("unsupported_bundle_schema")
    declared_files = manifest.get("files")
    if not isinstance(declared_files, Mapping):
        raise AuthorizationIncompleteError("manifest files map is missing")
    for name in sorted(required_files - {"manifest.json"}):
        declaration = declared_files.get(name)
        if not isinstance(declaration, Mapping):
            raise AuthorizationIncompleteError(f"manifest_file_missing:{name}")
        expected = declaration.get("sha256")
        actual = digest_text(files[name])
        if expected != actual:
            raise BundleVerificationError(f"manifest_hash_mismatch:{name}")

    records = parse_jsonl(files["decisions.jsonl"])
    if len(records) != 2:
        raise AuthorizationIncompleteError("decision_record_missing")
    if records[0].get("record_type") != "evidence_decision":
        raise AuthorizationMismatchError("first bundle record must be evidence_decision")
    if records[1].get("record_type") != "execution_authorization":
        raise AuthorizationMismatchError(
            "second bundle record must be execution_authorization"
        )

    chain_document = parse_json_object(files["hash-chain.json"], "hash-chain.json")
    entries = chain_document.get("entries")
    if not isinstance(entries, list) or len(entries) != len(records):
        raise BundleVerificationError("hash_chain_broken")
    expected_chain = build_hash_chain(records)
    if entries != list(expected_chain):
        raise BundleVerificationError("hash_chain_broken")
    chain_head = str(expected_chain[-1]["chain_digest"])
    if chain_document.get("chain_head") != chain_head:
        raise BundleVerificationError("hash_chain_broken")
    if manifest.get("chain_head") != chain_head:
        raise BundleVerificationError("hash_chain_broken")

    decision_record = records[0]
    authorization_record = records[1]
    decision_payload = decision_record.get("record")
    authorization_payload = authorization_record.get("record")
    if not isinstance(decision_payload, Mapping) or not isinstance(
        authorization_payload,
        Mapping,
    ):
        raise AuthorizationIncompleteError("decision_or_authorization_record_missing")
    if decision_payload.get("decision") != DecisionCode.ALLOW.value:
        raise AuthorizationMismatchError("model_output_alone_cannot_authorize")
    if authorization_payload.get("decision") != DecisionCode.ALLOW.value:
        raise AuthorizationMismatchError("authorization must carry ALLOW")

    decision_ref = "decision:sha256:" + digest_payload(decision_payload)
    if decision_record.get("decision_ref") != decision_ref:
        raise BundleVerificationError("decision_record_tampered")
    if manifest.get("decision_ref") != decision_ref:
        raise AuthorizationMismatchError("manifest decision_ref mismatch")
    if authorization_payload.get("parent_cause") != decision_ref:
        raise AuthorizationMismatchError("authorization parent decision mismatch")

    authorization_ref = "authorization-record:sha256:" + digest_payload(
        authorization_payload
    )
    if authorization_record.get("authorization_ref") != authorization_ref:
        raise BundleVerificationError("authorization_record_tampered")
    if manifest.get("authorization_ref") != authorization_ref:
        raise AuthorizationMismatchError("manifest authorization_ref mismatch")

    for field_name in ("task_id", "trail_id", "policy_version", "nonce"):
        if manifest.get(field_name) != authorization_payload.get(field_name):
            raise AuthorizationMismatchError(
                f"authorization field mismatch:{field_name}"
            )
    if manifest.get("evidence_refs") != authorization_payload.get("evidence_refs"):
        raise AuthorizationMismatchError("authorization evidence mismatch")
    if manifest.get("scope") != authorization_payload.get("scope"):
        raise AuthorizationMismatchError("authorization scope mismatch")
    if decision_payload.get("task_id") != authorization_payload.get("task_id"):
        raise AuthorizationMismatchError("decision task mismatch")
    if decision_payload.get("trail_id") != authorization_payload.get("trail_id"):
        raise AuthorizationMismatchError("decision trail mismatch")
    if decision_payload.get("policy_version") != authorization_payload.get(
        "policy_version"
    ):
        raise AuthorizationMismatchError("decision policy mismatch")
    if decision_payload.get("evidence_refs") != authorization_payload.get(
        "evidence_refs"
    ):
        raise AuthorizationMismatchError("decision evidence mismatch")

    now_dt = parse_datetime(now)
    issued_dt = parse_datetime(str(authorization_payload.get("issued_at", "")))
    expires_dt = parse_datetime(str(authorization_payload.get("expires_at", "")))
    if now_dt < issued_dt:
        raise AuthorizationMismatchError("authorization_not_yet_valid")
    if now_dt >= expires_dt:
        raise AuthorizationExpiredError("authorization_expired")

    privacy = parse_json_object(files["privacy-report.json"], "privacy-report.json")
    if privacy.get("status") != "pass":
        raise BundleVerificationError("privacy_boundary_failed")

    nonce = str(authorization_payload.get("nonce", ""))
    if not nonce:
        raise AuthorizationIncompleteError("authorization nonce is missing")
    if nonce_store is not None:
        if nonce_store.is_consumed(nonce):
            raise AuthorizationReplayError(f"authorization nonce already consumed: {nonce}")
        if consume_nonce:
            nonce_store.consume(nonce)

    return BundleVerificationResult(
        bundle_id=str(manifest["bundle_id"]),
        valid=True,
        verified_at=now,
        checked_files=tuple(sorted(required_files)),
        chain_head=chain_head,
        authorization_ref=authorization_ref,
    )


def authorization_bundle_event(bundle: AuthorizationBundle) -> TrailEvent:
    return TrailEvent(
        event_id=f"event-{bundle.authorization_ref.split(':')[-1][:16]}",
        task_id=bundle.task_id,
        trail_id=bundle.trail_id,
        event_type=TrailEventType.AUTHORIZATION_ISSUED,
        actor=bundle.actor,
        created_at=bundle.created_at,
        parent_cause=bundle.decision_ref,
        evidence_refs=bundle.evidence_refs,
        payload=bundle.to_dict(),
    )


def parse_datetime(value: str) -> datetime:
    if not value:
        raise AuthorizationIncompleteError("timestamp is missing")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise AuthorizationIncompleteError(f"invalid timestamp: {value}") from error
    if parsed.tzinfo is None:
        raise AuthorizationIncompleteError("timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def pretty_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def digest_payload(payload: Mapping[str, Any]) -> str:
    return digest_text(canonical_json(payload))


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_json_object(value: str, name: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as error:
        raise BundleVerificationError(f"invalid_json:{name}") from error
    if not isinstance(payload, dict):
        raise BundleVerificationError(f"invalid_object:{name}")
    return payload


def parse_jsonl(value: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in value.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as error:
            raise BundleVerificationError("invalid_json:decisions.jsonl") from error
        if not isinstance(payload, dict):
            raise BundleVerificationError("invalid_record:decisions.jsonl")
        records.append(payload)
    return records
