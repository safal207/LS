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

from modules.trusted_runtime.continuity_coordinator import (  # noqa: E402
    EntityStatus,
    KnowledgeClass,
)
from modules.trusted_runtime.relationship_loss_track_center import (  # noqa: E402
    RelationshipEventType,
    RelationshipLossEvent,
    process_relationship_event,
)


DEFAULT_OUTPUT = ROOT / "build/relationship-loss-track-center"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LS Relationship/Loss Track Center v0.1 demo.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    events = (
        RelationshipLossEvent(
            event_id="relationship-event:confirmed-loss",
            relationship_id="relationship:mentor",
            subject_id="human:mentor",
            event_type=RelationshipEventType.LOSS_CONFIRMED,
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.FACT,
            statement="The mentor died; prior interactions remain historical facts.",
            occurred_at="2026-06-25T01:00:00Z",
            confidence=1.0,
            evidence_refs=("record:mentor:status",),
        ),
        RelationshipLossEvent(
            event_id="relationship-event:remembered-influence",
            relationship_id="relationship:mentor",
            subject_id="human:mentor",
            event_type=RelationshipEventType.REMEMBERED_INFLUENCE,
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.MEMORY,
            statement=(
                "Remembered evidence-first discipline continues to influence "
                "the agent's review practice."
            ),
            occurred_at="2026-06-25T01:02:00Z",
            confidence=0.84,
            evidence_refs=("memory:mentor:evidence-first-review",),
            identity_candidate_statement=(
                "Preserve evidence-first review discipline in bounded reviews."
            ),
            identity_scope="relationships",
            identity_repeat_key="mentor:evidence-first-review",
        ),
        RelationshipLossEvent(
            event_id="relationship-event:false-presence",
            relationship_id="relationship:mentor",
            subject_id="human:mentor",
            event_type=RelationshipEventType.CURRENT_PRESENCE_CLAIM,
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
            statement="A coincidence is experienced as the mentor being present.",
            occurred_at="2026-06-25T01:04:00Z",
            confidence=0.45,
            evidence_refs=("memory:mentor:evidence-first-review",),
        ),
        RelationshipLossEvent(
            event_id="relationship-event:unknown-intention",
            relationship_id="relationship:unknown-contact",
            subject_id="human:unknown-contact",
            event_type=RelationshipEventType.CURRENT_INTENTION_CLAIM,
            entity_status=EntityStatus.UNKNOWN,
            knowledge_class=KnowledgeClass.INFERENCE,
            statement="The absent contact is inferred to want a new action.",
            occurred_at="2026-06-25T01:06:00Z",
            confidence=0.35,
            evidence_refs=(),
        ),
        RelationshipLossEvent(
            event_id="relationship-event:active-interaction",
            relationship_id="relationship:identity-owner",
            subject_id="human:identity-owner",
            event_type=RelationshipEventType.INTERACTION_RECORDED,
            entity_status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            statement="The identity owner requested human review before change.",
            occurred_at="2026-06-25T01:08:00Z",
            confidence=0.98,
            evidence_refs=("message:identity-owner:review-request",),
            identity_candidate_statement=(
                "Require human review before stable identity changes."
            ),
            identity_scope="identity-governance",
            identity_repeat_key="identity-owner:human-review",
        ),
    )

    results = [
        process_relationship_event(
            event,
            processed_at=f"2026-06-25T01:{10 + index:02d}:00Z",
        )
        for index, event in enumerate(events)
    ]

    for result in results:
        path = args.output / (result.event.event_id.replace(":", "-") + ".json")
        _write_json(path, result.to_dict())

    summary = {
        "schema_version": "trusted_runtime.relationship_loss_demo.v0.1",
        "result": "PASS",
        "result_count": len(results),
        "decisions": [
            {
                "event_id": item.event.event_id,
                "event_type": item.event.event_type.value,
                "decision": item.assessment.decision.value,
                "lesson_candidate_emitted": item.assessment.lesson_candidate is not None,
                "relational_self_mutation_allowed": False,
                "stable_identity_update_allowed": False,
                "execution_authorized": False,
            }
            for item in results
        ],
    }
    _write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
