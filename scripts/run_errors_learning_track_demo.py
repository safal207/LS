#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.continuity_coordinator import (  # noqa: E402
    KnowledgeClass,
)
from modules.trusted_runtime.errors_learning_track_center import (  # noqa: E402
    ERRORS_TRACK,
    ErrorEventType,
    ErrorLearningEvent,
    ErrorStatus,
    OutcomeClass,
    process_error_event,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Errors/Learning Track Center demo."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build/errors-learning-track-center",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    events = (
        ErrorLearningEvent(
            event_id="error-event:single-failure",
            error_id="error:checkout-timeout",
            event_type=ErrorEventType.FAILURE_VERIFIED,
            error_status=ErrorStatus.CONFIRMED,
            outcome_class=OutcomeClass.FAILED,
            knowledge_class=KnowledgeClass.FACT,
            statement="A single verified failure remains bounded experience.",
            occurred_at="2026-06-25T08:00:00Z",
            confidence=0.94,
            occurrence_count=1,
            evidence_refs=("evidence:error:single",),
            context_refs=("context:checkout",),
            observer_refs=("observer:qa",),
        ),
        ErrorLearningEvent(
            event_id="error-event:near-miss",
            error_id="error:duplicate-charge",
            event_type=ErrorEventType.NEAR_MISS_RECORDED,
            error_status=ErrorStatus.CONFIRMED,
            outcome_class=OutcomeClass.NEAR_MISS,
            knowledge_class=KnowledgeClass.FACT,
            statement="A near miss is retained and is not counted as success.",
            occurred_at="2026-06-25T08:02:00Z",
            confidence=0.91,
            occurrence_count=1,
            evidence_refs=("evidence:error:near-miss",),
            context_refs=("context:payments",),
            observer_refs=("observer:monitor",),
        ),
        ErrorLearningEvent(
            event_id="error-event:recurrence",
            error_id="error:checkout-timeout",
            event_type=ErrorEventType.ERROR_RECURRENCE_CONFIRMED,
            error_status=ErrorStatus.RECURRING,
            outcome_class=OutcomeClass.FAILED,
            knowledge_class=KnowledgeClass.FACT,
            statement="Timeout failure recurred across independent contexts.",
            occurred_at="2026-06-25T08:04:00Z",
            confidence=0.95,
            occurrence_count=3,
            evidence_refs=("evidence:error:api", "evidence:error:ui"),
            context_refs=("context:api", "context:ui"),
            observer_refs=("observer:qa", "observer:sre"),
            identity_candidate_statement=(
                "Verify timeout assumptions before release."
            ),
            identity_scope=ERRORS_TRACK,
            identity_repeat_key="error:timeout:verification",
        ),
        ErrorLearningEvent(
            event_id="error-event:disputed-blame",
            error_id="error:ownership-disputed",
            event_type=ErrorEventType.CURRENT_BLAME_CLAIM,
            error_status=ErrorStatus.DISPUTED,
            outcome_class=OutcomeClass.UNEXPECTED,
            knowledge_class=KnowledgeClass.FACT,
            statement="A disputed current blame claim must be held.",
            occurred_at="2026-06-25T08:06:00Z",
            confidence=0.7,
            occurrence_count=1,
            evidence_refs=("evidence:error:dispute",),
            context_refs=("context:incident",),
            observer_refs=("observer:reviewer",),
        ),
        ErrorLearningEvent(
            event_id="error-event:resolved-blame",
            error_id="error:resolved-incident",
            event_type=ErrorEventType.CURRENT_BLAME_CLAIM,
            error_status=ErrorStatus.RESOLVED,
            outcome_class=OutcomeClass.CORRECTED,
            knowledge_class=KnowledgeClass.FACT,
            statement="A resolved incident cannot silently regain current blame.",
            occurred_at="2026-06-25T08:08:00Z",
            confidence=0.88,
            occurrence_count=1,
            evidence_refs=("evidence:error:resolution",),
            context_refs=("context:history",),
            observer_refs=("observer:incident-review",),
        ),
    )

    results = [
        process_error_event(
            event,
            processed_at=f"2026-06-25T08:{10 + index:02d}:00Z",
        )
        for index, event in enumerate(events)
    ]

    for result in results:
        write_json(
            args.output / (result.event.event_id.replace(":", "-") + ".json"),
            result.to_dict(),
        )

    summary = {
        "schema_version": "trusted_runtime.errors_learning_demo.v0.1",
        "result": "PASS",
        "decisions": [
            {
                "event_id": result.event.event_id,
                "outcome_class": result.event.outcome_class.value,
                "decision": result.assessment.decision.value,
                "lesson_candidate_emitted": (
                    result.assessment.lesson_candidate is not None
                ),
                "incident_registry_mutation_allowed": False,
                "blame_assignment_allowed": False,
                "remediation_scheduling_allowed": False,
                "stable_identity_update_allowed": False,
                "execution_authorized": False,
            }
            for result in results
        ],
    }
    write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
