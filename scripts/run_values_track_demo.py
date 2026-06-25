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
from modules.trusted_runtime.values_track_center import (  # noqa: E402
    ValueEvent,
    ValueEventType,
    ValueStatus,
    process_value_event,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Values Track Center demo.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build/values-track-center",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    events = (
        ValueEvent(
            event_id="value-event:single-signal",
            value_key="value:evidence-first",
            event_type=ValueEventType.VALUE_SIGNAL_OBSERVED,
            value_status=ValueStatus.CANDIDATE,
            knowledge_class=KnowledgeClass.INFERENCE,
            statement="One statement may suggest evidence-first thinking.",
            occurred_at="2026-06-25T07:00:00Z",
            confidence=0.55,
            repeat_count=1,
            evidence_refs=("evidence:value:single",),
            context_refs=("context:conversation",),
        ),
        ValueEvent(
            event_id="value-event:repeated-practice",
            value_key="value:evidence-first",
            event_type=ValueEventType.VALUE_PRACTICED,
            value_status=ValueStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            statement="Evidence-first behavior was observed across contexts.",
            occurred_at="2026-06-25T07:02:00Z",
            confidence=0.93,
            repeat_count=3,
            evidence_refs=("evidence:value:work", "evidence:value:family"),
            context_refs=("context:work", "context:family"),
            identity_candidate_statement=(
                "Prefer evidence before confident conclusions."
            ),
            identity_scope="values",
            identity_repeat_key="value:evidence-first:cross-context",
        ),
        ValueEvent(
            event_id="value-event:contested-current",
            value_key="value:speed-over-care",
            event_type=ValueEventType.CURRENT_VALUE_CLAIM,
            value_status=ValueStatus.CONTESTED,
            knowledge_class=KnowledgeClass.FACT,
            statement="A contested value is claimed as current guidance.",
            occurred_at="2026-06-25T07:04:00Z",
            confidence=0.7,
            repeat_count=2,
            evidence_refs=("evidence:value:conflict",),
            context_refs=("context:project",),
        ),
        ValueEvent(
            event_id="value-event:retired-current",
            value_key="value:always-available",
            event_type=ValueEventType.CURRENT_VALUE_CLAIM,
            value_status=ValueStatus.RETIRED,
            knowledge_class=KnowledgeClass.FACT,
            statement="A retired value is claimed as current guidance.",
            occurred_at="2026-06-25T07:06:00Z",
            confidence=0.8,
            repeat_count=2,
            evidence_refs=("evidence:value:retirement",),
            context_refs=("context:history",),
        ),
        ValueEvent(
            event_id="value-event:mood",
            value_key="value:temporary-optimism",
            event_type=ValueEventType.MOOD_SIGNAL_OBSERVED,
            value_status=ValueStatus.CANDIDATE,
            knowledge_class=KnowledgeClass.INFERENCE,
            statement="A positive mood should not become a durable value.",
            occurred_at="2026-06-25T07:08:00Z",
            confidence=0.6,
            repeat_count=1,
            evidence_refs=("evidence:mood:1",),
            context_refs=("context:moment",),
        ),
    )

    results = [
        process_value_event(
            event,
            processed_at=f"2026-06-25T07:{10 + index:02d}:00Z",
        )
        for index, event in enumerate(events)
    ]

    for result in results:
        write_json(
            args.output / (result.event.event_id.replace(":", "-") + ".json"),
            result.to_dict(),
        )

    summary = {
        "schema_version": "trusted_runtime.values_track_demo.v0.1",
        "result": "PASS",
        "decisions": [
            {
                "event_id": result.event.event_id,
                "value_status": result.event.value_status.value,
                "decision": result.assessment.decision.value,
                "lesson_candidate_emitted": (
                    result.assessment.lesson_candidate is not None
                ),
                "value_registry_mutation_allowed": False,
                "priority_mutation_allowed": False,
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
