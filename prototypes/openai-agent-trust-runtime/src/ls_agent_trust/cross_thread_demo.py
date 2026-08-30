"""Run the seven-agent CrossThread Protocol reference workflow offline."""

from __future__ import annotations

import argparse
import json
from typing import Sequence

from .council import SevenAgentCouncil


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--brief",
        default=(
            "Build a vendor-neutral, evidence-aware protocol for safe coordination "
            "between durable AI-agent threads."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    run = SevenAgentCouncil().run(args.brief)
    print(json.dumps(run.to_dict(), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
