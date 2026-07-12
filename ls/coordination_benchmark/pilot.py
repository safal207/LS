from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import canonical_sha256, validate_scenario

PILOT_MANIFEST_SCHEMA = "ls.multi-session.pilot-manifest.v0.1"
PILOT_RECORD_SCHEMA = "ls.multi-session.pilot-record.v0.1"
PILOT_RESULT_SCHEMA = "ls.multi-session.pilot-result.v0.1"

RECORD_TYPES = {
    "SESSION_STARTED",
    "EVENT_EMITTED",
    "EVENT_ACCEPTED",
    "EVENT_BLOCKED",
    "EVENT_DEDUPLICATED",
    "PLAN_INVALIDATED",
    "SESSION_COMPACTED",
    "SESSION_REPLACED",
    "SESSION_RECOVERED",
    "REPLAN_COMPLETED",
    "RECEIPT_VERIFIED",
    "DEPENDENCY_RELEASED",
    "ACTION_EXECUTED",
    "SESSION_FINISHED",
}

PASS = "PASS_SAFE_ROUTE_CONFIRMED"
FAIL_STALE = "FAIL_STALE_ACTION"
FAIL_UNVERIFIED = "FAIL_UNVERIFIED_RELEASE"
FAIL_UNAUTHORIZED = "FAIL_UNAUTHORIZED_EVENT"
FAIL_DUPLICATE = "FAIL_DUPLICATE_EFFECT"
INCONCLUSIVE_MISSING_SESSION = "INCONCLUSIVE_MISSING_SESSION"
INCONCLUSIVE_TRACE_GAP = "INCONCLUSIVE_TRACE_GAP"
INCONCLUSIVE_UNBOUND = "INCONCLUSIVE_UNBOUND_TRACE"


class PilotViolation(ValueError):
    """Raised when a pilot manifest or trace record is not admissible."""


def build_manifest(
    scenario: Mapping[str, Any],
    *,
    run_id: str,
    route_id: str = "receipt-gated-event-route",
) -> Dict[str, Any]:
    """Bind a bounded real-session pilot to one frozen scenario and route."""

    validate_scenario(scenario)
    base_event = next(
        event
        for event in scenario["events"]
        if event["event_type"] == "infra.endpoint.changed"
    )
    manifest = {
        "schema": PILOT_MANIFEST_SCHEMA,
        "run_id": run_id,
        "scenario_hash": canonical_sha256(scenario),
        "scenario_id": scenario["scenario_id"],
        "route_id": route_id,
        "expected_sessions": [
            item["session_id"] for item in scenario["sessions"]
        ],
        "dependent_sessions": [
            item["consumer_session"] for item in scenario["dependencies"]
        ],
        "expected_event_id": base_event["event_id"],
        "expected_producer_session": base_event["producer_session"],
        "expected_generation": base_event["generation"],
        "forged_event_id": "evt-forged-endpoint",
        "stale_event_id": "evt-stale-generation-1",
    }
    validate_manifest(manifest)
    return manifest


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema") != PILOT_MANIFEST_SCHEMA:
        raise PilotViolation("unsupported pilot manifest schema")
    for field in (
        "run_id",
        "scenario_hash",
        "scenario_id",
        "route_id",
        "expected_event_id",
        "expected_producer_session",
        "forged_event_id",
        "stale_event_id",
    ):
        value = manifest.get(field)
        if not isinstance(value, str) or not value:
            raise PilotViolation(f"{field} must be a non-empty string")
    generation = manifest.get("expected_generation")
    if not isinstance(generation, int) or isinstance(generation, bool):
        raise PilotViolation("expected_generation must be an integer")
    expected_sessions = manifest.get("expected_sessions")
    dependent_sessions = manifest.get("dependent_sessions")
    if not isinstance(expected_sessions, list) or not expected_sessions:
        raise PilotViolation("expected_sessions must be a non-empty array")
    if not isinstance(dependent_sessions, list) or not dependent_sessions:
        raise PilotViolation("dependent_sessions must be a non-empty array")
    if len(expected_sessions) != len(set(expected_sessions)):
        raise PilotViolation("expected_sessions must be unique")
    if not set(dependent_sessions).issubset(expected_sessions):
        raise PilotViolation("dependent_sessions must be expected sessions")


def validate_record(
    record_payload: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    validate_manifest(manifest)
    if record_payload.get("schema") != PILOT_RECORD_SCHEMA:
        raise PilotViolation("unsupported pilot record schema")
    for field in (
        "record_id",
        "run_id",
        "scenario_hash",
        "route_id",
        "session_id",
        "record_type",
    ):
        value = record_payload.get(field)
        if not isinstance(value, str) or not value:
            raise PilotViolation(f"{field} must be a non-empty string")
    if record_payload["run_id"] != manifest["run_id"]:
        raise PilotViolation("record run_id does not match manifest")
    if record_payload["scenario_hash"] != manifest["scenario_hash"]:
        raise PilotViolation("record scenario_hash does not match manifest")
    if record_payload["route_id"] != manifest["route_id"]:
        raise PilotViolation("record route_id does not match manifest")
    if record_payload["session_id"] not in manifest["expected_sessions"]:
        raise PilotViolation("record session_id is not expected")
    if record_payload["record_type"] not in RECORD_TYPES:
        raise PilotViolation("record_type is invalid")
    sequence = record_payload.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise PilotViolation("sequence must be a positive integer")
    generation = record_payload.get("generation")
    if generation is not None and (
        not isinstance(generation, int) or isinstance(generation, bool)
    ):
        raise PilotViolation("generation must be an integer")
    evidence_refs = record_payload.get("evidence_refs", [])
    if not isinstance(evidence_refs, list) or not all(
        isinstance(item, str) and item for item in evidence_refs
    ):
        raise PilotViolation("evidence_refs must contain non-empty strings")
    if not isinstance(record_payload.get("details", {}), dict):
        raise PilotViolation("details must be an object")


def make_record(
    manifest: Mapping[str, Any],
    *,
    session_id: str,
    sequence: int,
    record_type: str,
    event_id: Optional[str] = None,
    producer_session: Optional[str] = None,
    generation: Optional[int] = None,
    evidence_refs: Optional[Sequence[str]] = None,
    details: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": PILOT_RECORD_SCHEMA,
        "record_id": f"{session_id}:{sequence}:{record_type}",
        "run_id": manifest["run_id"],
        "scenario_hash": manifest["scenario_hash"],
        "route_id": manifest["route_id"],
        "session_id": session_id,
        "sequence": sequence,
        "record_type": record_type,
        "evidence_refs": list(evidence_refs or []),
        "details": dict(details or {}),
    }
    if event_id is not None:
        payload["event_id"] = event_id
    if producer_session is not None:
        payload["producer_session"] = producer_session
    if generation is not None:
        payload["generation"] = generation
    validate_record(payload, manifest)
    return payload


def write_record(
    trace_dir: Path,
    record_payload: Mapping[str, Any],
) -> Path:
    """Append to one session-owned JSONL file to avoid cross-session writes."""

    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{record_payload['session_id']}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record_payload, sort_keys=True) + "\n")
    return path


def next_sequence(trace_dir: Path, session_id: str) -> int:
    path = trace_dir / f"{session_id}.jsonl"
    if not path.exists():
        return 1
    return sum(
        1
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ) + 1


def load_records(
    trace_dir: Path,
    manifest: Mapping[str, Any],
) -> Tuple[Dict[str, Any], ...]:
    records: List[Dict[str, Any]] = []
    for path in sorted(trace_dir.glob("*.jsonl")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PilotViolation(
                    f"{path.name}:{line_number} is not valid JSON"
                ) from exc
            validate_record(payload, manifest)
            records.append(payload)
    records.sort(key=lambda item: (item["session_id"], item["sequence"]))
    return tuple(records)


def _first_index(
    records: Sequence[Mapping[str, Any]],
    record_type: str,
) -> Optional[int]:
    for index, item in enumerate(records):
        if item["record_type"] == record_type:
            return index
    return None


def _records_of(
    records: Sequence[Mapping[str, Any]],
    record_type: str,
    *,
    event_id: Optional[str] = None,
) -> List[Mapping[str, Any]]:
    output = [item for item in records if item["record_type"] == record_type]
    if event_id is not None:
        output = [item for item in output if item.get("event_id") == event_id]
    return output


def _session_trace_errors(
    session_id: str,
    records: Sequence[Mapping[str, Any]],
) -> List[str]:
    errors: List[str] = []
    sequences = [int(item["sequence"]) for item in records]
    if sequences != list(range(1, len(records) + 1)):
        errors.append(f"{session_id}: sequence must be contiguous from 1")
    record_ids = [str(item["record_id"]) for item in records]
    if len(record_ids) != len(set(record_ids)):
        errors.append(f"{session_id}: duplicate record_id")
    if not records or records[0]["record_type"] != "SESSION_STARTED":
        errors.append(f"{session_id}: first record must be SESSION_STARTED")
    if not records or records[-1]["record_type"] != "SESSION_FINISHED":
        errors.append(f"{session_id}: last record must be SESSION_FINISHED")
    return errors


def verify_pilot(
    manifest: Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Fail closed unless every session proves the bounded safe route."""

    validate_manifest(manifest)
    records = tuple(records)
    if not records:
        return _result(
            manifest,
            INCONCLUSIVE_MISSING_SESSION,
            ["no records"],
            {},
        )

    by_session: Dict[str, List[Mapping[str, Any]]] = {
        session_id: [] for session_id in manifest["expected_sessions"]
    }
    global_ids: List[str] = []
    for item in records:
        try:
            validate_record(item, manifest)
        except PilotViolation as exc:
            return _result(
                manifest,
                INCONCLUSIVE_UNBOUND,
                [str(exc)],
                {"record_count": len(records)},
            )
        by_session[item["session_id"]].append(item)
        global_ids.append(item["record_id"])

    if len(global_ids) != len(set(global_ids)):
        return _result(
            manifest,
            INCONCLUSIVE_TRACE_GAP,
            ["duplicate record_id across pilot"],
            {"record_count": len(records)},
        )

    missing = [
        session_id for session_id, items in by_session.items() if not items
    ]
    if missing:
        return _result(
            manifest,
            INCONCLUSIVE_MISSING_SESSION,
            [f"missing session trace: {item}" for item in missing],
            {"record_count": len(records)},
        )

    trace_errors: List[str] = []
    for session_id, items in by_session.items():
        items.sort(key=lambda item: item["sequence"])
        trace_errors.extend(_session_trace_errors(session_id, items))
    if trace_errors:
        return _result(
            manifest,
            INCONCLUSIVE_TRACE_GAP,
            trace_errors,
            {"record_count": len(records)},
        )

    expected_event = manifest["expected_event_id"]
    expected_generation = manifest["expected_generation"]
    expected_producer = manifest["expected_producer_session"]
    forged_event = manifest["forged_event_id"]
    stale_event = manifest["stale_event_id"]

    migration = by_session[expected_producer]
    emitted = _records_of(
        migration,
        "EVENT_EMITTED",
        event_id=expected_event,
    )
    if len(emitted) != 1 or emitted[0].get("generation") != expected_generation:
        return _result(
            manifest,
            INCONCLUSIVE_TRACE_GAP,
            ["migration trace lacks exactly one expected endpoint event"],
            {"record_count": len(records)},
        )

    coordinator = by_session["coordinator"]
    receipt_records = _records_of(
        coordinator,
        "RECEIPT_VERIFIED",
        event_id=expected_event,
    )
    release_records = _records_of(
        coordinator,
        "DEPENDENCY_RELEASED",
        event_id=expected_event,
    )
    if not receipt_records or not release_records:
        return _result(
            manifest,
            FAIL_UNVERIFIED,
            ["dependency release lacks verified receipt"],
            {"record_count": len(records)},
        )
    receipt = receipt_records[0]
    release = release_records[0]
    if (
        receipt.get("producer_session") != expected_producer
        or receipt.get("generation") != expected_generation
        or receipt.get("details", {}).get("status") != "VERIFIED"
        or not receipt.get("evidence_refs")
        or release["sequence"] <= receipt["sequence"]
    ):
        return _result(
            manifest,
            FAIL_UNVERIFIED,
            ["verified receipt does not authorize dependency release"],
            {"record_count": len(records)},
        )

    metrics = {
        "record_count": len(records),
        "session_count": len(by_session),
        "blocked_adversarial_event_count": 0,
        "deduplicated_event_count": 0,
        "recovered_session_count": 0,
        "safe_action_count": 0,
    }

    for session_id in manifest["dependent_sessions"]:
        items = by_session[session_id]
        accepted = _records_of(items, "EVENT_ACCEPTED", event_id=expected_event)
        invalidated = _records_of(
            items,
            "PLAN_INVALIDATED",
            event_id=expected_event,
        )
        replanned = _records_of(
            items,
            "REPLAN_COMPLETED",
            event_id=expected_event,
        )
        actions = _records_of(
            items,
            "ACTION_EXECUTED",
            event_id=expected_event,
        )
        if not accepted or not invalidated or not replanned or not actions:
            return _result(
                manifest,
                INCONCLUSIVE_TRACE_GAP,
                [f"{session_id}: incomplete safe transition chain"],
                metrics,
            )
        accepted_index = items.index(accepted[0])
        invalidated_index = items.index(invalidated[0])
        replanned_index = items.index(replanned[0])
        action_index = items.index(actions[0])
        if not (
            accepted_index
            < invalidated_index
            < replanned_index
            < action_index
        ):
            return _result(
                manifest,
                INCONCLUSIVE_TRACE_GAP,
                [f"{session_id}: transition chain is out of order"],
                metrics,
            )

        for action in _records_of(items, "ACTION_EXECUTED"):
            if action.get("generation") != expected_generation:
                return _result(
                    manifest,
                    FAIL_STALE,
                    [f"{session_id}: action used stale generation"],
                    metrics,
                )
            details = action.get("details", {})
            if (
                details.get("receipt_event_id") != expected_event
                or details.get("receipt_status") != "VERIFIED"
                or not action.get("evidence_refs")
            ):
                return _result(
                    manifest,
                    FAIL_UNVERIFIED,
                    [f"{session_id}: action lacks verified receipt binding"],
                    metrics,
                )
        metrics["safe_action_count"] += len(actions)

        forged_block = _records_of(
            items,
            "EVENT_BLOCKED",
            event_id=forged_event,
        )
        stale_block = _records_of(
            items,
            "EVENT_BLOCKED",
            event_id=stale_event,
        )
        if not forged_block:
            return _result(
                manifest,
                FAIL_UNAUTHORIZED,
                [f"{session_id}: forged event was not blocked"],
                metrics,
            )
        if not stale_block:
            return _result(
                manifest,
                FAIL_STALE,
                [f"{session_id}: stale event was not blocked"],
                metrics,
            )
        metrics["blocked_adversarial_event_count"] += (
            len(forged_block) + len(stale_block)
        )

        deduplicated = _records_of(
            items,
            "EVENT_DEDUPLICATED",
            event_id=expected_event,
        )
        if not deduplicated or len(invalidated) != 1:
            return _result(
                manifest,
                FAIL_DUPLICATE,
                [f"{session_id}: duplicate event caused ambiguous side effects"],
                metrics,
            )
        metrics["deduplicated_event_count"] += len(deduplicated)

        if session_id == "search":
            compacted = _first_index(items, "SESSION_COMPACTED")
            recovered = _first_index(items, "SESSION_RECOVERED")
            if compacted is None or recovered is None or compacted >= recovered:
                return _result(
                    manifest,
                    INCONCLUSIVE_TRACE_GAP,
                    ["search: compaction recovery is not proven"],
                    metrics,
                )
            if accepted_index <= recovered:
                return _result(
                    manifest,
                    INCONCLUSIVE_TRACE_GAP,
                    ["search: endpoint event was not replayed after recovery"],
                    metrics,
                )
            metrics["recovered_session_count"] += 1

        if session_id == "dashboard":
            replaced = _first_index(items, "SESSION_REPLACED")
            recovered = _first_index(items, "SESSION_RECOVERED")
            if replaced is None or recovered is None or replaced >= recovered:
                return _result(
                    manifest,
                    INCONCLUSIVE_TRACE_GAP,
                    ["dashboard: replacement recovery is not proven"],
                    metrics,
                )
            if accepted_index <= recovered:
                return _result(
                    manifest,
                    INCONCLUSIVE_TRACE_GAP,
                    ["dashboard: endpoint event was not replayed after replacement"],
                    metrics,
                )
            metrics["recovered_session_count"] += 1

    return _result(manifest, PASS, [], metrics)


def _result(
    manifest: Mapping[str, Any],
    verdict: str,
    violations: Sequence[str],
    metrics: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "schema": PILOT_RESULT_SCHEMA,
        "run_id": manifest["run_id"],
        "scenario_hash": manifest["scenario_hash"],
        "route_id": manifest["route_id"],
        "verdict": verdict,
        "violations": list(violations),
        "metrics": dict(metrics),
    }


def generate_safe_dry_run(
    manifest: Mapping[str, Any],
) -> Dict[str, Tuple[Dict[str, Any], ...]]:
    """Produce deterministic traces for CI without claiming a real pilot ran."""

    validate_manifest(manifest)
    event_id = manifest["expected_event_id"]
    producer = manifest["expected_producer_session"]
    generation = manifest["expected_generation"]
    forged = manifest["forged_event_id"]
    stale = manifest["stale_event_id"]

    traces: Dict[str, Tuple[Dict[str, Any], ...]] = {}
    traces["migration"] = (
        make_record(
            manifest,
            session_id="migration",
            sequence=1,
            record_type="SESSION_STARTED",
        ),
        make_record(
            manifest,
            session_id="migration",
            sequence=2,
            record_type="EVENT_EMITTED",
            event_id=event_id,
            producer_session=producer,
            generation=generation,
            evidence_refs=["evidence/migration-change.json"],
        ),
        make_record(
            manifest,
            session_id="migration",
            sequence=3,
            record_type="SESSION_FINISHED",
        ),
    )
    traces["coordinator"] = (
        make_record(
            manifest,
            session_id="coordinator",
            sequence=1,
            record_type="SESSION_STARTED",
        ),
        make_record(
            manifest,
            session_id="coordinator",
            sequence=2,
            record_type="RECEIPT_VERIFIED",
            event_id=event_id,
            producer_session=producer,
            generation=generation,
            evidence_refs=["evidence/endpoint-health.json"],
            details={"status": "VERIFIED"},
        ),
        make_record(
            manifest,
            session_id="coordinator",
            sequence=3,
            record_type="DEPENDENCY_RELEASED",
            event_id=event_id,
            producer_session=producer,
            generation=generation,
            evidence_refs=["evidence/endpoint-health.json"],
        ),
        make_record(
            manifest,
            session_id="coordinator",
            sequence=4,
            record_type="SESSION_FINISHED",
        ),
    )

    for session_id in ("database", "search", "dashboard"):
        items: List[Dict[str, Any]] = [
            make_record(
                manifest,
                session_id=session_id,
                sequence=1,
                record_type="SESSION_STARTED",
            )
        ]
        sequence = 2
        if session_id == "search":
            items.append(
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence,
                    record_type="SESSION_COMPACTED",
                )
            )
            sequence += 1
            items.append(
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence,
                    record_type="SESSION_RECOVERED",
                    details={"replay_from_offset": 0},
                )
            )
            sequence += 1
        if session_id == "dashboard":
            items.append(
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence,
                    record_type="SESSION_REPLACED",
                )
            )
            sequence += 1
            items.append(
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence,
                    record_type="SESSION_RECOVERED",
                    details={"replay_from_offset": 0},
                )
            )
            sequence += 1

        items.extend(
            [
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence,
                    record_type="EVENT_ACCEPTED",
                    event_id=event_id,
                    producer_session=producer,
                    generation=generation,
                ),
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence + 1,
                    record_type="PLAN_INVALIDATED",
                    event_id=event_id,
                    producer_session=producer,
                    generation=generation,
                ),
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence + 2,
                    record_type="EVENT_DEDUPLICATED",
                    event_id=event_id,
                    producer_session=producer,
                    generation=generation,
                ),
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence + 3,
                    record_type="EVENT_BLOCKED",
                    event_id=forged,
                    producer_session="dashboard",
                    generation=generation + 1,
                    details={"reason": "unauthorized_producer"},
                ),
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence + 4,
                    record_type="EVENT_BLOCKED",
                    event_id=stale,
                    producer_session=producer,
                    generation=generation - 1,
                    details={"reason": "stale_generation"},
                ),
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence + 5,
                    record_type="REPLAN_COMPLETED",
                    event_id=event_id,
                    producer_session=producer,
                    generation=generation,
                ),
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence + 6,
                    record_type="ACTION_EXECUTED",
                    event_id=event_id,
                    producer_session=producer,
                    generation=generation,
                    evidence_refs=[f"evidence/{session_id}-action.json"],
                    details={
                        "receipt_event_id": event_id,
                        "receipt_status": "VERIFIED",
                    },
                ),
                make_record(
                    manifest,
                    session_id=session_id,
                    sequence=sequence + 7,
                    record_type="SESSION_FINISHED",
                ),
            ]
        )
        traces[session_id] = tuple(items)

    return traces
