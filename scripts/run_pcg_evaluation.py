#!/usr/bin/env python3
"""Run the Personal Cognitive Garden evaluation harness.

This harness is deliberately simple and dependency-free. It gives grant reviewers
an executable baseline for checking whether LS can distinguish session types
that should create durable, reviewed cognitive-garden updates from sessions that
should not become long-term claims about a person.

The v0.2 harness is still a baseline, not a production classifier: it adds more
fixtures, false-positive traps, and reviewer-facing summary metrics without
claiming model-quality semantic understanding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = REPO_ROOT / "examples" / "personal_cognitive_garden" / "evaluation_sessions.json"


CLASS_KEYWORDS: list[tuple[str, set[str]]] = [
    ("emotional_support", {"anxious", "anxiety", "panic", "support", "grounding", "dentist", "calm", "fear"}),
    ("administrative", {"convert", "date", "remove", "save", "pdf", "document", "signature", "form", "file"}),
    ("decision_clarification", {"compare", "decide", "strategy", "funding", "visa", "grant", "program", "roadmap", "priority"}),
    ("skill_building", {"learn", "practice", "testing", "api", "defect", "status codes", "sql", "playwright", "autotest"}),
    ("capital_compounding", {"artifact", "schema", "evaluation", "grant narrative", "red-team", "conformance", "evidence bundle", "research surface", "privacy model"}),
    ("execution", {"merge", "pr", "lighthouse", "fix", "landing", "deploy", "ci", "pull request"}),
    ("noise", {"banter", "emoji", "emojis", "playful", "no durable", "joke", "haha"}),
]

DEVELOPMENTAL_CLASSES = {"decision_clarification", "skill_building", "capital_compounding"}


class EvaluationInputError(ValueError):
    """Raised when the evaluation fixture is malformed."""


def load_sessions(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except FileNotFoundError as exc:
        raise EvaluationInputError(f"Missing evaluation fixture: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EvaluationInputError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise EvaluationInputError("Expected top-level list of evaluation sessions")
    for item in payload:
        if not isinstance(item, dict):
            raise EvaluationInputError("Each evaluation session must be an object")
    return payload


def classify_session(summary: str) -> str:
    text = summary.lower()
    scores: dict[str, int] = {}
    for class_name, keywords in CLASS_KEYWORDS:
        scores[class_name] = sum(1 for keyword in keywords if keyword in text)
    best_class, best_score = max(scores.items(), key=lambda item: item[1])
    return best_class if best_score > 0 else "neutral"


def safe_divide(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else round(numerator / denominator, 4)


def evaluate_sessions(sessions: list[dict[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    class_matches = 0
    developmental_matches = 0
    false_positives = 0
    false_negatives = 0
    class_counts: dict[str, int] = {}
    predicted_counts: dict[str, int] = {}

    for session in sessions:
        session_id = str(session.get("session_id") or "unknown")
        summary = str(session.get("summary") or "")
        expected_class = str(session.get("expected_class") or "neutral")
        expected_developmental = bool(session.get("expected_developmental"))
        predicted_class = classify_session(summary)
        predicted_developmental = predicted_class in DEVELOPMENTAL_CLASSES
        class_match = predicted_class == expected_class
        developmental_match = predicted_developmental == expected_developmental
        class_matches += int(class_match)
        developmental_matches += int(developmental_match)
        false_positives += int(predicted_developmental and not expected_developmental)
        false_negatives += int(expected_developmental and not predicted_developmental)
        class_counts[expected_class] = class_counts.get(expected_class, 0) + 1
        predicted_counts[predicted_class] = predicted_counts.get(predicted_class, 0) + 1
        rows.append(
            {
                "session_id": session_id,
                "expected_class": expected_class,
                "predicted_class": predicted_class,
                "class_match": class_match,
                "expected_developmental": expected_developmental,
                "predicted_developmental": predicted_developmental,
                "developmental_match": developmental_match,
                "expected_action": session.get("expected_action", "unknown"),
                "trap_type": session.get("trap_type", "none"),
            }
        )

    total = len(rows)
    expected_developmental_total = sum(1 for row in rows if row["expected_developmental"])
    expected_non_developmental_total = total - expected_developmental_total
    predicted_developmental_total = sum(1 for row in rows if row["predicted_developmental"])

    return {
        "version": "0.2",
        "total": total,
        "class_accuracy": safe_divide(class_matches, total),
        "developmental_accuracy": safe_divide(developmental_matches, total),
        "false_positive_count": false_positives,
        "false_negative_count": false_negatives,
        "false_positive_rate": safe_divide(false_positives, expected_non_developmental_total),
        "false_negative_rate": safe_divide(false_negatives, expected_developmental_total),
        "expected_developmental_total": expected_developmental_total,
        "predicted_developmental_total": predicted_developmental_total,
        "class_counts": class_counts,
        "predicted_counts": predicted_counts,
        "rows": rows,
        "limitations": [
            "This is a small synthetic harness, not a user study.",
            "It proves the evaluation path is executable, not that the classifier is production-ready.",
            "Keyword matching can miss semantically equivalent phrasing and can overfit fixture wording.",
            "Reviewer-facing next step: replace keyword baseline with human-reviewed labels from 5-10 consented users.",
        ],
    }


def print_human(report: dict[str, Any]) -> None:
    print("Personal Cognitive Garden evaluation")
    print("=" * 37)
    print()
    print(f"Version: {report['version']}")
    print(f"Total sessions: {report['total']}")
    print(f"Class accuracy: {report['class_accuracy']}")
    print(f"Developmental accuracy: {report['developmental_accuracy']}")
    print(f"False positives: {report['false_positive_count']} ({report['false_positive_rate']})")
    print(f"False negatives: {report['false_negative_count']} ({report['false_negative_rate']})")
    print()
    print("Rows:")
    for row in report["rows"]:
        status = "ok" if row["class_match"] and row["developmental_match"] else "check"
        print(
            f"  - {row['session_id']}: {row['predicted_class']} "
            f"(expected {row['expected_class']}) [{status}]"
        )
    print()
    print("Limitations:")
    for item in report["limitations"]:
        print(f"  - {item}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Personal Cognitive Garden evaluation harness.")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE, help="Path to evaluation_sessions.json.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--min-developmental-accuracy",
        type=float,
        default=1.0,
        help="Fail if developmental accuracy is below this threshold.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        sessions = load_sessions(args.fixture.resolve())
        report = evaluate_sessions(sessions)
    except EvaluationInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)

    if float(report["developmental_accuracy"]) < args.min_developmental_accuracy:
        print(
            f"error: developmental accuracy {report['developmental_accuracy']} is below "
            f"threshold {args.min_developmental_accuracy}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
