from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"

if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
if str(MODULES_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULES_ROOT))

from modules.web4_runtime.loadtest import LoadTestConfig, run_load_test


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Web4 runtime load-test harness phases (phase1/phase2).",
    )
    parser.add_argument("--phase", choices=["phase1", "phase2"], default="phase1")
    parser.add_argument("--mode", choices=["sync", "async", "both"], default="both")
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--messages-per-session", type=int, default=200)
    parser.add_argument("--max-queue", type=int, default=64)
    parser.add_argument("--total-limit", type=int, default=512)
    parser.add_argument("--per-session-limit", type=int, default=64)
    parser.add_argument("--block-timeout-s", type=float, default=0.8)
    parser.add_argument("--random-seed", type=int, default=42)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = LoadTestConfig(
        phase=args.phase,
        mode=args.mode,
        sessions=args.sessions,
        messages_per_session=args.messages_per_session,
        max_queue=args.max_queue,
        total_limit=args.total_limit,
        per_session_limit=args.per_session_limit,
        block_timeout_s=args.block_timeout_s,
        random_seed=args.random_seed,
    )
    report = run_load_test(config)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
