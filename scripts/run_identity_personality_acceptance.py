#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_personality_acceptance import (  # noqa: E402
    run_identity_personality_acceptance,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the deterministic VerifiedEpisode v0.2 to governed personality "
            "projection acceptance path."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path. Defaults to stdout.",
    )
    parser.add_argument(
        "--markdown-output",
        type=Path,
        help="Optional path for the bounded AGENTS.md/CLAUDE.md projection.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_identity_personality_acceptance()
    payload = json.dumps(
        result.to_dict(),
        sort_keys=True,
        indent=2,
        ensure_ascii=False,
    )

    if args.output is None:
        print(payload)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")

    if args.markdown_output is not None:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(
            result.runtime_markdown,
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
