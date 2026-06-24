#!/usr/bin/env python3
"""Run the modern-main LS Trusted PR Review MVP v0.2 end to end."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCENARIOS = ROOT / "fixtures" / "trusted-pr-review" / "scenarios-v0.1.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "trusted-pr-review-mvp-v0.2"
VERSION = "ls.trusted_pr_review_mvp.v0.2"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pretty(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: top-level JSON object required")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pretty(value), encoding="utf-8")


def load_module(name: str, relative_path: str) -> ModuleType:
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def stage_event(
    *,
    event_id: str,
    event_type: str,
    created_at: str,
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "created_at": created_at,
        "payload": copy.deepcopy(dict(payload)),
    }


class Runtime:
    def __init__(self) -> None:
        self.orientation = load_module(
            "ls_e2e_orientation", "tools/evaluate_orientation_triad.py"
        )
        self.recognition = load_module(
            "ls_e2e_recognition", "tools/validate_recognition_gate_v0_1.py"
        )
        self.handoff = load_module(
            "ls_e2e_handoff",
            "tools/validate_recognition_evidence_handoff_v0_1.py",
        )
        self.evidence = load_module(
            "ls_e2e_evidence", "tools/validate_evidence_gate_v0_1.py"
        )
        self.authorization = load_module(
            "ls_e2e_authorization",
            "tools/validate_authorization_bundle_v0_1.py",
        )
        self.execution = load_module(
            "ls_e2e_execution", "tools/validate_commit_before_effect_v0_1.py"
        )
        self.outcome = load_module(
            "ls_e2e_outcome", "tools/evaluate_outcome_verification.py"
        )
        self.replay = load_module(
            "ls_e2e_replay", "tools/validate_replay_persistence_v0_1.py"
        )


class PortableReviewEffect:
    """Cross-platform wrapper around the shipped idempotent reference effect."""

    def __init__(self, runtime: Runtime, root: Path, journal: Any) -> None:
        base = runtime.execution.IdempotentReviewEffect

        class _Portable(base):
            def _target(self, execution_id: str) -> Path:  # type: ignore[override]
                filename = hashlib.sha256(execution_id.encode("utf-8")).hexdigest()
                return self.root / f"{filename}.effect.json"

        self.instance = _Portable(root, journal)


def orientation_case(
    task: Mapping[str, Any], candidate_digest: str, scenario_id: str
) -> dict[str, Any]:
    common = {
        "workspace_id": task["workspace_id"],
        "trajectory_id": task["trajectory_id"],
        "continuation_id": task["continuation_id"],
        "action_digest": candidate_digest,
    }
    relationship = {
        "relationship_id": task["relationship_id"],
        "actor_id": task["actor_id"],
        "action_digest": candidate_digest,
    }
    return {
        "fixture_id": f"trusted-pr-review:{scenario_id}:orientation",
        "toc": {
            "center_version": "temporal-orientation-v0.1",
            "verdict": "RESUME",
            "reason_code": "CURRENT_CONTINUATION_VALID",
            "bindings": common,
            "execution_authorized": False,
            "downstream_gates_required": True,
        },
        "rtoc": {
            "center_version": "relational-temporal-orientation-v0.1",
            "verdict": "RESUME",
            "reason_code": "RELATIONSHIP_VALID",
            "bindings": relationship,
            "execution_authorized": False,
            "downstream_gates_required": True,
        },
        "patoc": {
            "center_version": "precise-action-temporal-orientation-v0.1",
            "verdict": "EXECUTE_CANDIDATE",
            "reason_code": "EXACT_ACTION_CURRENT",
            "bindings": {**common, **relationship},
            "execution_authorized": False,
            "downstream_gates_required": True,
        },
    }


def make_outcome_case(
    *,
    execution_record: Mapping[str, Any],
    action: Mapping[str, Any],
    effect_path: Path,
) -> dict[str, Any]:
    state_digest = sha256_bytes(effect_path.read_bytes())
    execution_id = str(execution_record["execution_id"])
    action_digest = str(execution_record["action_digest"])
    action_id = str(action["action_id"])
    side_effect_key = str(action["idempotency_key"])
    receipt_id = "receipt:" + hashlib.sha256(
        f"{execution_id}:{state_digest}".encode("utf-8")
    ).hexdigest()
    receipt_digest = sha256_text(effect_path.read_text(encoding="utf-8"))
    scope_digest = sha256_text(canonical(action["scope"]))

    return {
        "fixture_id": "trusted-pr-review:expected-outcome",
        "verification": {
            "verification_version": "outcome-verification-v0.1",
            "execution_identity": {
                "execution_id": execution_id,
                "action_id": action_id,
                "action_digest": action_digest,
                "actor_id": "runtime:ls",
                "target_id": effect_path.name,
                "side_effect_key": side_effect_key,
            },
            "expected_outcome": {
                "pre_state_digest": sha256_text("absent"),
                "expected_state_digest": state_digest,
                "consistency_window_until": "2026-06-25T18:15:00Z",
                "verification_deadline_at": "2026-06-25T18:30:00Z",
            },
            "evidence_contract": {
                "required_evidence_kinds": ["state_digest", "external_receipt"],
                "min_independent_observers": 2,
                "required_observer_scope_digest": scope_digest,
                "allow_receipt_only": False,
            },
            "execution_receipt": {
                "receipt_id": receipt_id,
                "receipt_digest": receipt_digest,
                "execution_id": execution_id,
                "action_id": action_id,
                "action_digest": action_digest,
                "side_effect_key": side_effect_key,
                "status": "completed",
                "issued_at": "2026-06-25T18:05:00Z",
                "issuer_id": "ls-local-runtime",
            },
            "observations": [
                {
                    "observation_id": "observation:local-state",
                    "observer_id": "ls-state-reader",
                    "observer_type": "state_store",
                    "independent": True,
                    "authority_scope_digest": scope_digest,
                    "observed_at": "2026-06-25T18:06:00Z",
                    "state_digest": state_digest,
                    "evidence_kind": "state_digest",
                    "evidence_digest": sha256_text("local-state:" + state_digest),
                    "outcome_status": "complete",
                },
                {
                    "observation_id": "observation:effect-receipt",
                    "observer_id": "ls-receipt-reader",
                    "observer_type": "external_system",
                    "independent": True,
                    "authority_scope_digest": scope_digest,
                    "observed_at": "2026-06-25T18:07:00Z",
                    "state_digest": state_digest,
                    "evidence_kind": "external_receipt",
                    "evidence_digest": sha256_text("effect-receipt:" + receipt_digest),
                    "outcome_status": "complete",
                },
            ],
            "provenance": {
                "causal_trace_id": str(execution_record["authorization_ref"]),
                "source_event_ids": [
                    "event:execution-committed",
                    "event:execution-completed",
                ],
            },
        },
        "authoritative_state": {
            "expected_execution_id": execution_id,
            "expected_action_id": action_id,
            "expected_action_digest": action_digest,
            "expected_side_effect_key": side_effect_key,
            "expected_state_digest": state_digest,
            "trusted_receipt_issuers": ["ls-local-runtime"],
            "seen_receipt_ids": [],
            "seen_evidence_digests": [],
            "required_observer_scope_digest": scope_digest,
            "required_evidence_kinds": ["state_digest", "external_receipt"],
            "min_independent_observers": 2,
            "current_time": "2026-06-25T18:10:00Z",
        },
    }


def persist_events(
    runtime: Runtime,
    scenario_dir: Path,
    trail_id: str,
    templates: Sequence[Mapping[str, Any]],
    *,
    terminal_status: str,
    terminal_reason: str,
) -> dict[str, Any]:
    sensitive_keys = {
        "credentials",
        "private_task_content",
        "prompt",
        "raw_model_output",
        "payment_data",
        "secret",
        "token",
    }
    store = runtime.replay.JsonlEventStore(
        scenario_dir / "events" / "trail.jsonl",
        trail_id,
        sensitive_keys,
    )
    for template in templates:
        outcome = store.append(template)
        require(outcome == "APPENDED", "unexpected non-new E2E event")

    scan = runtime.replay.scan_integrity(store.path, trail_id)
    require(scan.valid, f"durable event stream failed integrity: {scan.reason_code}")
    baseline = {
        str(event["event_id"]): str(event["source_payload_digest"])
        for event in scan.valid_events
    }
    semantic, checkpoint = runtime.replay.semantic_replay(
        trail_id,
        scan,
        baseline,
        append_conflict=False,
    )

    if terminal_status == "BLOCK":
        semantic = {
            "classification": "REJECTED",
            "reason_code": terminal_reason,
            "completion_state": "INVALID",
            "resume_allowed": False,
        }
        checkpoint = None

    return {
        "classification": semantic["classification"],
        "reason_code": semantic["reason_code"],
        "completion_state": semantic["completion_state"],
        "resume_allowed": semantic["resume_allowed"],
        "integrity_valid": scan.valid,
        "valid_prefix_events": len(scan.valid_events),
        "chain_head": scan.chain_head,
        "checkpoint": checkpoint,
        "event_stream": relative(store.path, scenario_dir),
        "redactions_applied": store.redactions_applied,
        "model_calls": 0,
        "tool_calls": 0,
        "effect_calls": 0,
    }


def markdown_summary(result: Mapping[str, Any]) -> str:
    lines = [
        f"# Trusted PR Review v0.2 — {result['scenario_id']}",
        "",
        f"**Final status:** `{result['final_status']}`  ",
        f"**Stop reason:** `{result['stop_reason']}`  ",
        f"**Protected effect written:** `{str(result['protected_effect_written']).lower()}`  ",
        f"**Replay:** `{result['replay']['classification']}` / `{result['replay']['completion_state']}`",
        "",
        "## Stage decisions",
        "",
    ]
    for stage in result["stage_records"]:
        decision = (
            stage.get("decision")
            or stage.get("verdict")
            or stage.get("handoff_outcome")
            or stage.get("state")
        )
        reason = stage.get("reason_code") or stage.get("decision_code")
        lines.append(f"- **{stage['stage']}** — `{decision}` ({reason})")
    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "Model output is proposal data, not authorization. Non-ALLOW paths never reach the protected effect. Replay never reruns models, tools, or effects.",
            "",
        ]
    )
    return "\n".join(lines)


def run_scenario(
    runtime: Runtime,
    config: Mapping[str, Any],
    scenario: Mapping[str, Any],
    output_root: Path,
) -> dict[str, Any]:
    scenario_id = str(scenario["scenario_id"])
    task = copy.deepcopy(dict(config["task"]))
    roles = copy.deepcopy(list(config["roles"]))
    diff_path = ROOT / str(config["diff_path"])
    diff_text = diff_path.read_text(encoding="utf-8")
    candidate_digest = sha256_text(diff_text)
    intent_digest = sha256_text(canonical({"task": task, "intent": "trusted PR review"}))
    target_state_digest = sha256_text(
        canonical({"artifact": "trusted-pr-review", "scenario": scenario_id})
    )

    scenario_dir = output_root / scenario_id
    if scenario_dir.exists():
        shutil.rmtree(scenario_dir)
    scenario_dir.mkdir(parents=True)

    stages: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = [
        stage_event(
            event_id="event:task-accepted",
            event_type="TASK_ACCEPTED",
            created_at="2026-06-25T18:00:00Z",
            payload={
                "task_id": task["task_id"],
                "diff_digest": candidate_digest,
                "private_task_content": "deterministic fixture review",
            },
        )
    ]

    orientation = runtime.orientation.evaluate(
        orientation_case(task, candidate_digest, scenario_id)
    )
    require(
        orientation["verdict"] == "COORDINATED_ACTION_CANDIDATE",
        "orientation did not produce a coordinated candidate",
    )
    stages.append({"stage": "orientation", **orientation})
    events.append(
        stage_event(
            event_id="event:orientation-coordinated",
            event_type="ORIENTATION_COORDINATED",
            created_at="2026-06-25T18:00:01Z",
            payload=orientation,
        )
    )

    recognition_case_payload = {
        "context": {
            "intent_digest": intent_digest,
            "target_state_digest": target_state_digest,
        },
        "candidate": {
            "output_type": "tool_call",
            "dependencies": [],
            "caveat_repeated": False,
            "provisional": False,
        },
        "recognitions": [],
        "evidence": [],
    }
    recognition = runtime.recognition.evaluate(recognition_case_payload)
    recognition_result = {
        **recognition,
        "result_ref": f"recognition-result:{scenario_id}",
        "candidate_digest": candidate_digest,
        "intent_digest": intent_digest,
        "target_state_digest": target_state_digest,
    }
    require(recognition_result["decision"] == "ALLOW", "recognition did not allow")
    stages.append({"stage": "recognition", **recognition_result})
    events.append(
        stage_event(
            event_id="event:recognition-allowed",
            event_type="RECOGNITION_ALLOWED",
            created_at="2026-06-25T18:00:02Z",
            payload=recognition_result,
        )
    )

    handoff_case = {
        "context": {
            "intent_digest": intent_digest,
            "target_state_digest": target_state_digest,
        },
        "recognition_result": recognition_result,
        "candidate": {
            "candidate_digest": candidate_digest,
            "candidate_type": "tool_call",
            "effectful": True,
        },
        "claimed_downstream_eligible": True,
    }
    handoff_observed = runtime.handoff.evaluate(handoff_case)
    handoff = {
        **handoff_observed,
        "candidate_digest": candidate_digest,
        "intent_digest": intent_digest,
        "target_state_digest": target_state_digest,
        "recognition_result_ref": recognition_result["result_ref"],
    }
    require(
        handoff["handoff_outcome"] == "FORWARD_TO_EVIDENCE_GATE",
        "recognition handoff did not forward",
    )
    stages.append({"stage": "recognition_to_evidence", **handoff})

    evidence_mode = str(scenario["evidence_mode"])
    verifier_status = "VERIFIED" if evidence_mode == "verified" else "PENDING"
    evidence_refs = (
        ["evidence:fixture-tests", "evidence:causal-audit"]
        if evidence_mode == "verified"
        else []
    )
    evidence_case = {
        "handoff": handoff,
        "request": {
            "candidate_digest": candidate_digest,
            "intent_digest": intent_digest,
            "target_state_digest": target_state_digest,
            "policy_id": task["policy_id"],
            "policy_version": task["policy_version"],
            "causal_status": scenario["causal_status"],
            "verifier_status": verifier_status,
            "evidence_refs": evidence_refs,
            "evidence_snapshot_digest": (
                sha256_text(canonical(evidence_refs)) if evidence_refs else None
            ),
            "scope": task["scope"],
            "reversibility": "REVERSIBLE",
            "approval_required": False,
            "approval_ref": None,
        },
        "policy_context": {
            "policy_id": task["policy_id"],
            "policy_version": task["policy_version"],
        },
    }
    evidence = runtime.evidence.evaluate(evidence_case)
    evidence_record = {
        **evidence,
        "result_ref": f"evidence-gate-result:{scenario_id}",
        "evidence_snapshot_digest": evidence_case["request"].get(
            "evidence_snapshot_digest"
        ),
        "causal_audit_refs": ["evidence:causal-audit"],
    }
    stages.append({"stage": "evidence", **evidence_record})
    events.append(
        stage_event(
            event_id="event:evidence-decision",
            event_type="EVIDENCE_ALLOWED",
            created_at="2026-06-25T18:00:03Z",
            payload=evidence_record,
        )
    )

    final_status = "HOLD" if evidence["decision"] == "HOLD" else "BLOCK"
    stop_reason = str(evidence["reason_code"])
    authorization_result: dict[str, Any] | None = None
    execution_record: dict[str, Any] | None = None
    outcome_result: dict[str, Any] | None = None
    protected_effect: Path | None = None
    artifact_core: dict[str, Any] | None = None

    if evidence["decision"] == "ALLOW":
        expired = scenario["authorization_mode"] == "expired"
        current_time = "2026-06-25T18:00:00Z"
        expires_at = (
            "2026-06-25T17:59:00Z"
            if expired
            else "2026-06-25T18:30:00Z"
        )
        auth_payload = {
            "current_time": current_time,
            "evidence_decision": {
                "result_ref": evidence_record["result_ref"],
                "decision": evidence["decision"],
                "authorization_bundle_eligible": evidence[
                    "authorization_bundle_eligible"
                ],
                "execution_authorized": False,
                "candidate_digest": candidate_digest,
                "intent_digest": intent_digest,
                "target_state_digest": target_state_digest,
                "evidence_refs": evidence_refs,
                "evidence_snapshot_digest": evidence_record[
                    "evidence_snapshot_digest"
                ],
                "policy_id": task["policy_id"],
                "policy_version": task["policy_version"],
                "causal_audit_refs": evidence_record["causal_audit_refs"],
            },
            "authorization_intent": {
                "intent_id": f"intent:{scenario_id}",
                "task_id": task["task_id"],
                "trail_id": task["trail_id"],
                "actor": "human:repository-owner",
                "action_ref": task["action_ref"],
                "scope": task["scope"],
                "issued_at": "2026-06-25T17:55:00Z",
                "expires_at": expires_at,
                "nonce": f"nonce:{scenario_id}",
                "candidate_digest": candidate_digest,
                "intent_digest": intent_digest,
                "target_state_digest": target_state_digest,
                "policy_id": task["policy_id"],
                "policy_version": task["policy_version"],
                "evidence_refs": evidence_refs,
                "evidence_snapshot_digest": evidence_record[
                    "evidence_snapshot_digest"
                ],
                "causal_audit_refs": evidence_record["causal_audit_refs"],
                "parent_cause": evidence_record["result_ref"],
            },
        }
        auth_reason = runtime.authorization.validate_issuance(auth_payload, set())
        if auth_reason is not None:
            final_status = "BLOCK"
            stop_reason = str(auth_reason)
            authorization_result = {
                "issued": False,
                "verified": False,
                "reason_code": auth_reason,
                "execution_authorized": False,
            }
            stages.append({"stage": "authorization", **authorization_result})
            events.append(
                stage_event(
                    event_id="event:authorization-rejected",
                    event_type="AUTHORIZATION_REJECTED",
                    created_at="2026-06-25T18:00:04Z",
                    payload=authorization_result,
                )
            )
        else:
            bundle_files, bundle_manifest = runtime.authorization.build_bundle(
                auth_payload
            )
            verify_reason, verifier_result = runtime.authorization.verify_bundle(
                bundle_files,
                current_time=current_time,
                consumed_nonces=set(),
            )
            require(verify_reason is None, f"bundle verification failed: {verify_reason}")
            require(verifier_result is not None, "bundle verifier result missing")
            bundle_dir = scenario_dir / "authorization-bundle"
            for name, content in bundle_files.items():
                target = bundle_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            authorization_result = {
                "issued": True,
                "verified": True,
                "reason_code": "BUNDLE_VERIFIED",
                "bundle_id": bundle_manifest["bundle_id"],
                "authorization_ref": bundle_manifest["authorization_ref"],
                "verifier_result_ref": verifier_result["authorization_ref"],
                "commit_before_effect_eligible": True,
                "execution_authorized": False,
            }
            stages.append({"stage": "authorization", **authorization_result})
            events.append(
                stage_event(
                    event_id="event:authorization-verified",
                    event_type="AUTHORIZATION_VERIFIED",
                    created_at="2026-06-25T18:00:04Z",
                    payload=authorization_result,
                )
            )

            verified_bundle = {
                "bundle_id": bundle_manifest["bundle_id"],
                "authorization_ref": bundle_manifest["authorization_ref"],
                "verifier_result_ref": verifier_result["authorization_ref"],
                "valid": True,
                "commit_before_effect_eligible": True,
                "execution_authorized": False,
                "task_id": task["task_id"],
                "trail_id": task["trail_id"],
                "action_ref": task["action_ref"],
                "candidate_digest": candidate_digest,
                "policy_id": task["policy_id"],
                "policy_version": task["policy_version"],
                "nonce": f"nonce:{scenario_id}",
                "scope": task["scope"],
                "expires_at": expires_at,
            }
            action = {
                "action_id": f"action:{scenario_id}",
                "action_ref": task["action_ref"],
                "candidate_digest": candidate_digest,
                "scope": task["scope"],
                "payload": {
                    "review_status": "approved",
                    "summary": "The fixture adds explicit empty-title validation.",
                    "findings": [
                        {
                            "severity": "info",
                            "message": "Behavior is deterministic and covered by evidence fixtures.",
                        }
                    ],
                },
                "idempotency_key": f"trusted-pr-review:{scenario_id}",
                "requested_at": "2026-06-25T18:00:00Z",
                "mature_after": None,
                "expires_at": "2026-06-25T18:25:00Z",
            }
            journal = runtime.execution.AtomicExecutionJournal(
                scenario_dir / "internal" / "execution-journal.json"
            )
            portable_effect = PortableReviewEffect(
                runtime,
                scenario_dir / "protected",
                journal,
            ).instance
            controller = runtime.execution.CommitBeforeEffectController(
                journal, portable_effect
            )
            record, reused, recovery_mode = controller.run(
                verified_bundle,
                action,
                now="2026-06-25T18:05:00Z",
                preconditions_met=True,
            )
            require(record["state"] == "EXECUTED", "protected action did not execute")
            require(portable_effect.execute_calls == 1, "effect call count is not one")
            effect_files = sorted((scenario_dir / "protected").glob("*.effect.json"))
            require(len(effect_files) == 1, "protected effect file count is not one")
            protected_effect = effect_files[0]
            execution_record = copy.deepcopy(record)
            execution_record["reused_receipt"] = reused
            execution_record["recovery_mode"] = recovery_mode
            stages.append({"stage": "execution", **execution_record})
            events.extend(
                [
                    stage_event(
                        event_id="event:execution-committed",
                        event_type="EXECUTION_COMMITTED",
                        created_at="2026-06-25T18:05:00Z",
                        payload={
                            "execution_id": record["execution_id"],
                            "state": "COMMITTED",
                            "authorization_ref": record["authorization_ref"],
                            "effect_attempted": False,
                            "execution_authorized": True,
                        },
                    ),
                    stage_event(
                        event_id="event:execution-completed",
                        event_type="EXECUTION_COMPLETED",
                        created_at="2026-06-25T18:05:01Z",
                        payload={
                            "execution_id": record["execution_id"],
                            "state": record["state"],
                            "effect_ref": record["effect_ref"],
                            "effect_attempted": record["effect_attempted"],
                            "effect_succeeded": record["effect_succeeded"],
                        },
                    ),
                ]
            )

            outcome_case = make_outcome_case(
                execution_record=record,
                action=action,
                effect_path=protected_effect,
            )
            outcome_result = runtime.outcome.evaluate(outcome_case)
            require(
                outcome_result["verdict"] == "VERIFIED",
                f"outcome was not verified: {outcome_result['reason_code']}",
            )
            stages.append({"stage": "outcome_verification", **outcome_result})
            final_status = "VERIFIED"
            stop_reason = str(outcome_result["reason_code"])

            artifact_core = {
                "schema_version": VERSION,
                "scenario_id": scenario_id,
                "task": task,
                "input": {
                    "diff_path": str(config["diff_path"]),
                    "diff_digest": candidate_digest,
                    "intent_digest": intent_digest,
                    "target_state_digest": target_state_digest,
                },
                "route": {
                    "orientation": orientation,
                    "recognition": recognition_result,
                    "handoff": handoff,
                },
                "contributions": roles,
                "evidence": evidence_record,
                "authorization": authorization_result,
                "execution": execution_record,
                "outcome": outcome_result,
                "protected_effect_ref": relative(protected_effect, scenario_dir),
            }
            core_digest = sha256_text(canonical(artifact_core))
            events.append(
                stage_event(
                    event_id="event:artifact-exported",
                    event_type="ARTIFACT_EXPORTED",
                    created_at="2026-06-25T18:10:01Z",
                    payload={
                        "artifact_ref": f"artifact:{scenario_id}",
                        "artifact_digest": core_digest,
                        "outcome_verdict": outcome_result["verdict"],
                        "raw_model_output": "excluded-from-durable-artifact",
                    },
                )
            )

    replay_result = persist_events(
        runtime,
        scenario_dir,
        str(task["trail_id"]) + ":" + scenario_id,
        events,
        terminal_status=final_status,
        terminal_reason=stop_reason,
    )

    protected_written = protected_effect is not None and protected_effect.exists()
    if final_status != "VERIFIED":
        require(not protected_written, "non-verified path wrote protected effect")
        protected_dir = scenario_dir / "protected"
        require(
            not protected_dir.exists() or not list(protected_dir.iterdir()),
            "non-verified path contains protected files",
        )

    result: dict[str, Any] = {
        "schema_version": VERSION,
        "scenario_id": scenario_id,
        "final_status": final_status,
        "stop_reason": stop_reason,
        "protected_effect_written": protected_written,
        "protected_effect_ref": (
            relative(protected_effect, scenario_dir) if protected_effect else None
        ),
        "stage_records": stages,
        "replay": replay_result,
        "expected": copy.deepcopy(dict(scenario["expected"])),
    }

    if artifact_core is not None:
        artifact = {
            **artifact_core,
            "replay": replay_result,
            "integrity": {
                "artifact_digest": sha256_text(
                    canonical({**artifact_core, "replay": replay_result})
                ),
                "protected_effect_digest": (
                    sha256_bytes(protected_effect.read_bytes())
                    if protected_effect
                    else None
                ),
            },
            "claims": [
                "The fixture workflow reached a verified outcome.",
                "The protected effect occurred only after durable COMMITTED state.",
                "The durable event stream replayed without model, tool, or effect calls.",
            ],
            "non_claims": [
                "No production repository mutation was performed.",
                "No payment, deployment, credentialed API, or destructive effect was exercised.",
                "Local idempotence is not universal distributed exactly-once delivery.",
            ],
        }
        artifact_path = scenario_dir / "trusted-pr-review-artifact.json"
        write_json(artifact_path, artifact)
        result["artifact_ref"] = relative(artifact_path, scenario_dir)
    else:
        diagnostic_path = scenario_dir / "diagnostic.json"
        write_json(
            diagnostic_path,
            {
                "schema_version": VERSION,
                "scenario_id": scenario_id,
                "final_status": final_status,
                "stop_reason": stop_reason,
                "stages": stages,
                "replay": replay_result,
                "protected_effect_written": False,
            },
        )
        result["artifact_ref"] = None
        result["diagnostic_ref"] = relative(diagnostic_path, scenario_dir)

    summary_path = scenario_dir / "review-summary.md"
    summary_path.write_text(markdown_summary(result), encoding="utf-8")
    result["summary_ref"] = relative(summary_path, scenario_dir)
    write_json(scenario_dir / "scenario-result.json", result)
    return result


def compare_expected(result: Mapping[str, Any]) -> list[str]:
    expected = result["expected"]
    observed = {
        "final_status": result["final_status"],
        "stop_reason": result["stop_reason"],
        "protected_effect_written": result["protected_effect_written"],
        "replay_classification": result["replay"]["classification"],
        "replay_completion_state": result["replay"]["completion_state"],
        "resume_allowed": result["replay"]["resume_allowed"],
    }
    return [
        f"{key}: expected {expected.get(key)!r}, observed {value!r}"
        for key, value in observed.items()
        if expected.get(key) != value
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenarios", type=Path, default=DEFAULT_SCENARIOS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--scenario",
        action="append",
        dest="selected",
        help="Run only the named scenario; may be repeated.",
    )
    args = parser.parse_args()

    config = load_json(args.scenarios)
    if config.get("contract_version") != VERSION:
        raise ValueError("scenario contract version mismatch")
    raw_scenarios = config.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise ValueError("scenarios must be a non-empty list")
    selected = set(args.selected or [])
    scenarios = [
        item
        for item in raw_scenarios
        if isinstance(item, dict)
        and (not selected or item.get("scenario_id") in selected)
    ]
    scenario_ids = {str(item.get("scenario_id")) for item in scenarios}
    if selected != scenario_ids and selected:
        missing = sorted(selected - scenario_ids)
        raise ValueError(f"unknown scenarios: {missing}")

    output_root = args.output
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    runtime = Runtime()
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        result = run_scenario(runtime, config, scenario, output_root)
        errors = compare_expected(result)
        result["passed"] = not errors
        result["errors"] = errors
        write_json(output_root / result["scenario_id"] / "scenario-result.json", result)
        results.append(result)

    statuses = {item["final_status"] for item in results}
    report = {
        "contract_version": VERSION,
        "command": "python scripts/run_trusted_pr_review_v0_2.py",
        "scenarios_total": len(results),
        "scenarios_passed": sum(bool(item["passed"]) for item in results),
        "statuses_covered": sorted(statuses),
        "protected_effects_written": sum(
            bool(item["protected_effect_written"]) for item in results
        ),
        "boundary": {
            "model_output_is_authorization": False,
            "hold_can_reach_protected_effect": False,
            "block_can_reach_protected_effect": False,
            "effect_can_precede_durable_commit": False,
            "replay_reruns_models_tools_or_effects": False,
            "outcome_verification_creates_retroactive_authority": False,
        },
        "results": results,
    }
    required_statuses = {"VERIFIED", "HOLD", "BLOCK"}
    report["passed"] = (
        report["scenarios_passed"] == report["scenarios_total"]
        and (required_statuses.issubset(statuses) if not selected else True)
        and report["protected_effects_written"]
        == (1 if not selected or "allow_verified" in selected else 0)
    )
    write_json(output_root / "run-report.json", report)

    index_lines = [
        "# LS Trusted PR Review MVP v0.2",
        "",
        f"Overall result: **{'PASS' if report['passed'] else 'FAIL'}**",
        "",
    ]
    for item in results:
        index_lines.append(
            f"- `{item['scenario_id']}` → **{item['final_status']}** "
            f"(`{item['stop_reason']}`), effect={str(item['protected_effect_written']).lower()}"
        )
    index_lines.extend(
        [
            "",
            "The verified path exports a reusable JSON artifact and Markdown review. HOLD/BLOCK paths export diagnostics only and contain no protected effect.",
            "",
        ]
    )
    (output_root / "README.md").write_text("\n".join(index_lines), encoding="utf-8")

    print(pretty(report), end="")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
