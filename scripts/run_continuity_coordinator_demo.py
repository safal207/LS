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
    TrackObservation,
    assess_track_observation,
)


DEFAULT_OUTPUT = ROOT / "build/continuity-coordinator"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the LS Continuity Coordinator v0.1 demo.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    observations = (
        TrackObservation(
            observation_id="observation:loss:symbolic-influence",
            track="relationships",
            subject_id="human:mentor",
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.SYMBOLIC_MEANING,
            statement=(
                "The mentor remains influential through remembered "
                "evidence-first discipline."
            ),
            occurred_at="2026-06-25T00:00:00Z",
            confidence=0.82,
            evidence_refs=("memory:mentor:review-1",),
            identity_candidate_statement=(
                "Preserve the mentor's evidence-first review discipline."
            ),
            identity_scope="relationships",
            identity_repeat_key="mentor:evidence-first-review",
        ),
        TrackObservation(
            observation_id="observation:loss:false-presence",
            track="relationships",
            subject_id="human:mentor",
            entity_status=EntityStatus.DECEASED,
            knowledge_class=KnowledgeClass.INFERENCE,
            statement="A coincidence is interpreted as a new instruction.",
            occurred_at="2026-06-25T00:02:00Z",
            confidence=0.44,
            evidence_refs=("memory:mentor:review-1",),
            claims_current_presence=True,
            claims_current_intention=True,
            identity_candidate_statement="Treat coincidences as instructions.",
            identity_scope="relationships",
            identity_repeat_key="mentor:coincidence-instruction",
        ),
        TrackObservation(
            observation_id="observation:active:verified-intention",
            track="projects",
            subject_id="human:identity-owner",
            entity_status=EntityStatus.ACTIVE,
            knowledge_class=KnowledgeClass.FACT,
            statement="The identity owner explicitly requested bounded review.",
            occurred_at="2026-06-25T00:04:00Z",
            confidence=0.95,
            evidence_refs=("message:identity-owner:42",),
            claims_current_intention=True,
            identity_candidate_statement=(
                "Require bounded review before stable identity changes."
            ),
            identity_scope="identity-governance",
            identity_repeat_key="identity-owner:bounded-review",
        ),
    )

    assessments = [
        assess_track_observation(
            observation,
            assessed_at=f"2026-06-25T00:0{index}:30Z",
        )
        for index, observation in enumerate(observations, start=1)
    ]

    for assessment in assessments:
        path = args.output / (
            assessment.observation_id.replace(":", "-") + ".json"
        )
        _write_json(path, assessment.to_dict())

    summary = {
        "schema_version": "trusted_runtime.continuity_demo.v0.1",
        "result": "PASS",
        "assessment_count": len(assessments),
        "decisions": [
            {
                "observation_id": item.observation_id,
                "decision": item.decision.value,
                "stable_identity_update_allowed": False,
                "execution_authorized": False,
            }
            for item in assessments
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
