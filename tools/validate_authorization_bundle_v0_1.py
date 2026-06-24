#!/usr/bin/env python3
"""Build and offline-verify LS portable authorization bundles v0.1."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures" / "authorization-bundle" / "manifest-v0.1.json"
OUTPUT = ROOT / "artifacts" / "authorization-bundle-v0.1-result.json"
VERSION = "ls.authorization_bundle.v0.1"
VERIFIER_VERSION = "ls.authorization_bundle_verifier_result.v0.1"
REQUIRED_PAYLOAD_FILES = {
    "decisions.jsonl",
    "hash-chain.json",
    "privacy-report.json",
    "README.md",
}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: JSON object required")
    return value


def text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pretty(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def digest_payload(value: object) -> str:
    return digest_text(canonical(value))


def parse_time(value: object) -> datetime:
    raw = text(value)
    if raw is None:
        raise ValueError("timestamp required")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed


def deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def unique_nonempty(values: object) -> bool:
    return (
        isinstance(values, list)
        and bool(values)
        and all(text(value) is not None for value in values)
        and len(values) == len(set(values))
    )


def rejected(reason: str, *, bundle_created: bool = False) -> dict[str, Any]:
    return {
        "outcome": "REJECTED",
        "reason_code": reason,
        "bundle_created": bundle_created,
        "offline_verified": False,
        "commit_before_effect_eligible": False,
        "execution_authorized": False,
    }


def validate_issuance(payload: Mapping[str, Any], consumed_nonces: set[str]) -> str | None:
    decision = payload.get("evidence_decision")
    intent = payload.get("authorization_intent")
    if not isinstance(decision, Mapping) or not isinstance(intent, Mapping):
        return "INTENT_INCOMPLETE"

    if decision.get("execution_authorized") is not False:
        return "UPSTREAM_EXECUTION_AUTHORITY_INVALID"
    if decision.get("decision") != "ALLOW":
        return "EVIDENCE_GATE_NOT_ALLOW"
    if decision.get("authorization_bundle_eligible") is not True:
        return "DECISION_NOT_BUNDLE_ELIGIBLE"
    if text(decision.get("result_ref")) is None:
        return "EVIDENCE_RESULT_REF_MISSING"

    required_intent = (
        "intent_id",
        "task_id",
        "trail_id",
        "actor",
        "action_ref",
        "issued_at",
        "expires_at",
        "nonce",
        "candidate_digest",
        "intent_digest",
        "target_state_digest",
        "policy_id",
        "policy_version",
        "evidence_snapshot_digest",
        "parent_cause",
    )
    if any(text(intent.get(key)) is None for key in required_intent):
        return "INTENT_INCOMPLETE"
    if not unique_nonempty(intent.get("scope")):
        return "INTENT_INCOMPLETE"
    if not unique_nonempty(intent.get("evidence_refs")):
        return "INTENT_INCOMPLETE"
    if not unique_nonempty(intent.get("causal_audit_refs")):
        return "INTENT_INCOMPLETE"

    if intent.get("candidate_digest") != decision.get("candidate_digest"):
        return "CANDIDATE_BINDING_MISMATCH"
    if (
        intent.get("intent_digest") != decision.get("intent_digest")
        or intent.get("target_state_digest") != decision.get("target_state_digest")
    ):
        return "CONTEXT_BINDING_MISMATCH"
    if (
        intent.get("policy_id") != decision.get("policy_id")
        or intent.get("policy_version") != decision.get("policy_version")
    ):
        return "POLICY_BINDING_MISMATCH"
    if (
        intent.get("evidence_refs") != decision.get("evidence_refs")
        or intent.get("evidence_snapshot_digest")
        != decision.get("evidence_snapshot_digest")
    ):
        return "EVIDENCE_BINDING_MISMATCH"
    if intent.get("causal_audit_refs") != decision.get("causal_audit_refs"):
        return "CAUSAL_BINDING_MISMATCH"
    if intent.get("parent_cause") != decision.get("result_ref"):
        return "PARENT_CAUSE_MISMATCH"

    try:
        issued = parse_time(intent.get("issued_at"))
        expires = parse_time(intent.get("expires_at"))
        current = parse_time(payload.get("current_time"))
    except (TypeError, ValueError):
        return "INVALID_TIME_WINDOW"
    if expires <= issued:
        return "INVALID_TIME_WINDOW"
    if current > expires:
        return "AUTHORIZATION_EXPIRED"
    if intent.get("nonce") in consumed_nonces:
        return "NONCE_REPLAY"
    return None


def build_hash_chain(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    chain: list[dict[str, Any]] = []
    previous: str | None = None
    for sequence, record in enumerate(records):
        link = {
            "sequence": sequence,
            "record_type": record.get("record_type"),
            "record_digest": digest_payload(record),
            "previous_chain_digest": previous,
        }
        link["chain_digest"] = digest_payload(link)
        chain.append(link)
        previous = link["chain_digest"]
    return chain


def build_bundle(payload: Mapping[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    decision = copy.deepcopy(dict(payload["evidence_decision"]))
    intent = copy.deepcopy(dict(payload["authorization_intent"]))
    decision_ref = str(decision["result_ref"])
    authorization_ref = "authorization-record:sha256:" + digest_payload(
        {"decision_ref": decision_ref, "intent": intent}
    )
    records = [
        {
            "record_type": "evidence_decision",
            "decision_ref": decision_ref,
            "record": decision,
        },
        {
            "record_type": "authorization_intent",
            "intent_ref": intent["intent_id"],
            "record": intent,
        },
        {
            "record_type": "bundle_issuance",
            "authorization_ref": authorization_ref,
            "parent_cause": decision_ref,
            "decision": "ALLOW",
            "commit_before_effect_eligible": True,
            "execution_authorized": False,
        },
    ]
    chain = build_hash_chain(records)
    chain_head = str(chain[-1]["chain_digest"])
    bundle_id = "ls-bundle-" + chain_head[:20]

    payload_files = {
        "decisions.jsonl": "".join(canonical(record) + "\n" for record in records),
        "hash-chain.json": pretty(
            {
                "schema_version": "ls.authorization_hash_chain.v0.1",
                "bundle_id": bundle_id,
                "chain_head": chain_head,
                "entries": chain,
            }
        ),
        "privacy-report.json": pretty(
            {
                "schema_version": "ls.authorization_privacy_report.v0.1",
                "bundle_id": bundle_id,
                "status": "pass",
                "included_fields": [
                    "identifiers",
                    "scope",
                    "policy",
                    "evidence_references",
                    "causal_references",
                    "decision",
                    "expiry",
                    "nonce",
                ],
                "excluded_fields": [
                    "prompts",
                    "raw_model_output",
                    "credentials",
                    "private_task_content",
                    "unnecessary_personal_data",
                    "payment_data",
                ],
            }
        ),
        "README.md": (
            "# LS portable authorization bundle v0.1\n\n"
            "Verify non-manifest file hashes, rebuild the ordered hash chain, "
            "match decision and intent bindings, check expiry and nonce state, "
            "then pass a valid bundle to a separate commit-before-effect gate.\n\n"
            "This bundle does not authorize execution.\n"
        ),
    }
    file_hashes = {
        name: digest_text(content) for name, content in payload_files.items()
    }
    manifest = {
        "schema_version": VERSION,
        "bundle_id": bundle_id,
        "adapter": "ls-proofpath-style",
        "actor": intent["actor"],
        "created_at": intent["issued_at"],
        "expires_at": intent["expires_at"],
        "intent_ref": intent["intent_id"],
        "decision_ref": decision_ref,
        "authorization_ref": authorization_ref,
        "task_id": intent["task_id"],
        "trail_id": intent["trail_id"],
        "action_ref": intent["action_ref"],
        "candidate_digest": intent["candidate_digest"],
        "intent_digest": intent["intent_digest"],
        "target_state_digest": intent["target_state_digest"],
        "policy_id": intent["policy_id"],
        "policy_version": intent["policy_version"],
        "nonce": intent["nonce"],
        "scope": intent["scope"],
        "evidence_refs": intent["evidence_refs"],
        "evidence_snapshot_digest": intent["evidence_snapshot_digest"],
        "causal_audit_refs": intent["causal_audit_refs"],
        "chain_head": chain_head,
        "file_hashes": file_hashes,
        "file_names": sorted(
            ["manifest.json", "verifier-result.json", *payload_files.keys()]
        ),
        "verification_instructions": [
            "Verify every non-manifest payload hash.",
            "Rebuild the ordered decision hash chain.",
            "Match candidate, context, policy, evidence, and causal bindings.",
            "Reject expired or previously consumed nonces.",
        ],
        "commit_before_effect_eligible": True,
        "execution_authorized": False,
    }
    files = dict(payload_files)
    files["manifest.json"] = pretty(manifest)
    return files, manifest


def verify_bundle(
    files: dict[str, str],
    *,
    current_time: str,
    consumed_nonces: set[str],
) -> tuple[str | None, dict[str, Any] | None]:
    required = {"manifest.json", *REQUIRED_PAYLOAD_FILES}
    if not required.issubset(files):
        return "BUNDLE_INCOMPLETE", None
    try:
        manifest = json.loads(files["manifest.json"])
        chain_file = json.loads(files["hash-chain.json"])
        privacy = json.loads(files["privacy-report.json"])
    except (TypeError, ValueError, json.JSONDecodeError):
        return "BUNDLE_MALFORMED", None
    if not isinstance(manifest, dict) or manifest.get("schema_version") != VERSION:
        return "BUNDLE_SCHEMA_INVALID", None
    if manifest.get("execution_authorized") is not False:
        return "BUNDLE_EXECUTION_AUTHORITY_INVALID", None
    if manifest.get("commit_before_effect_eligible") is not True:
        return "BUNDLE_ELIGIBILITY_INVALID", None

    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or set(hashes) != REQUIRED_PAYLOAD_FILES:
        return "BUNDLE_INCOMPLETE", None
    for name, expected_hash in hashes.items():
        if name not in files or digest_text(files[name]) != expected_hash:
            return "FILE_HASH_MISMATCH", None

    try:
        records = [json.loads(line) for line in files["decisions.jsonl"].splitlines() if line]
    except json.JSONDecodeError:
        return "DECISIONS_MALFORMED", None
    if len(records) != 3 or [item.get("record_type") for item in records] != [
        "evidence_decision",
        "authorization_intent",
        "bundle_issuance",
    ]:
        return "DECISION_ORDER_INVALID", None
    rebuilt_chain = build_hash_chain(records)
    if not isinstance(chain_file, dict) or chain_file.get("entries") != rebuilt_chain:
        return "HASH_CHAIN_MISMATCH", None
    if chain_file.get("chain_head") != manifest.get("chain_head"):
        return "CHAIN_HEAD_MISMATCH", None
    if rebuilt_chain[-1].get("chain_digest") != manifest.get("chain_head"):
        return "CHAIN_HEAD_MISMATCH", None

    decision = records[0].get("record")
    intent = records[1].get("record")
    issuance = records[2]
    if not isinstance(decision, dict) or not isinstance(intent, dict):
        return "DECISIONS_MALFORMED", None
    if decision.get("decision") != "ALLOW" or decision.get("authorization_bundle_eligible") is not True:
        return "EVIDENCE_GATE_NOT_ALLOW", None
    if decision.get("execution_authorized") is not False:
        return "UPSTREAM_EXECUTION_AUTHORITY_INVALID", None
    if issuance.get("execution_authorized") is not False:
        return "BUNDLE_EXECUTION_AUTHORITY_INVALID", None
    if issuance.get("parent_cause") != decision.get("result_ref"):
        return "PARENT_CAUSE_MISMATCH", None
    if issuance.get("authorization_ref") != manifest.get("authorization_ref"):
        return "AUTHORIZATION_REF_MISMATCH", None

    exact_bindings = {
        "candidate_digest": decision.get("candidate_digest"),
        "intent_digest": decision.get("intent_digest"),
        "target_state_digest": decision.get("target_state_digest"),
        "policy_id": decision.get("policy_id"),
        "policy_version": decision.get("policy_version"),
        "evidence_refs": decision.get("evidence_refs"),
        "evidence_snapshot_digest": decision.get("evidence_snapshot_digest"),
        "causal_audit_refs": decision.get("causal_audit_refs"),
    }
    for key, expected in exact_bindings.items():
        if intent.get(key) != expected or manifest.get(key) != expected:
            return "OFFLINE_BINDING_MISMATCH", None
    if manifest.get("decision_ref") != decision.get("result_ref"):
        return "OFFLINE_BINDING_MISMATCH", None
    if manifest.get("intent_ref") != intent.get("intent_id"):
        return "OFFLINE_BINDING_MISMATCH", None
    if manifest.get("nonce") != intent.get("nonce"):
        return "OFFLINE_BINDING_MISMATCH", None

    try:
        current = parse_time(current_time)
        expires = parse_time(intent.get("expires_at"))
    except (TypeError, ValueError):
        return "INVALID_TIME_WINDOW", None
    if current > expires:
        return "AUTHORIZATION_EXPIRED", None
    if intent.get("nonce") in consumed_nonces:
        return "NONCE_REPLAY", None

    required_excluded = {
        "prompts",
        "raw_model_output",
        "credentials",
        "private_task_content",
        "unnecessary_personal_data",
        "payment_data",
    }
    if (
        not isinstance(privacy, dict)
        or privacy.get("status") != "pass"
        or not required_excluded.issubset(set(privacy.get("excluded_fields", [])))
    ):
        return "PRIVACY_REPORT_INVALID", None

    verifier = {
        "schema_version": VERIFIER_VERSION,
        "bundle_id": manifest["bundle_id"],
        "valid": True,
        "verified_at": current_time,
        "checked_files": sorted(required),
        "chain_head": manifest["chain_head"],
        "authorization_ref": manifest["authorization_ref"],
        "reason_codes": [],
        "commit_before_effect_eligible": True,
        "execution_authorized": False,
    }
    files["verifier-result.json"] = pretty(verifier)
    return None, verifier


def run_case(base: Mapping[str, Any], case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    overrides = case.get("overrides", {})
    if not isinstance(overrides, Mapping):
        raise ValueError("case overrides must be an object")
    payload = deep_merge(base, overrides)
    consumed = case.get("consumed_nonces", [])
    if not isinstance(consumed, list) or any(text(item) is None for item in consumed):
        raise ValueError("consumed_nonces must be a string list")
    consumed_set = set(consumed)

    reason = validate_issuance(payload, consumed_set)
    if reason is not None:
        return rejected(reason), None

    files, manifest = build_bundle(payload)
    tamper = case.get("tamper")
    if tamper is not None:
        if not isinstance(tamper, Mapping):
            raise ValueError("tamper must be null or an object")
        name = text(tamper.get("file"))
        append = tamper.get("append")
        if name is None or name not in files or not isinstance(append, str):
            raise ValueError("invalid tamper instruction")
        files[name] = files[name] + append

    verify_reason, verifier = verify_bundle(
        files,
        current_time=str(payload["current_time"]),
        consumed_nonces=consumed_set,
    )
    if verify_reason is not None:
        return rejected(verify_reason, bundle_created=True), manifest
    if verifier is None:
        raise AssertionError("verified bundle missing verifier result")
    return {
        "outcome": "ISSUED_AND_VERIFIED",
        "reason_code": "BUNDLE_VERIFIED",
        "bundle_created": True,
        "offline_verified": True,
        "commit_before_effect_eligible": True,
        "execution_authorized": False,
    }, manifest


def validate(manifest_path: Path) -> dict[str, Any]:
    fixture = load(manifest_path)
    if fixture.get("contract_version") != VERSION:
        raise ValueError("manifest contract version mismatch")
    base = fixture.get("base")
    names = fixture.get("cases")
    if not isinstance(base, dict):
        raise ValueError("manifest base must be an object")
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise ValueError("manifest cases must be a unique non-empty list")

    results = []
    reasons: set[str] = set()
    outcomes: set[str] = set()
    seen: set[str] = set()
    for filename in names:
        if not isinstance(filename, str) or not filename.endswith(".json"):
            raise ValueError(f"invalid case filename: {filename!r}")
        case = load(manifest_path.parent / filename)
        name = text(case.get("case"))
        expected = case.get("expected")
        if name is None or name in seen or not isinstance(expected, dict):
            raise ValueError(f"{filename}: invalid case metadata")
        seen.add(name)
        observed, bundle_manifest = run_case(base, case)
        errors = []
        if observed != expected:
            errors.append("observed result differs from expected")
        if observed["execution_authorized"] is not False:
            errors.append("bundle flow authorized execution")
        if observed["outcome"] != "ISSUED_AND_VERIFIED" and observed["commit_before_effect_eligible"]:
            errors.append("rejected bundle became commit eligible")
        if observed["offline_verified"] and not observed["bundle_created"]:
            errors.append("unbuilt bundle marked verified")
        reasons.add(observed["reason_code"])
        outcomes.add(observed["outcome"])
        results.append(
            {
                "case": name,
                "file": filename,
                "passed": not errors,
                "errors": errors,
                "observed": observed,
                "expected": expected,
                "bundle_manifest": bundle_manifest,
            }
        )

    required_cases = {
        "valid_bundle",
        "non_allow_decision",
        "expired_intent",
        "replayed_nonce",
        "candidate_binding_mismatch",
        "policy_binding_mismatch",
        "evidence_binding_mismatch",
        "tampered_payload",
    }
    if seen != required_cases:
        raise ValueError(f"case set mismatch: {sorted(required_cases - seen)}")
    required_reasons = {
        "BUNDLE_VERIFIED",
        "EVIDENCE_GATE_NOT_ALLOW",
        "AUTHORIZATION_EXPIRED",
        "NONCE_REPLAY",
        "CANDIDATE_BINDING_MISMATCH",
        "POLICY_BINDING_MISMATCH",
        "EVIDENCE_BINDING_MISMATCH",
        "FILE_HASH_MISMATCH",
    }
    report = {
        "contract_version": VERSION,
        "cases_total": len(results),
        "cases_passed": sum(bool(item["passed"]) for item in results),
        "outcomes_covered": sorted(outcomes),
        "reason_codes_covered": sorted(reasons),
        "portable_files": sorted(
            ["manifest.json", "decisions.jsonl", "hash-chain.json", "privacy-report.json", "README.md", "verifier-result.json"]
        ),
        "boundary": {
            "evidence_allow_is_execution_authority": False,
            "bundle_verification_is_execution_authority": False,
            "offline_verification_requires_model": False,
            "nonce_replay_allowed": False,
            "tampered_bundle_allowed": False,
        },
        "results": results,
    }
    report["passed"] = (
        report["cases_passed"] == report["cases_total"]
        and outcomes == {"ISSUED_AND_VERIFIED", "REJECTED"}
        and required_reasons.issubset(reasons)
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", nargs="?", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = validate(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(pretty(report), encoding="utf-8")
    print(pretty(report), end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
