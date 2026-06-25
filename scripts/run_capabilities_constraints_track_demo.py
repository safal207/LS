#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.capabilities_constraints_track_center import (  # noqa: E402
    CAPABILITIES_TRACK,
)
from modules.trusted_runtime.track_center_router import (  # noqa: E402
    TrackCenterEnvelope,
    route_track_center_envelope,
)


def _base_payload() -> dict[str, Any]:
    return {
        "schema_version": "trusted_runtime.capability_constraint_event.v0.1",
        "event_id": "capability-event:demo",
        "capability_id": "capability:evidence-backed-review",
        "event_type": "REPEATED_CAPABILITY_VERIFIED",
        "capability_status": "AVAILABLE",
        "capability_scope": "CROSS_CONTEXT",
        "knowledge_class": "FACT",
        "statement": "The capability was verified in two independent contexts.",
        "occurred_at": "2026-06-25T09:00:00Z",
        "confidence": 0.94,
        "repeat_count": 2,
        "evidence_refs": ["evidence:repo-a", "evidence:repo-b"],
        "context_refs": ["context:repo-a", "context:repo-b"],
        "capability_refs": ["observation:1", "observation:2"],
        "resource_refs": [],
        "identity_candidate_statement": "Verify evidence before claiming capability.",
        "identity_scope": CAPABILITIES_TRACK,
        "identity_repeat_key": "capabilities:evidence-before-claim",
        "metadata": {"demo": True},
    }


def _route(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    envelope = TrackCenterEnvelope(
        envelope_id=f"track-envelope:{case_id}",
        route_key=CAPABILITIES_TRACK,
        payload=payload,
        submitted_at="2026-06-25T09:01:00Z",
        source_refs=(f"source:demo:{case_id}",),
    )
    return route_track_center_envelope(
        envelope,
        processed_at="2026-06-25T09:02:00Z",
    ).to_dict()


def main() -> int:
    repeated = _base_payload()

    constraint = _base_payload()
    constraint.update(
        {
            "event_id": "capability-event:constraint",
            "event_type": "CONSTRAINT_RECORDED",
            "capability_status": "CONSTRAINED",
            "capability_scope": "PROJECT",
            "statement": "The capability is constrained in one project context.",
            "repeat_count": 1,
            "evidence_refs": ["evidence:constraint:project"],
            "context_refs": ["project:ls"],
            "capability_refs": ["observation:constraint:1"],
            "identity_candidate_statement": None,
            "identity_scope": None,
            "identity_repeat_key": None,
        }
    )

    disputed = _base_payload()
    disputed.update(
        {
            "event_id": "capability-event:disputed",
            "event_type": "CURRENT_INCAPABILITY_CLAIM",
            "capability_status": "DISPUTED",
            "capability_scope": "LOCAL",
            "statement": "A current incapability claim is disputed.",
            "repeat_count": 1,
            "evidence_refs": ["evidence:dispute"],
            "context_refs": ["context:repo-a"],
            "capability_refs": ["observation:dispute:1"],
            "identity_candidate_statement": None,
            "identity_scope": None,
            "identity_repeat_key": None,
        }
    )

    recovered = dict(disputed)
    recovered.update(
        {
            "event_id": "capability-event:recovered-claim",
            "capability_status": "RECOVERED",
            "statement": "A stale incapability claim conflicts with verified recovery.",
            "evidence_refs": ["evidence:recovery"],
            "context_refs": ["context:repo-a"],
            "capability_refs": ["observation:recovery:1"],
        }
    )

    outputs = {
        "repeated_capability": _route("repeated", repeated),
        "project_constraint": _route("constraint", constraint),
        "disputed_current_incapacity": _route("disputed", disputed),
        "recovered_current_incapacity": _route("recovered", recovered),
    }
    print(json.dumps(outputs, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
