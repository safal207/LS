#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.identity_learning_v02 import (  # noqa: E402
    aggregate_verified_episode_v02_mappings,
)


DEFAULT_CREATED_AT = "2026-06-25T12:00:00Z"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate immutable LS VerifiedEpisode v0.2 records into a "
            "review-only identity update proposal."
        ),
    )
    parser.add_argument(
        "--episode",
        action="append",
        type=Path,
        required=True,
        help="Path to VerifiedEpisode v0.2 JSON. Repeat for multiple episodes.",
    )
    parser.add_argument("--scope", required=True)
    parser.add_argument("--repeat-key", required=True)
    parser.add_argument("--statement", required=True)
    parser.add_argument(
        "--required-support-count",
        type=int,
        default=3,
    )
    parser.add_argument("--created-at", default=DEFAULT_CREATED_AT)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build/identity-learning-v0.2",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payloads = tuple(_read_json(path) for path in args.episode)
    aggregation = aggregate_verified_episode_v02_mappings(
        payloads,
        scope=args.scope,
        repeat_key=args.repeat_key,
        candidate_statement=args.statement,
        created_at=args.created_at,
        required_support_count=args.required_support_count,
        metadata={
            "source": "aggregate_verified_episodes_v02_cli",
            "input_count": len(args.episode),
        },
    )

    args.output.mkdir(parents=True, exist_ok=True)
    aggregation_path = args.output / "lesson-aggregation-v0.2.json"
    _write_json(aggregation_path, aggregation.to_dict())

    proposal_path = None
    if aggregation.proposal is not None:
        proposal_path = args.output / "identity-update-proposal.json"
        _write_json(proposal_path, aggregation.proposal.to_dict())

    summary = {
        "schema_version": aggregation.schema_version,
        "status": aggregation.status.value,
        "aggregation_ref": aggregation.aggregation_id,
        "support_count": aggregation.support_count,
        "failure_count": aggregation.failure_count,
        "contradiction_count": aggregation.contradiction_count,
        "ignored_count": aggregation.ignored_count,
        "aggregated_confidence": aggregation.aggregated_confidence,
        "proposal_created": aggregation.proposal is not None,
        "proposal_ref": (
            aggregation.proposal.proposal_id if aggregation.proposal else None
        ),
        "proposal_applied": False,
        "aggregation_path": str(aggregation_path),
        "proposal_path": str(proposal_path) if proposal_path else None,
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


def _read_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
