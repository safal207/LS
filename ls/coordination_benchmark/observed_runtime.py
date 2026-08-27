from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import canonical_sha256, validate_coordination_event
from .pilot_runtime import (
    PASS,
    PilotViolation,
    load_records,
    make_record,
    next_sequence,
    validate_manifest,
    verify_pilot,
    write_record,
)

TRANSPORT_SCHEMA = "ls.multi-session.observed-transport.v0.1"
AUDIT_SCHEMA = "ls.multi-session.observed-audit.v0.1"
OBSERVED_PASS = "PASS_OBSERVED_RUNTIME_CONFIRMED"
OBSERVED_FAIL = "FAIL_OBSERVED_RUNTIME_EVIDENCE"


class ObservedRuntimeViolation(ValueError):
    """Raised when observed runtime evidence is malformed or inconsistent."""


def _canonical_record_hash(payload: Mapping[str, Any]) -> str:
    unsigned = {key: value for key, value in payload.items() if key != "record_hash"}
    return canonical_sha256(unsigned)


def _read_jsonl(path: Path) -> Tuple[Dict[str, Any], ...]:
    if not path.exists():
        return ()
    records: List[Dict[str, Any]] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ObservedRuntimeViolation(
                f"{path.name}:{line_number} is not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ObservedRuntimeViolation(
                f"{path.name}:{line_number} must contain a JSON object"
            )
        records.append(payload)
    return tuple(records)


def _locked_append(path: Path, payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Append one hash-chained record under an exclusive filesystem lock."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+", encoding="utf-8") as lock_handle:
        try:
            import fcntl

            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        except ImportError as exc:
            raise ObservedRuntimeViolation(
                "observed runtime requires POSIX file locking"
            ) from exc
        existing = _read_jsonl(path)
        previous_hash = existing[-1]["record_hash"] if existing else "GENESIS"
        record = dict(payload)
        record["offset"] = len(existing) + 1
        record["previous_hash"] = previous_hash
        record["record_hash"] = _canonical_record_hash(record)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    return record


def _validate_chain(
    records: Sequence[Mapping[str, Any]],
    *,
    schema: str,
    run_id: str,
    scenario_hash: str,
    name: str,
) -> None:
    previous_hash = "GENESIS"
    for expected_offset, record in enumerate(records, start=1):
        if record.get("schema") != schema:
            raise ObservedRuntimeViolation(f"{name}: unsupported schema")
        if record.get("run_id") != run_id:
            raise ObservedRuntimeViolation(f"{name}: run_id mismatch")
        if record.get("scenario_hash") != scenario_hash:
            raise ObservedRuntimeViolation(f"{name}: scenario_hash mismatch")
        if record.get("offset") != expected_offset:
            raise ObservedRuntimeViolation(f"{name}: offsets are not contiguous")
        if record.get("previous_hash") != previous_hash:
            raise ObservedRuntimeViolation(f"{name}: previous_hash mismatch")
        if record.get("record_hash") != _canonical_record_hash(record):
            raise ObservedRuntimeViolation(f"{name}: record_hash mismatch")
        previous_hash = str(record["record_hash"])


def initialize_observed_runtime(run_dir: Path) -> None:
    for directory in ("transport", "audit", "state"):
        (run_dir / directory).mkdir(parents=True, exist_ok=True)
    for path in (
        run_dir / "transport" / "events.jsonl",
        run_dir / "audit" / "global.jsonl",
    ):
        path.touch(exist_ok=True)


def _manifest_record_fields(manifest: Mapping[str, Any]) -> Dict[str, Any]:
    validate_manifest(manifest)
    return {
        "run_id": manifest["run_id"],
        "scenario_hash": manifest["scenario_hash"],
        "route_id": manifest["route_id"],
    }


def append_audit(
    run_dir: Path,
    manifest: Mapping[str, Any],
    *,
    session_id: str,
    action_type: str,
    event_id: Optional[str] = None,
    transport_offset: Optional[int] = None,
    transport_hash: Optional[str] = None,
    evidence_refs: Optional[Sequence[str]] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if session_id not in manifest["expected_sessions"]:
        raise ObservedRuntimeViolation("audit session_id is not expected")
    payload: Dict[str, Any] = {
        "schema": AUDIT_SCHEMA,
        **_manifest_record_fields(manifest),
        "session_id": session_id,
        "action_type": action_type,
        "evidence_refs": list(evidence_refs or []),
        "details": dict(details or {}),
    }
    if event_id is not None:
        payload["event_id"] = event_id
    if transport_offset is not None:
        payload["transport_offset"] = transport_offset
    if transport_hash is not None:
        payload["transport_hash"] = transport_hash
    return _locked_append(run_dir / "audit" / "global.jsonl", payload)


def publish_transport_event(
    run_dir: Path,
    manifest: Mapping[str, Any],
    *,
    publisher_session: str,
    event: Mapping[str, Any],
    evidence_refs: Optional[Sequence[str]] = None,
    failure_injection: bool = False,
    emit_session_trace: bool = False,
) -> Dict[str, Any]:
    validate_manifest(manifest)
    validate_coordination_event(event)
    if publisher_session not in manifest["expected_sessions"]:
        raise ObservedRuntimeViolation("publisher_session is not expected")
    envelope = _locked_append(
        run_dir / "transport" / "events.jsonl",
        {
            "schema": TRANSPORT_SCHEMA,
            **_manifest_record_fields(manifest),
            "publisher_session": publisher_session,
            "failure_injection": failure_injection,
            "event": dict(event),
            "evidence_refs": list(evidence_refs or []),
        },
    )
    audit = append_audit(
        run_dir,
        manifest,
        session_id=publisher_session,
        action_type="TRANSPORT_PUBLISHED",
        event_id=str(event["event_id"]),
        transport_offset=int(envelope["offset"]),
        transport_hash=str(envelope["record_hash"]),
        evidence_refs=evidence_refs,
        details={"failure_injection": failure_injection},
    )
    if emit_session_trace:
        _append_trace(
            run_dir,
            manifest,
            session_id=publisher_session,
            record_type="EVENT_EMITTED",
            event_id=str(event["event_id"]),
            producer_session=str(event["producer_session"]),
            generation=int(event["generation"]),
            evidence_refs=evidence_refs,
            details=_binding(envelope, audit),
        )
    return envelope


def _state_path(run_dir: Path, session_id: str) -> Path:
    return run_dir / "state" / f"{session_id}.json"


def _load_state(run_dir: Path, session_id: str) -> Dict[str, Any]:
    path = _state_path(run_dir, session_id)
    if not path.exists():
        return {"last_transport_offset": 0, "seen_event_ids": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ObservedRuntimeViolation("consumer state must be an object")
    return payload


def _write_state(run_dir: Path, session_id: str, state: Mapping[str, Any]) -> None:
    path = _state_path(run_dir, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _append_trace(
    run_dir: Path,
    manifest: Mapping[str, Any],
    *,
    session_id: str,
    record_type: str,
    event_id: Optional[str] = None,
    producer_session: Optional[str] = None,
    generation: Optional[int] = None,
    evidence_refs: Optional[Sequence[str]] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    trace_dir = run_dir / "traces"
    record = make_record(
        manifest,
        session_id=session_id,
        sequence=next_sequence(trace_dir, session_id),
        record_type=record_type,
        event_id=event_id,
        producer_session=producer_session,
        generation=generation,
        evidence_refs=evidence_refs,
        details=details,
    )
    write_record(trace_dir, record)
    return record


def _binding(
    transport: Optional[Mapping[str, Any]],
    audit: Mapping[str, Any],
    extra: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    details: Dict[str, Any] = {
        "audit_offset": audit["offset"],
        "audit_hash": audit["record_hash"],
    }
    if transport is not None:
        details.update(
            {
                "transport_offset": transport["offset"],
                "transport_hash": transport["record_hash"],
            }
        )
    details.update(dict(extra or {}))
    return details


def start_session(
    run_dir: Path,
    manifest: Mapping[str, Any],
    session_id: str,
    *,
    instance_id: str,
) -> Dict[str, Any]:
    audit = append_audit(
        run_dir,
        manifest,
        session_id=session_id,
        action_type="SESSION_STARTED",
        details={"instance_id": instance_id},
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id=session_id,
        record_type="SESSION_STARTED",
        details=_binding(None, audit, {"instance_id": instance_id}),
    )


def interrupt_session(
    run_dir: Path,
    manifest: Mapping[str, Any],
    session_id: str,
    *,
    kind: str,
) -> Dict[str, Any]:
    record_type = {
        "compaction": "SESSION_COMPACTED",
        "replacement": "SESSION_REPLACED",
    }.get(kind)
    if record_type is None:
        raise ObservedRuntimeViolation("interruption kind is invalid")
    audit = append_audit(
        run_dir,
        manifest,
        session_id=session_id,
        action_type=record_type,
        details={"kind": kind},
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id=session_id,
        record_type=record_type,
        details=_binding(None, audit, {"kind": kind}),
    )


def recover_session(
    run_dir: Path,
    manifest: Mapping[str, Any],
    session_id: str,
    *,
    instance_id: str,
) -> Dict[str, Any]:
    audit = append_audit(
        run_dir,
        manifest,
        session_id=session_id,
        action_type="SESSION_RECOVERED",
        details={"instance_id": instance_id},
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id=session_id,
        record_type="SESSION_RECOVERED",
        details=_binding(None, audit, {"instance_id": instance_id}),
    )


def consume_transport(
    run_dir: Path,
    manifest: Mapping[str, Any],
    session_id: str,
) -> Tuple[Dict[str, Any], ...]:
    if session_id not in manifest["dependent_sessions"]:
        raise ObservedRuntimeViolation("only dependent sessions consume endpoint events")
    transport_records = _read_jsonl(run_dir / "transport" / "events.jsonl")
    state = _load_state(run_dir, session_id)
    last_offset = int(state.get("last_transport_offset", 0))
    seen = set(state.get("seen_event_ids", []))
    output: List[Dict[str, Any]] = []
    expected_producer = manifest["expected_producer_session"]
    expected_generation = int(manifest["expected_generation"])

    for envelope in transport_records[last_offset:]:
        event = envelope["event"]
        event_id = str(event["event_id"])
        state["last_transport_offset"] = int(envelope["offset"])
        if session_id not in event["affected_sessions"]:
            continue
        if event_id in seen:
            action_type = "EVENT_DEDUPLICATED"
            reason = "duplicate_event_id"
        elif event["producer_session"] != expected_producer:
            action_type = "EVENT_BLOCKED"
            reason = "unauthorized_producer"
        elif int(event["generation"]) < expected_generation:
            action_type = "EVENT_BLOCKED"
            reason = "stale_generation"
        else:
            action_type = "EVENT_ACCEPTED"
            reason = "valid_provenance_and_generation"
            seen.add(event_id)

        audit = append_audit(
            run_dir,
            manifest,
            session_id=session_id,
            action_type=action_type,
            event_id=event_id,
            transport_offset=int(envelope["offset"]),
            transport_hash=str(envelope["record_hash"]),
            details={"reason": reason},
        )
        trace = _append_trace(
            run_dir,
            manifest,
            session_id=session_id,
            record_type=action_type,
            event_id=event_id,
            producer_session=str(event["producer_session"]),
            generation=int(event["generation"]),
            details=_binding(envelope, audit, {"reason": reason}),
        )
        output.append(trace)
        if action_type == "EVENT_ACCEPTED":
            invalidation_audit = append_audit(
                run_dir,
                manifest,
                session_id=session_id,
                action_type="PLAN_INVALIDATED",
                event_id=event_id,
                transport_offset=int(envelope["offset"]),
                transport_hash=str(envelope["record_hash"]),
                details={"generation": int(event["generation"])},
            )
            output.append(
                _append_trace(
                    run_dir,
                    manifest,
                    session_id=session_id,
                    record_type="PLAN_INVALIDATED",
                    event_id=event_id,
                    producer_session=str(event["producer_session"]),
                    generation=int(event["generation"]),
                    details=_binding(envelope, invalidation_audit),
                )
            )

    state["seen_event_ids"] = sorted(seen)
    _write_state(run_dir, session_id, state)
    return tuple(output)


def mark_replan_complete(
    run_dir: Path,
    manifest: Mapping[str, Any],
    session_id: str,
) -> Dict[str, Any]:
    event_id = manifest["expected_event_id"]
    audit = append_audit(
        run_dir,
        manifest,
        session_id=session_id,
        action_type="REPLAN_COMPLETED",
        event_id=event_id,
        details={"generation": manifest["expected_generation"]},
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id=session_id,
        record_type="REPLAN_COMPLETED",
        event_id=event_id,
        producer_session=manifest["expected_producer_session"],
        generation=int(manifest["expected_generation"]),
        details=_binding(None, audit),
    )


def _coordinator_records(
    run_dir: Path,
    manifest: Mapping[str, Any],
) -> Tuple[Optional[Mapping[str, Any]], Optional[Mapping[str, Any]]]:
    records = load_records(run_dir / "traces", manifest)
    receipt = next(
        (
            item for item in records
            if item["session_id"] == "coordinator"
            and item["record_type"] == "RECEIPT_VERIFIED"
        ),
        None,
    )
    release = next(
        (
            item for item in records
            if item["session_id"] == "coordinator"
            and item["record_type"] == "DEPENDENCY_RELEASED"
        ),
        None,
    )
    return receipt, release


def verify_receipt(
    run_dir: Path,
    manifest: Mapping[str, Any],
    *,
    evidence_ref: str,
) -> Dict[str, Any]:
    event_id = manifest["expected_event_id"]
    audit = append_audit(
        run_dir,
        manifest,
        session_id="coordinator",
        action_type="RECEIPT_VERIFIED",
        event_id=event_id,
        evidence_refs=[evidence_ref],
        details={"status": "VERIFIED"},
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id="coordinator",
        record_type="RECEIPT_VERIFIED",
        event_id=event_id,
        producer_session=manifest["expected_producer_session"],
        generation=int(manifest["expected_generation"]),
        evidence_refs=[evidence_ref],
        details=_binding(None, audit, {"status": "VERIFIED"}),
    )


def release_dependencies(
    run_dir: Path,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    receipt, existing_release = _coordinator_records(run_dir, manifest)
    if receipt is None or existing_release is not None:
        raise ObservedRuntimeViolation(
            "dependency release requires exactly one verified receipt and no release"
        )
    audit = append_audit(
        run_dir,
        manifest,
        session_id="coordinator",
        action_type="DEPENDENCY_RELEASED",
        event_id=manifest["expected_event_id"],
        details={"receipt_record_id": receipt["record_id"]},
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id="coordinator",
        record_type="DEPENDENCY_RELEASED",
        event_id=manifest["expected_event_id"],
        producer_session=manifest["expected_producer_session"],
        generation=int(manifest["expected_generation"]),
        evidence_refs=receipt.get("evidence_refs", []),
        details=_binding(
            None,
            audit,
            {"receipt_record_id": receipt["record_id"]},
        ),
    )


def attempt_action(
    run_dir: Path,
    manifest: Mapping[str, Any],
    session_id: str,
    *,
    evidence_ref: Optional[str] = None,
) -> Dict[str, Any]:
    if session_id not in manifest["dependent_sessions"]:
        raise ObservedRuntimeViolation("action session is not dependent")
    receipt, release = _coordinator_records(run_dir, manifest)
    if receipt is None or release is None:
        return append_audit(
            run_dir,
            manifest,
            session_id=session_id,
            action_type="ACTION_BLOCKED",
            event_id=manifest["expected_event_id"],
            details={"reason": "missing_verified_release"},
        )
    if not evidence_ref:
        raise ObservedRuntimeViolation("executed action requires evidence_ref")
    audit = append_audit(
        run_dir,
        manifest,
        session_id=session_id,
        action_type="ACTION_EXECUTED",
        event_id=manifest["expected_event_id"],
        evidence_refs=[evidence_ref],
        details={
            "receipt_record_id": receipt["record_id"],
            "release_record_id": release["record_id"],
        },
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id=session_id,
        record_type="ACTION_EXECUTED",
        event_id=manifest["expected_event_id"],
        producer_session=manifest["expected_producer_session"],
        generation=int(manifest["expected_generation"]),
        evidence_refs=[evidence_ref],
        details=_binding(
            None,
            audit,
            {
                "receipt_event_id": manifest["expected_event_id"],
                "receipt_status": "VERIFIED",
                "receipt_record_id": receipt["record_id"],
                "release_record_id": release["record_id"],
            },
        ),
    )


def finish_session(
    run_dir: Path,
    manifest: Mapping[str, Any],
    session_id: str,
) -> Dict[str, Any]:
    audit = append_audit(
        run_dir,
        manifest,
        session_id=session_id,
        action_type="SESSION_FINISHED",
    )
    return _append_trace(
        run_dir,
        manifest,
        session_id=session_id,
        record_type="SESSION_FINISHED",
        details=_binding(None, audit),
    )


def _index_by_offset(
    records: Sequence[Mapping[str, Any]],
) -> Dict[int, Mapping[str, Any]]:
    return {int(record["offset"]): record for record in records}


def _verify_trace_bindings(
    trace_records: Sequence[Mapping[str, Any]],
    transport_records: Sequence[Mapping[str, Any]],
    audit_records: Sequence[Mapping[str, Any]],
) -> None:
    transport_by_offset = _index_by_offset(transport_records)
    audit_by_offset = _index_by_offset(audit_records)
    bound_types = {
        "EVENT_EMITTED",
        "EVENT_ACCEPTED",
        "EVENT_BLOCKED",
        "EVENT_DEDUPLICATED",
        "PLAN_INVALIDATED",
        "REPLAN_COMPLETED",
        "RECEIPT_VERIFIED",
        "DEPENDENCY_RELEASED",
        "ACTION_EXECUTED",
    }
    for trace in trace_records:
        if trace["record_type"] not in bound_types:
            continue
        details = trace.get("details", {})
        audit_offset = details.get("audit_offset")
        audit_hash = details.get("audit_hash")
        if not isinstance(audit_offset, int):
            raise ObservedRuntimeViolation(
                f"{trace['record_id']}: missing audit_offset"
            )
        audit = audit_by_offset.get(audit_offset)
        if audit is None or audit.get("record_hash") != audit_hash:
            raise ObservedRuntimeViolation(
                f"{trace['record_id']}: audit binding mismatch"
            )
        if (
            audit.get("session_id") != trace["session_id"]
            or audit.get("action_type") != trace["record_type"]
            or audit.get("event_id") != trace.get("event_id")
        ):
            raise ObservedRuntimeViolation(
                f"{trace['record_id']}: audit semantics mismatch"
            )
        if trace["record_type"] in {
            "EVENT_EMITTED",
            "EVENT_ACCEPTED",
            "EVENT_BLOCKED",
            "EVENT_DEDUPLICATED",
            "PLAN_INVALIDATED",
        }:
            transport_offset = details.get("transport_offset")
            transport_hash = details.get("transport_hash")
            if not isinstance(transport_offset, int):
                raise ObservedRuntimeViolation(
                    f"{trace['record_id']}: missing transport_offset"
                )
            transport = transport_by_offset.get(transport_offset)
            if (
                transport is None
                or transport.get("record_hash") != transport_hash
                or transport.get("event", {}).get("event_id")
                != trace.get("event_id")
            ):
                raise ObservedRuntimeViolation(
                    f"{trace['record_id']}: transport binding mismatch"
                )


def verify_observed_runtime(
    run_dir: Path,
    manifest: Mapping[str, Any],
) -> Dict[str, Any]:
    """Verify pilot semantics plus transport, audit, and global order evidence."""

    validate_manifest(manifest)
    trace_records = load_records(run_dir / "traces", manifest)
    base_result = verify_pilot(manifest, trace_records)
    if base_result["verdict"] != PASS:
        return {
            "verdict": OBSERVED_FAIL,
            "violations": [
                f"base pilot verdict is {base_result['verdict']}",
                *base_result.get("violations", []),
            ],
            "base_result": base_result,
        }

    try:
        transport_records = _read_jsonl(
            run_dir / "transport" / "events.jsonl"
        )
        audit_records = _read_jsonl(run_dir / "audit" / "global.jsonl")
        _validate_chain(
            transport_records,
            schema=TRANSPORT_SCHEMA,
            run_id=manifest["run_id"],
            scenario_hash=manifest["scenario_hash"],
            name="transport",
        )
        _validate_chain(
            audit_records,
            schema=AUDIT_SCHEMA,
            run_id=manifest["run_id"],
            scenario_hash=manifest["scenario_hash"],
            name="audit",
        )
        _verify_trace_bindings(trace_records, transport_records, audit_records)

        blocked = [
            item for item in audit_records
            if item["session_id"] == "database"
            and item["action_type"] == "ACTION_BLOCKED"
            and item.get("details", {}).get("reason")
            == "missing_verified_release"
        ]
        receipt = next(
            item for item in audit_records
            if item["action_type"] == "RECEIPT_VERIFIED"
        )
        release = next(
            item for item in audit_records
            if item["action_type"] == "DEPENDENCY_RELEASED"
        )
        executed = [
            item for item in audit_records
            if item["action_type"] == "ACTION_EXECUTED"
        ]
        if len(blocked) != 1:
            raise ObservedRuntimeViolation(
                "database must prove exactly one premature blocked action"
            )
        if len(executed) != len(manifest["dependent_sessions"]):
            raise ObservedRuntimeViolation(
                "every dependent session must prove one executed action"
            )
        if not (
            blocked[0]["offset"]
            < receipt["offset"]
            < release["offset"]
            < min(item["offset"] for item in executed)
        ):
            raise ObservedRuntimeViolation(
                "global action/receipt/release order is invalid"
            )
    except (ObservedRuntimeViolation, StopIteration, PilotViolation) as exc:
        return {
            "verdict": OBSERVED_FAIL,
            "violations": [str(exc)],
            "base_result": base_result,
        }

    return {
        "verdict": OBSERVED_PASS,
        "violations": [],
        "evidence_mode": "OBSERVED_RUNTIME_BOUND_TRACE",
        "metrics": {
            "transport_record_count": len(transport_records),
            "audit_record_count": len(audit_records),
            "trace_record_count": len(trace_records),
            "premature_blocked_action_count": len(blocked),
            "executed_action_count": len(executed),
        },
        "base_result": base_result,
    }
