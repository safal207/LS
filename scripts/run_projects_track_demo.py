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
from modules.trusted_runtime.projects_track_center import (  # noqa: E402
    ProjectEvent,
    ProjectEventType,
    ProjectStatus,
    process_project_event,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Projects Track Center demo.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build/projects-track-center",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    events = (
        ProjectEvent(
            event_id="project-event:lesson",
            project_id="project:ls",
            event_type=ProjectEventType.PROJECT_LESSON_RETAINED,
            project_status=ProjectStatus.COMPLETED,
            previous_status=None,
            knowledge_class=KnowledgeClass.MEMORY,
            statement="The completed project retained evidence-first discipline.",
            occurred_at="2026-06-25T06:00:00Z",
            confidence=0.9,
            evidence_refs=("evidence:project:lesson",),
            identity_candidate_statement=(
                "Preserve evidence-first delivery discipline."
            ),
            identity_scope="projects",
            identity_repeat_key="project:ls:evidence-first-delivery",
        ),
        ProjectEvent(
            event_id="project-event:paused-task",
            project_id="project:ls",
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.PAUSED,
            previous_status=None,
            knowledge_class=KnowledgeClass.FACT,
            statement="The paused project is claimed to have a current task.",
            occurred_at="2026-06-25T06:02:00Z",
            confidence=0.88,
            evidence_refs=("evidence:project:paused",),
        ),
        ProjectEvent(
            event_id="project-event:closed-task",
            project_id="project:ls",
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.COMPLETED,
            previous_status=None,
            knowledge_class=KnowledgeClass.INFERENCE,
            statement="A completed project is inferred to have a new task.",
            occurred_at="2026-06-25T06:04:00Z",
            confidence=0.4,
            evidence_refs=("evidence:project:history",),
        ),
        ProjectEvent(
            event_id="project-event:active-task",
            project_id="project:next",
            event_type=ProjectEventType.CURRENT_TASK_CLAIM,
            project_status=ProjectStatus.ACTIVE,
            previous_status=None,
            knowledge_class=KnowledgeClass.FACT,
            statement="An active project has a source-backed current task.",
            occurred_at="2026-06-25T06:06:00Z",
            confidence=0.97,
            evidence_refs=("evidence:project:active-task",),
        ),
    )

    results = [
        process_project_event(
            event,
            processed_at=f"2026-06-25T06:{10 + index:02d}:00Z",
        )
        for index, event in enumerate(events)
    ]

    for result in results:
        write_json(
            args.output / (result.event.event_id.replace(":", "-") + ".json"),
            result.to_dict(),
        )

    summary = {
        "schema_version": "trusted_runtime.projects_track_demo.v0.1",
        "result": "PASS",
        "decisions": [
            {
                "event_id": result.event.event_id,
                "project_status": result.event.project_status.value,
                "decision": result.assessment.decision.value,
                "lesson_candidate_emitted": (
                    result.assessment.lesson_candidate is not None
                ),
                "project_registry_mutation_allowed": False,
                "task_scheduling_allowed": False,
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
