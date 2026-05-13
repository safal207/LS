#!/usr/bin/env python3
"""Run the Personal Cognitive Garden demo flow.

This script is intentionally dependency-free. It reads the checked-in example
artifacts and prints a compact, reviewer-facing walkthrough:

session summary -> development classification -> skill delta -> governance review
-> accepted graph state
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXAMPLE_DIR = REPO_ROOT / "examples" / "personal_cognitive_garden"


class DemoInputError(ValueError):
    """Raised when the demo artifacts are missing required fields."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as file:
            value = json.load(file)
    except FileNotFoundError as exc:
        raise DemoInputError(f"Missing demo artifact: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DemoInputError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise DemoInputError(f"Expected object at top level in {path}")
    return value


def require(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise DemoInputError(f"Missing required field `{key}` in {context}")
    return mapping[key]


def first_accepted_update(graph_state: dict[str, Any]) -> dict[str, Any]:
    accepted_updates = require(graph_state, "accepted_updates", "accepted graph state")
    if not isinstance(accepted_updates, list) or not accepted_updates:
        raise DemoInputError("`accepted_updates` must be a non-empty list")
    first = accepted_updates[0]
    if not isinstance(first, dict):
        raise DemoInputError("First accepted update must be an object")
    return first


def summarize(session_summary: dict[str, Any], proposed_update: dict[str, Any], graph_state: dict[str, Any]) -> dict[str, Any]:
    development_effect = require(proposed_update, "development_effect", "proposed update")
    if not isinstance(development_effect, dict):
        raise DemoInputError("`development_effect` must be an object")

    accepted_update = first_accepted_update(graph_state)
    review = require(accepted_update, "review", "accepted update")
    if not isinstance(review, dict):
        raise DemoInputError("`review` must be an object")

    nodes = require(graph_state, "nodes", "accepted graph state")
    if not isinstance(nodes, list):
        raise DemoInputError("`nodes` must be a list")

    return {
        "session_id": require(session_summary, "session_id", "session summary"),
        "session_type": session_summary.get("session_type", "unknown"),
        "development_class": require(proposed_update, "session_development_class", "proposed update"),
        "is_developmental": require(development_effect, "is_developmental", "development effect"),
        "human_skill_delta": require(development_effect, "human_skill_delta", "development effect"),
        "capital_effect": require(development_effect, "capital_effect", "development effect"),
        "practice_needed": require(development_effect, "practice_needed", "development effect"),
        "compounding_score": require(development_effect, "compounding_score", "development effect"),
        "proposed_status": require(proposed_update, "status", "proposed update"),
        "review_decision": require(review, "decision", "review"),
        "reviewed_by": require(review, "reviewed_by", "review"),
        "accepted_nodes": [node.get("label", node.get("node_id", "unknown")) for node in nodes if isinstance(node, dict)],
    }


def print_human(summary: dict[str, Any]) -> None:
    print("Personal Cognitive Garden demo")
    print("=" * 32)
    print()
    print(f"1. Session: {summary['session_id']} ({summary['session_type']})")
    print(f"2. Development class: {summary['development_class']}")
    print(f"3. Developmental: {summary['is_developmental']}")
    print()
    print("4. Human skill delta:")
    for skill in summary["human_skill_delta"]:
        print(f"   - {skill}")
    print()
    print(f"5. Capital effect: {summary['capital_effect']}")
    print(f"6. Practice needed: {summary['practice_needed']}")
    print(f"7. Compounding score: {summary['compounding_score']}")
    print()
    print(f"8. Proposed status: {summary['proposed_status']}")
    print(f"9. Review: {summary['review_decision']} by {summary['reviewed_by']}")
    print()
    print("10. Accepted graph nodes:")
    for node in summary["accepted_nodes"]:
        print(f"   - {node}")
    print()
    print("Invariant: A session may inform memory, but only developmental sessions should compound human capital.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Personal Cognitive Garden example demo.")
    parser.add_argument(
        "--example-dir",
        type=Path,
        default=DEFAULT_EXAMPLE_DIR,
        help="Directory containing session_summary.json, proposed_update.json, and accepted_graph_state.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable summary JSON instead of the human walkthrough.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    example_dir = args.example_dir.resolve()

    try:
        session_summary = load_json(example_dir / "session_summary.json")
        proposed_update = load_json(example_dir / "proposed_update.json")
        graph_state = load_json(example_dir / "accepted_graph_state.json")
        summary = summarize(session_summary, proposed_update, graph_state)
    except DemoInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_human(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
