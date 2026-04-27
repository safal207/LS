"""Run the Reflection Dashboard JSON API (GET /api/reflection/snapshot, POST /api/reflection/action)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.reflection_dashboard_api import run_reflection_dashboard_api  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Reflection Dashboard HTTP API")
    parser.add_argument("--host", default="127.0.0.1", help="bind address")
    parser.add_argument("--port", type=int, default=8780, help="listen port")
    parser.add_argument(
        "--state",
        default="reflection_state.json",
        help="path to cognitive state JSON for DecisionPipeline",
    )
    args = parser.parse_args()
    run_reflection_dashboard_api(host=args.host, port=args.port, state_path=args.state)


if __name__ == "__main__":
    main()
