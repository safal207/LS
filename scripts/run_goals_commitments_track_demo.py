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
from modules.trusted_runtime.goals_commitments_track_center import (  # noqa: E402
    GOALS_TRACK,
    CommitmentLevel,
    GoalCommitmentEvent,
    GoalEventType,
    GoalStatus,
    process_goal_event,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Goals/Commitments Track Center demo."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build/goals-commitments-track-center",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    events = (
        GoalCommitmentEvent(
            event_id="goal-event:wish",
            goal_id="goal:learn-language",
            event_type=GoalEventType.WISH_OBSERVED,
            goal_status=GoalStatus.PROPOSED,
            commitment_level=CommitmentLevel.WISH,
            knowledge_class=KnowledgeClass.INFERENCE,
            statement="A wish is retained without creating duty.",
            occurred_at="2026-06-25T09:00:00Z",
            confidence=0.6,
            repeat_count=1,
            evidence_refs=("evidence:goal:wish",),
            context_refs=("context:conversation",),
            commitment_refs=("signal:wish",),
        ),
        GoalCommitmentEvent(
            event_id="goal-event:active-commitment",
            goal_id="goal:publish-release",
            event_type=GoalEventType.COMMITMENT_DECLARED,
            goal_status=GoalStatus.ACTIVE,
            commitment_level=CommitmentLevel.COMMITMENT,
            knowledge_class=KnowledgeClass.FACT,
            statement="An explicit commitment is recorded as bounded evidence.",
            occurred_at="2026-06-25T09:02:00Z",
            confidence=0.92,
            repeat_count=1,
            evidence_refs=("evidence:goal:commitment",),
            context_refs=("context:project",),
            commitment_refs=("commitment:release",),
        ),
        GoalCommitmentEvent(
            event_id="goal-event:follow-through",
            goal_id="goal:follow-through-pattern",
            event_type=GoalEventType.FOLLOW_THROUGH_VERIFIED,
            goal_status=GoalStatus.COMPLETED,
            commitment_level=CommitmentLevel.COMMITMENT,
            knowledge_class=KnowledgeClass.FACT,
            statement="Follow-through was verified across distinct commitments.",
            occurred_at="2026-06-25T09:04:00Z",
            confidence=0.95,
            repeat_count=2,
            evidence_refs=("evidence:goal:work", "evidence:goal:family"),
            context_refs=("context:work", "context:family"),
            commitment_refs=("commitment:work", "commitment:family"),
            identity_candidate_statement=(
                "Confirm scope before accepting a deadline."
            ),
            identity_scope=GOALS_TRACK,
            identity_repeat_key="goals:scope-before-deadline",
        ),
        GoalCommitmentEvent(
            event_id="goal-event:paused-duty",
            goal_id="goal:paused-project",
            event_type=GoalEventType.CURRENT_DUTY_CLAIM,
            goal_status=GoalStatus.PAUSED,
            commitment_level=CommitmentLevel.COMMITMENT,
            knowledge_class=KnowledgeClass.FACT,
            statement="A paused goal is claimed as a current duty.",
            occurred_at="2026-06-25T09:06:00Z",
            confidence=0.8,
            repeat_count=1,
            evidence_refs=("evidence:goal:pause",),
            context_refs=("context:project",),
            commitment_refs=("commitment:paused",),
        ),
        GoalCommitmentEvent(
            event_id="goal-event:cancelled-duty",
            goal_id="goal:cancelled-project",
            event_type=GoalEventType.CURRENT_DUTY_CLAIM,
            goal_status=GoalStatus.CANCELLED,
            commitment_level=CommitmentLevel.COMMITMENT,
            knowledge_class=KnowledgeClass.FACT,
            statement="A cancelled goal is claimed as a current duty.",
            occurred_at="2026-06-25T09:08:00Z",
            confidence=0.9,
            repeat_count=1,
            evidence_refs=("evidence:goal:cancellation",),
            context_refs=("context:history",),
            commitment_refs=("commitment:cancelled",),
        ),
        GoalCommitmentEvent(
            event_id="goal-event:verified-release",
            goal_id="goal:release-pattern",
            event_type=GoalEventType.COMMITMENT_RELEASE_VERIFIED,
            goal_status=GoalStatus.RETIRED,
            commitment_level=CommitmentLevel.OBLIGATION,
            knowledge_class=KnowledgeClass.FACT,
            statement="Healthy release was verified across distinct obligations.",
            occurred_at="2026-06-25T09:10:00Z",
            confidence=0.93,
            repeat_count=2,
            evidence_refs=("evidence:release:1", "evidence:release:2"),
            context_refs=("context:work", "context:personal"),
            commitment_refs=("obligation:1", "obligation:2"),
            identity_candidate_statement=(
                "Release obligations explicitly when their basis ends."
            ),
            identity_scope=GOALS_TRACK,
            identity_repeat_key="goals:explicit-release",
        ),
    )

    results = [
        process_goal_event(
            event,
            processed_at=f"2026-06-25T09:{12 + index:02d}:00Z",
        )
        for index, event in enumerate(events)
    ]

    for result in results:
        write_json(
            args.output / (result.event.event_id.replace(":", "-") + ".json"),
            result.to_dict(),
        )

    summary = {
        "schema_version": "trusted_runtime.goals_commitments_demo.v0.1",
        "result": "PASS",
        "decisions": [
            {
                "event_id": result.event.event_id,
                "commitment_level": result.event.commitment_level.value,
                "goal_status": result.event.goal_status.value,
                "decision": result.assessment.decision.value,
                "claims_current_duty": (
                    result.observation.claims_current_intention
                ),
                "lesson_candidate_emitted": (
                    result.assessment.lesson_candidate is not None
                ),
                "goal_registry_mutation_allowed": False,
                "obligation_assignment_allowed": False,
                "work_scheduling_allowed": False,
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
