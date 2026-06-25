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

from modules.trusted_runtime.relationship_loss_track_center import (  # noqa: E402
    RELATIONSHIP_LOSS_TRACK,
)
from modules.trusted_runtime.track_center_router import (  # noqa: E402
    TrackCenterEnvelope,
    route_track_center_envelope,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Track Center Router demo.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build/track-center-router",
    )
    return parser.parse_args()


def relationship_payload(event_id: str) -> dict[str, Any]:
    return {
        "schema_version": "trusted_runtime.relationship_loss_event.v0.1",
        "event_id": event_id,
        "relationship_id": "relationship:mentor",
        "subject_id": "human:mentor",
        "event_type": "REMEMBERED_INFLUENCE",
        "entity_status": "DECEASED",
        "knowledge_class": "MEMORY",
        "statement": "Remembered evidence-first discipline remains influential.",
        "occurred_at": "2026-06-25T05:00:00Z",
        "confidence": 0.86,
        "evidence_refs": ["evidence:router-demo:1"],
        "identity_candidate_statement": (
            "Preserve evidence-first discipline in bounded reviews."
        ),
        "identity_scope": "relationships",
        "identity_repeat_key": "mentor:evidence-first-review",
        "metadata": {"source": "track-center-router-demo"},
    }


def main() -> int:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    valid = relationship_payload("relationship-event:router:valid")
    invalid = relationship_payload("relationship-event:router:invalid")
    invalid.pop("subject_id")

    envelopes = (
        TrackCenterEnvelope(
            envelope_id="track-envelope:valid",
            route_key=RELATIONSHIP_LOSS_TRACK,
            payload=valid,
            submitted_at="2026-06-25T05:10:00Z",
            source_refs=("source:demo:valid",),
        ),
        TrackCenterEnvelope(
            envelope_id="track-envelope:unknown",
            route_key="projects.future",
            payload={"event_id": "project-event:future:1"},
            submitted_at="2026-06-25T05:11:00Z",
            source_refs=("source:demo:unknown",),
        ),
        TrackCenterEnvelope(
            envelope_id="track-envelope:invalid",
            route_key=RELATIONSHIP_LOSS_TRACK,
            payload=invalid,
            submitted_at="2026-06-25T05:12:00Z",
            source_refs=("source:demo:invalid",),
        ),
    )

    results = [
        route_track_center_envelope(
            envelope,
            processed_at=f"2026-06-25T05:{20 + index:02d}:00Z",
        )
        for index, envelope in enumerate(envelopes)
    ]

    for result in results:
        write_json(
            args.output / (result.envelope_id.replace(":", "-") + ".json"),
            result.to_dict(),
        )

    summary = {
        "schema_version": "trusted_runtime.track_center_router_demo.v0.1",
        "result": "PASS",
        "decisions": [
            {
                "envelope_id": result.envelope_id,
                "decision": result.decision.value,
                "nested_continuity_decision": (
                    result.routed_result.assessment.decision.value
                    if result.routed_result
                    else None
                ),
                "relational_self_mutation_allowed": False,
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
