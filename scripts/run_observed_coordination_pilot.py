from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping

from ls.coordination_benchmark.observed_runtime import (
    OBSERVED_PASS,
    append_audit,
    attempt_action,
    consume_transport,
    finish_session,
    initialize_observed_runtime,
    interrupt_session,
    mark_replan_complete,
    publish_transport_event,
    recover_session,
    release_dependencies,
    start_session,
    verify_observed_runtime,
    verify_receipt,
)
from ls.coordination_benchmark.pilot_runtime import (
    build_manifest,
    make_record,
    next_sequence,
    write_record,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "multi-session-coordination"
SCENARIO_PATH = EXPERIMENT / "canonical-five-session-scenario.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest(run_dir: Path) -> dict:
    path = run_dir / "manifest.json"
    if not path.exists():
        raise SystemExit(f"missing manifest: {path}")
    return _load_json(path)


def _canonical_event() -> Dict[str, Any]:
    scenario = _load_json(SCENARIO_PATH)
    return next(
        dict(event)
        for event in scenario["events"]
        if event["event_type"] == "infra.endpoint.changed"
    )


def _trace_emitted(
    run_dir: Path,
    manifest: Mapping[str, Any],
    event: Mapping[str, Any],
    envelope: Mapping[str, Any],
    evidence_ref: str,
) -> None:
    audit = append_audit(
        run_dir,
        manifest,
        session_id="migration",
        action_type="EVENT_EMITTED",
        event_id=str(event["event_id"]),
        transport_offset=int(envelope["offset"]),
        transport_hash=str(envelope["record_hash"]),
        evidence_refs=[evidence_ref],
    )
    details = {
        "transport_offset": envelope["offset"],
        "transport_hash": envelope["record_hash"],
        "audit_offset": audit["offset"],
        "audit_hash": audit["record_hash"],
    }
    trace_dir = run_dir / "traces"
    record = make_record(
        manifest,
        session_id="migration",
        sequence=next_sequence(trace_dir, "migration"),
        record_type="EVENT_EMITTED",
        event_id=str(event["event_id"]),
        producer_session=str(event["producer_session"]),
        generation=int(event["generation"]),
        evidence_refs=[evidence_ref],
        details=details,
    )
    write_record(trace_dir, record)


def command_init(args: argparse.Namespace) -> int:
    scenario = _load_json(SCENARIO_PATH)
    manifest = build_manifest(scenario, run_id=args.run_id)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    (args.run_dir / "traces").mkdir(exist_ok=True)
    (args.run_dir / "evidence").mkdir(exist_ok=True)
    _write_json(args.run_dir / "manifest.json", manifest)
    initialize_observed_runtime(args.run_dir)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def command_start(args: argparse.Namespace) -> int:
    record = start_session(
        args.run_dir,
        _manifest(args.run_dir),
        args.session_id,
        instance_id=args.instance_id,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_interrupt(args: argparse.Namespace) -> int:
    record = interrupt_session(
        args.run_dir,
        _manifest(args.run_dir),
        args.session_id,
        kind=args.kind,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_recover(args: argparse.Namespace) -> int:
    record = recover_session(
        args.run_dir,
        _manifest(args.run_dir),
        args.session_id,
        instance_id=args.instance_id,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_publish_valid(args: argparse.Namespace) -> int:
    manifest = _manifest(args.run_dir)
    event = _canonical_event()
    envelope = publish_transport_event(
        args.run_dir,
        manifest,
        publisher_session="migration",
        event=event,
        evidence_refs=[args.evidence_ref],
    )
    _trace_emitted(
        args.run_dir,
        manifest,
        event,
        envelope,
        args.evidence_ref,
    )
    print(json.dumps(envelope, indent=2, sort_keys=True))
    return 0


def command_inject_failures(args: argparse.Namespace) -> int:
    manifest = _manifest(args.run_dir)
    valid = _canonical_event()
    duplicate = dict(valid)
    forged = dict(valid)
    forged.update(
        {
            "event_id": manifest["forged_event_id"],
            "producer_session": "dashboard",
            "generation": int(manifest["expected_generation"]) + 1,
            "payload": {
                "key": "SERVER_IP",
                "previous_value": "198.51.100.20",
                "new_value": "203.0.113.66",
            },
        }
    )
    stale = dict(valid)
    stale.update(
        {
            "event_id": manifest["stale_event_id"],
            "generation": int(manifest["expected_generation"]) - 1,
            "payload": {
                "key": "SERVER_IP",
                "previous_value": "198.51.100.20",
                "new_value": "192.0.2.10",
            },
        }
    )
    output = []
    for event in (duplicate, forged, stale):
        output.append(
            publish_transport_event(
                args.run_dir,
                manifest,
                publisher_session="coordinator",
                event=event,
                failure_injection=True,
            )
        )
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def command_consume(args: argparse.Namespace) -> int:
    records = consume_transport(
        args.run_dir,
        _manifest(args.run_dir),
        args.session_id,
    )
    print(json.dumps(records, indent=2, sort_keys=True))
    return 0


def command_replan(args: argparse.Namespace) -> int:
    record = mark_replan_complete(
        args.run_dir,
        _manifest(args.run_dir),
        args.session_id,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_attempt_action(args: argparse.Namespace) -> int:
    record = attempt_action(
        args.run_dir,
        _manifest(args.run_dir),
        args.session_id,
        evidence_ref=args.evidence_ref,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_verify_receipt(args: argparse.Namespace) -> int:
    record = verify_receipt(
        args.run_dir,
        _manifest(args.run_dir),
        evidence_ref=args.evidence_ref,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_release(args: argparse.Namespace) -> int:
    record = release_dependencies(args.run_dir, _manifest(args.run_dir))
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_finish(args: argparse.Namespace) -> int:
    record = finish_session(
        args.run_dir,
        _manifest(args.run_dir),
        args.session_id,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def command_verify_observed(args: argparse.Namespace) -> int:
    result = verify_observed_runtime(args.run_dir, _manifest(args.run_dir))
    _write_json(args.run_dir / "observed-result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == OBSERVED_PASS else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the evidence-bound observed coordination pilot runtime"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--run-dir", type=Path, required=True)
    init_parser.add_argument("--run-id", required=True)
    init_parser.set_defaults(handler=command_init)

    for name, handler in (
        ("start", command_start),
        ("recover", command_recover),
    ):
        current = subparsers.add_parser(name)
        current.add_argument("--run-dir", type=Path, required=True)
        current.add_argument("--session-id", required=True)
        current.add_argument("--instance-id", required=True)
        current.set_defaults(handler=handler)

    interrupt_parser = subparsers.add_parser("interrupt")
    interrupt_parser.add_argument("--run-dir", type=Path, required=True)
    interrupt_parser.add_argument("--session-id", required=True)
    interrupt_parser.add_argument(
        "--kind", choices=("compaction", "replacement"), required=True
    )
    interrupt_parser.set_defaults(handler=command_interrupt)

    publish_parser = subparsers.add_parser("publish-valid")
    publish_parser.add_argument("--run-dir", type=Path, required=True)
    publish_parser.add_argument("--evidence-ref", required=True)
    publish_parser.set_defaults(handler=command_publish_valid)

    inject_parser = subparsers.add_parser("inject-failures")
    inject_parser.add_argument("--run-dir", type=Path, required=True)
    inject_parser.set_defaults(handler=command_inject_failures)

    for name, handler in (
        ("consume", command_consume),
        ("replan", command_replan),
        ("finish", command_finish),
    ):
        current = subparsers.add_parser(name)
        current.add_argument("--run-dir", type=Path, required=True)
        current.add_argument("--session-id", required=True)
        current.set_defaults(handler=handler)

    action_parser = subparsers.add_parser("attempt-action")
    action_parser.add_argument("--run-dir", type=Path, required=True)
    action_parser.add_argument("--session-id", required=True)
    action_parser.add_argument("--evidence-ref")
    action_parser.set_defaults(handler=command_attempt_action)

    receipt_parser = subparsers.add_parser("verify-receipt")
    receipt_parser.add_argument("--run-dir", type=Path, required=True)
    receipt_parser.add_argument("--evidence-ref", required=True)
    receipt_parser.set_defaults(handler=command_verify_receipt)

    release_parser = subparsers.add_parser("release")
    release_parser.add_argument("--run-dir", type=Path, required=True)
    release_parser.set_defaults(handler=command_release)

    verify_parser = subparsers.add_parser("verify-observed")
    verify_parser.add_argument("--run-dir", type=Path, required=True)
    verify_parser.set_defaults(handler=command_verify_observed)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
