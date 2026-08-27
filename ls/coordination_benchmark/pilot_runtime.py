from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .contracts import canonical_sha256, validate_scenario

PILOT_MANIFEST_SCHEMA = "ls.multi-session.pilot-manifest.v0.1"
PILOT_RECORD_SCHEMA = "ls.multi-session.pilot-record.v0.1"
PILOT_RESULT_SCHEMA = "ls.multi-session.pilot-result.v0.1"

RECORD_TYPES = {
    "SESSION_STARTED", "EVENT_EMITTED", "EVENT_ACCEPTED", "EVENT_BLOCKED",
    "EVENT_DEDUPLICATED", "PLAN_INVALIDATED", "SESSION_COMPACTED",
    "SESSION_REPLACED", "SESSION_RECOVERED", "REPLAN_COMPLETED",
    "RECEIPT_VERIFIED", "DEPENDENCY_RELEASED", "ACTION_EXECUTED",
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
    validate_scenario(scenario)
    base_event = next(
        event for event in scenario["events"]
        if event["event_type"] == "infra.endpoint.changed"
    )
    manifest = {
        "schema": PILOT_MANIFEST_SCHEMA,
        "run_id": run_id,
        "scenario_hash": canonical_sha256(scenario),
        "scenario_id": scenario["scenario_id"],
        "route_id": route_id,
        "expected_sessions": [x["session_id"] for x in scenario["sessions"]],
        "dependent_sessions": [
            x["consumer_session"] for x in scenario["dependencies"]
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
    string_fields = (
        "run_id", "scenario_hash", "scenario_id", "route_id",
        "expected_event_id", "expected_producer_session",
        "forged_event_id", "stale_event_id",
    )
    for field in string_fields:
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise PilotViolation(f"{field} must be a non-empty string")
    generation = manifest.get("expected_generation")
    if not isinstance(generation, int) or isinstance(generation, bool):
        raise PilotViolation("expected_generation must be an integer")
    expected = manifest.get("expected_sessions")
    dependent = manifest.get("dependent_sessions")
    if not isinstance(expected, list) or not expected:
        raise PilotViolation("expected_sessions must be a non-empty array")
    if not isinstance(dependent, list) or not dependent:
        raise PilotViolation("dependent_sessions must be a non-empty array")
    if len(expected) != len(set(expected)):
        raise PilotViolation("expected_sessions must be unique")
    if not set(dependent).issubset(expected):
        raise PilotViolation("dependent_sessions must be expected sessions")
    if "coordinator" not in expected:
        raise PilotViolation("coordinator must be an expected session")


def validate_record(record: Mapping[str, Any], manifest: Mapping[str, Any]) -> None:
    validate_manifest(manifest)
    if record.get("schema") != PILOT_RECORD_SCHEMA:
        raise PilotViolation("unsupported pilot record schema")
    string_fields = (
        "record_id", "run_id", "scenario_hash", "route_id",
        "session_id", "record_type",
    )
    for field in string_fields:
        if not isinstance(record.get(field), str) or not record[field]:
            raise PilotViolation(f"{field} must be a non-empty string")
    for field in ("run_id", "scenario_hash", "route_id"):
        if record[field] != manifest[field]:
            raise PilotViolation(f"record {field} does not match manifest")
    if record["session_id"] not in manifest["expected_sessions"]:
        raise PilotViolation("record session_id is not expected")
    if record["record_type"] not in RECORD_TYPES:
        raise PilotViolation("record_type is invalid")
    sequence = record.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise PilotViolation("sequence must be a positive integer")
    generation = record.get("generation")
    if generation is not None and (
        not isinstance(generation, int) or isinstance(generation, bool)
    ):
        raise PilotViolation("generation must be an integer")
    refs = record.get("evidence_refs", [])
    if not isinstance(refs, list) or not all(
        isinstance(item, str) and item for item in refs
    ):
        raise PilotViolation("evidence_refs must contain non-empty strings")
    if not isinstance(record.get("details", {}), dict):
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
    optional = {
        "event_id": event_id,
        "producer_session": producer_session,
        "generation": generation,
    }
    payload.update({key: value for key, value in optional.items() if value is not None})
    validate_record(payload, manifest)
    return payload


def write_record(trace_dir: Path, record: Mapping[str, Any]) -> Path:
    trace_dir.mkdir(parents=True, exist_ok=True)
    path = trace_dir / f"{record['session_id']}.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def next_sequence(trace_dir: Path, session_id: str) -> int:
    path = trace_dir / f"{session_id}.jsonl"
    if not path.exists():
        return 1
    return sum(bool(line.strip()) for line in path.read_text(
        encoding="utf-8"
    ).splitlines()) + 1


def load_records(
    trace_dir: Path,
    manifest: Mapping[str, Any],
) -> Tuple[Dict[str, Any], ...]:
    validate_manifest(manifest)
    records: List[Dict[str, Any]] = []
    for path in sorted(trace_dir.glob("*.jsonl")):
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PilotViolation(
                    f"{path.name}:{line_number} is not valid JSON"
                ) from exc
            if not isinstance(payload, dict):
                raise PilotViolation(
                    f"{path.name}:{line_number} must contain a JSON object"
                )
            records.append(payload)
    records.sort(key=lambda item: (
        str(item.get("session_id", "")),
        item.get("sequence", 0) if isinstance(item.get("sequence"), int) else 0,
    ))
    return tuple(records)


def _records_of(
    records: Sequence[Mapping[str, Any]],
    record_type: str,
    event_id: Optional[str] = None,
) -> List[Mapping[str, Any]]:
    output = [item for item in records if item["record_type"] == record_type]
    if event_id is not None:
        output = [item for item in output if item.get("event_id") == event_id]
    return output


def _first_index(
    records: Sequence[Mapping[str, Any]], record_type: str
) -> Optional[int]:
    return next(
        (index for index, item in enumerate(records)
         if item["record_type"] == record_type),
        None,
    )


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


def inconclusive_result(
    manifest: Mapping[str, Any], violation: str
) -> Dict[str, Any]:
    return _result(manifest, INCONCLUSIVE_UNBOUND, [violation], {})


def _group_records(
    manifest: Mapping[str, Any],
    records: Tuple[Mapping[str, Any], ...],
) -> Tuple[Optional[Dict[str, List[Mapping[str, Any]]]], Optional[Dict[str, Any]]]:
    by_session: Dict[str, List[Mapping[str, Any]]] = {
        session_id: [] for session_id in manifest["expected_sessions"]
    }
    record_ids: List[str] = []
    for item in records:
        try:
            validate_record(item, manifest)
        except PilotViolation as exc:
            return None, _result(
                manifest, INCONCLUSIVE_UNBOUND, [str(exc)],
                {"record_count": len(records)},
            )
        by_session[item["session_id"]].append(item)
        record_ids.append(item["record_id"])
    if len(record_ids) != len(set(record_ids)):
        return None, _result(
            manifest, INCONCLUSIVE_TRACE_GAP,
            ["duplicate record_id across pilot"],
            {"record_count": len(records)},
        )
    missing = [sid for sid, items in by_session.items() if not items]
    if missing:
        return None, _result(
            manifest, INCONCLUSIVE_MISSING_SESSION,
            [f"missing session trace: {sid}" for sid in missing],
            {"record_count": len(records)},
        )
    errors: List[str] = []
    for session_id, items in by_session.items():
        items.sort(key=lambda item: item["sequence"])
        sequences = [int(item["sequence"]) for item in items]
        if sequences != list(range(1, len(items) + 1)):
            errors.append(f"{session_id}: sequence must be contiguous from 1")
        if items[0]["record_type"] != "SESSION_STARTED":
            errors.append(f"{session_id}: first record must be SESSION_STARTED")
        if items[-1]["record_type"] != "SESSION_FINISHED":
            errors.append(f"{session_id}: last record must be SESSION_FINISHED")
    if errors:
        return None, _result(
            manifest, INCONCLUSIVE_TRACE_GAP, errors,
            {"record_count": len(records)},
        )
    return by_session, None


def verify_pilot(
    manifest: Mapping[str, Any],
    records: Iterable[Mapping[str, Any]],
) -> Dict[str, Any]:
    validate_manifest(manifest)
    records = tuple(records)
    if not records:
        return _result(
            manifest, INCONCLUSIVE_MISSING_SESSION, ["no records"], {}
        )
    by_session, error = _group_records(manifest, records)
    if error is not None:
        return error
    assert by_session is not None

    expected_event = manifest["expected_event_id"]
    generation = manifest["expected_generation"]
    producer = manifest["expected_producer_session"]
    forged = manifest["forged_event_id"]
    stale = manifest["stale_event_id"]

    migration = by_session[producer]
    emitted = _records_of(migration, "EVENT_EMITTED", expected_event)
    if len(emitted) != 1 or (
        emitted[0].get("producer_session") != producer
        or emitted[0].get("generation") != generation
        or not emitted[0].get("evidence_refs")
    ):
        return _result(
            manifest, INCONCLUSIVE_TRACE_GAP,
            ["migration trace lacks one evidence-bound expected event"],
            {"record_count": len(records)},
        )

    coordinator = by_session["coordinator"]
    receipts = _records_of(coordinator, "RECEIPT_VERIFIED", expected_event)
    releases = _records_of(coordinator, "DEPENDENCY_RELEASED", expected_event)
    if len(receipts) != 1 or len(releases) != 1:
        return _result(
            manifest, FAIL_UNVERIFIED,
            ["dependency release lacks one verified receipt"],
            {"record_count": len(records)},
        )
    receipt, release = receipts[0], releases[0]
    if (
        receipt.get("producer_session") != producer
        or receipt.get("generation") != generation
        or receipt.get("details", {}).get("status") != "VERIFIED"
        or not receipt.get("evidence_refs")
        or release["sequence"] <= receipt["sequence"]
        or release.get("details", {}).get("receipt_record_id")
        != receipt["record_id"]
    ):
        return _result(
            manifest, FAIL_UNVERIFIED,
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
        accepted = _records_of(items, "EVENT_ACCEPTED", expected_event)
        invalidated = _records_of(items, "PLAN_INVALIDATED", expected_event)
        replanned = _records_of(items, "REPLAN_COMPLETED", expected_event)
        actions = _records_of(items, "ACTION_EXECUTED", expected_event)
        if not all(len(group) == 1 for group in (
            accepted, invalidated, replanned, actions
        )):
            return _result(
                manifest, FAIL_DUPLICATE,
                [f"{session_id}: expected exactly one safe transition chain"],
                metrics,
            )
        chain = (accepted[0], invalidated[0], replanned[0], actions[0])
        indices = [items.index(item) for item in chain]
        if indices != sorted(indices) or len(set(indices)) != 4:
            return _result(
                manifest, INCONCLUSIVE_TRACE_GAP,
                [f"{session_id}: transition chain is out of order"],
                metrics,
            )
        if any(
            item.get("producer_session") != producer
            or item.get("generation") != generation
            for item in chain
        ):
            return _result(
                manifest, FAIL_STALE,
                [f"{session_id}: safe chain has stale or foreign provenance"],
                metrics,
            )

        all_accepted = _records_of(items, "EVENT_ACCEPTED")
        if any(
            item.get("event_id") != expected_event
            or item.get("producer_session") != producer
            or item.get("generation") != generation
            for item in all_accepted
        ):
            return _result(
                manifest, FAIL_UNAUTHORIZED,
                [f"{session_id}: unauthorized event was accepted"],
                metrics,
            )

        action = actions[0]
        details = action.get("details", {})
        if (
            details.get("receipt_event_id") != expected_event
            or details.get("receipt_status") != "VERIFIED"
            or details.get("receipt_record_id") != receipt["record_id"]
            or details.get("release_record_id") != release["record_id"]
            or not action.get("evidence_refs")
        ):
            return _result(
                manifest, FAIL_UNVERIFIED,
                [f"{session_id}: action lacks exact receipt/release binding"],
                metrics,
            )
        metrics["safe_action_count"] += 1

        forged_blocks = _records_of(items, "EVENT_BLOCKED", forged)
        stale_blocks = _records_of(items, "EVENT_BLOCKED", stale)
        valid_forged = (
            len(forged_blocks) == 1
            and forged_blocks[0].get("producer_session") != producer
            and forged_blocks[0].get("details", {}).get("reason")
            == "unauthorized_producer"
        )
        valid_stale = (
            len(stale_blocks) == 1
            and stale_blocks[0].get("producer_session") == producer
            and stale_blocks[0].get("generation", generation) < generation
            and stale_blocks[0].get("details", {}).get("reason")
            == "stale_generation"
        )
        if not valid_forged:
            return _result(
                manifest, FAIL_UNAUTHORIZED,
                [f"{session_id}: forged event was not correctly blocked"],
                metrics,
            )
        if not valid_stale:
            return _result(
                manifest, FAIL_STALE,
                [f"{session_id}: stale event was not correctly blocked"],
                metrics,
            )
        metrics["blocked_adversarial_event_count"] += 2

        dedup = _records_of(items, "EVENT_DEDUPLICATED", expected_event)
        valid_dedup = (
            len(dedup) == 1
            and dedup[0].get("producer_session") == producer
            and dedup[0].get("generation") == generation
        )
        if not valid_dedup:
            return _result(
                manifest, FAIL_DUPLICATE,
                [f"{session_id}: duplicate event was not safely deduplicated"],
                metrics,
            )
        metrics["deduplicated_event_count"] += 1

        recovery_type = {
            "search": "SESSION_COMPACTED",
            "dashboard": "SESSION_REPLACED",
        }.get(session_id)
        if recovery_type is not None:
            interrupted = _first_index(items, recovery_type)
            recovered = _first_index(items, "SESSION_RECOVERED")
            accepted_index = items.index(accepted[0])
            if (
                interrupted is None or recovered is None
                or interrupted >= recovered or recovered >= accepted_index
            ):
                return _result(
                    manifest, INCONCLUSIVE_TRACE_GAP,
                    [f"{session_id}: recovery replay is not proven"],
                    metrics,
                )
            metrics["recovered_session_count"] += 1

    return _result(manifest, PASS, [], metrics)


def _dependent_trace(
    manifest: Mapping[str, Any],
    session_id: str,
    *,
    receipt_record_id: str,
    release_record_id: str,
) -> Tuple[Dict[str, Any], ...]:
    event_id = manifest["expected_event_id"]
    producer = manifest["expected_producer_session"]
    generation = manifest["expected_generation"]
    forged = manifest["forged_event_id"]
    stale = manifest["stale_event_id"]
    items: List[Dict[str, Any]] = [
        make_record(
            manifest, session_id=session_id, sequence=1,
            record_type="SESSION_STARTED",
        )
    ]
    sequence = 2
    interruption = {
        "search": "SESSION_COMPACTED",
        "dashboard": "SESSION_REPLACED",
    }.get(session_id)
    if interruption is not None:
        items.append(make_record(
            manifest, session_id=session_id, sequence=sequence,
            record_type=interruption,
        ))
        sequence += 1
        items.append(make_record(
            manifest, session_id=session_id, sequence=sequence,
            record_type="SESSION_RECOVERED",
            details={"replay_from_offset": 0},
        ))
        sequence += 1

    specs = [
        ("EVENT_ACCEPTED", event_id, producer, generation, {}, []),
        ("PLAN_INVALIDATED", event_id, producer, generation, {}, []),
        ("EVENT_DEDUPLICATED", event_id, producer, generation, {}, []),
        (
            "EVENT_BLOCKED", forged, "dashboard", generation + 1,
            {"reason": "unauthorized_producer"}, [],
        ),
        (
            "EVENT_BLOCKED", stale, producer, generation - 1,
            {"reason": "stale_generation"}, [],
        ),
        ("REPLAN_COMPLETED", event_id, producer, generation, {}, []),
        (
            "ACTION_EXECUTED", event_id, producer, generation,
            {
                "receipt_event_id": event_id,
                "receipt_status": "VERIFIED",
                "receipt_record_id": receipt_record_id,
                "release_record_id": release_record_id,
            },
            [f"evidence/{session_id}-action.json"],
        ),
    ]
    for record_type, current_event, current_producer, current_generation, details, refs in specs:
        items.append(make_record(
            manifest,
            session_id=session_id,
            sequence=sequence,
            record_type=record_type,
            event_id=current_event,
            producer_session=current_producer,
            generation=current_generation,
            details=details,
            evidence_refs=refs,
        ))
        sequence += 1
    items.append(make_record(
        manifest, session_id=session_id, sequence=sequence,
        record_type="SESSION_FINISHED",
    ))
    return tuple(items)


def generate_safe_dry_run(
    manifest: Mapping[str, Any],
) -> Dict[str, Tuple[Dict[str, Any], ...]]:
    validate_manifest(manifest)
    event_id = manifest["expected_event_id"]
    producer = manifest["expected_producer_session"]
    generation = manifest["expected_generation"]
    receipt_id = "coordinator:2:RECEIPT_VERIFIED"
    release_id = "coordinator:3:DEPENDENCY_RELEASED"
    traces: Dict[str, Tuple[Dict[str, Any], ...]] = {
        "migration": (
            make_record(
                manifest, session_id="migration", sequence=1,
                record_type="SESSION_STARTED",
            ),
            make_record(
                manifest, session_id="migration", sequence=2,
                record_type="EVENT_EMITTED", event_id=event_id,
                producer_session=producer, generation=generation,
                evidence_refs=["evidence/migration-change.json"],
            ),
            make_record(
                manifest, session_id="migration", sequence=3,
                record_type="SESSION_FINISHED",
            ),
        ),
        "coordinator": (
            make_record(
                manifest, session_id="coordinator", sequence=1,
                record_type="SESSION_STARTED",
            ),
            make_record(
                manifest, session_id="coordinator", sequence=2,
                record_type="RECEIPT_VERIFIED", event_id=event_id,
                producer_session=producer, generation=generation,
                evidence_refs=["evidence/endpoint-health.json"],
                details={"status": "VERIFIED"},
            ),
            make_record(
                manifest, session_id="coordinator", sequence=3,
                record_type="DEPENDENCY_RELEASED", event_id=event_id,
                producer_session=producer, generation=generation,
                evidence_refs=["evidence/endpoint-health.json"],
                details={"receipt_record_id": receipt_id},
            ),
            make_record(
                manifest, session_id="coordinator", sequence=4,
                record_type="SESSION_FINISHED",
            ),
        ),
    }
    for session_id in ("database", "search", "dashboard"):
        traces[session_id] = _dependent_trace(
            manifest, session_id,
            receipt_record_id=receipt_id,
            release_record_id=release_id,
        )
    return traces
