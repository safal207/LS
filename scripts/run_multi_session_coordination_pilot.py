from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from ls.coordination_benchmark import (
    build_manifest,
    generate_safe_dry_run,
    load_records,
    make_record,
    next_sequence,
    verify_pilot,
    write_record,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "multi-session-coordination"
SCENARIO = EXPERIMENT / "canonical-five-session-scenario.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_instructions(manifest: Mapping[str, Any], run_dir: Path) -> str:
    lines = [
        "# Bounded multi-session coordination pilot",
        "",
        f"Run ID: `{manifest['run_id']}`",
        f"Scenario hash: `{manifest['scenario_hash']}`",
        f"Route: `{manifest['route_id']}`",
        "",
        "Each Claude Code session owns exactly one JSONL file under `traces/`.",
        "Never edit another session's file and never hand-edit completed records.",
        "",
        "## Record command",
        "",
        "```bash",
        "PYTHONPATH=. python scripts/run_multi_session_coordination_pilot.py record \\",
        f"  --run-dir {run_dir} \\",
        "  --session-id <session> \\",
        "  --record-type <type>",
        "```",
        "",
        "Attach `--event-id`, `--producer-session`, `--generation`,",
        "`--evidence-ref`, and `--details-json` when the transition requires them.",
        "",
        "## Verify after all five sessions finish",
        "",
        "```bash",
        "PYTHONPATH=. python scripts/run_multi_session_coordination_pilot.py verify \\",
        f"  --run-dir {run_dir}",
        "```",
        "",
        "A real pilot is valid only when the final verdict is",
        "`PASS_SAFE_ROUTE_CONFIRMED`. Dry-run output must never be represented",
        "as observed Claude Code evidence.",
        "",
    ]
    return "\n".join(lines)


def _init_run(run_dir: Path, run_id: str) -> dict:
    scenario = _load_json(SCENARIO)
    manifest = build_manifest(scenario, run_id=run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "traces").mkdir(exist_ok=True)
    (run_dir / "evidence").mkdir(exist_ok=True)
    _write_json(run_dir / "manifest.json", manifest)
    (run_dir / "SESSION_INSTRUCTIONS.md").write_text(
        _render_instructions(manifest, run_dir),
        encoding="utf-8",
    )
    return manifest


def _load_manifest(run_dir: Path) -> dict:
    path = run_dir / "manifest.json"
    if not path.exists():
        raise SystemExit(f"missing pilot manifest: {path}")
    return _load_json(path)


def command_init(args: argparse.Namespace) -> int:
    manifest = _init_run(args.run_dir, args.run_id)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def command_record(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.run_dir)
    trace_dir = args.run_dir / "traces"
    sequence = next_sequence(trace_dir, args.session_id)
    details = json.loads(args.details_json) if args.details_json else {}
    payload = make_record(
        manifest,
        session_id=args.session_id,
        sequence=sequence,
        record_type=args.record_type,
        event_id=args.event_id,
        producer_session=args.producer_session,
        generation=args.generation,
        evidence_refs=args.evidence_ref,
        details=details,
    )
    path = write_record(trace_dir, payload)
    print(f"recorded {payload['record_id']} -> {path}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    manifest = _load_manifest(args.run_dir)
    records = load_records(args.run_dir / "traces", manifest)
    result = verify_pilot(manifest, records)
    _write_json(args.run_dir / "pilot-result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "PASS_SAFE_ROUTE_CONFIRMED" else 1


def command_dry_run(args: argparse.Namespace) -> int:
    manifest = _init_run(args.run_dir, args.run_id)
    trace_dir = args.run_dir / "traces"
    for path in trace_dir.glob("*.jsonl"):
        path.unlink()
    traces = generate_safe_dry_run(manifest)
    for session_records in traces.values():
        for payload in session_records:
            write_record(trace_dir, payload)
    records = load_records(trace_dir, manifest)
    result = verify_pilot(manifest, records)
    result["evidence_mode"] = "DETERMINISTIC_DRY_RUN_NOT_OBSERVED"
    _write_json(args.run_dir / "pilot-result.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["verdict"] == "PASS_SAFE_ROUTE_CONFIRMED" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture and verify a bounded multi-session pilot"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--run-dir", type=Path, required=True)
    init_parser.add_argument("--run-id", required=True)
    init_parser.set_defaults(handler=command_init)

    record_parser = subparsers.add_parser("record")
    record_parser.add_argument("--run-dir", type=Path, required=True)
    record_parser.add_argument("--session-id", required=True)
    record_parser.add_argument("--record-type", required=True)
    record_parser.add_argument("--event-id")
    record_parser.add_argument("--producer-session")
    record_parser.add_argument("--generation", type=int)
    record_parser.add_argument(
        "--evidence-ref",
        action="append",
        default=[],
    )
    record_parser.add_argument("--details-json")
    record_parser.set_defaults(handler=command_record)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--run-dir", type=Path, required=True)
    verify_parser.set_defaults(handler=command_verify)

    dry_run_parser = subparsers.add_parser("dry-run")
    dry_run_parser.add_argument("--run-dir", type=Path, required=True)
    dry_run_parser.add_argument("--run-id", required=True)
    dry_run_parser.set_defaults(handler=command_dry_run)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
