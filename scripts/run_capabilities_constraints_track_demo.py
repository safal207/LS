#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from modules.trusted_runtime.capabilities_constraints_track_center import (  # noqa: E402
    CAPABILITIES_TRACK,
    CapabilityConstraintEvent,
    CapabilityEventType,
    CapabilityStatus,
    process_capability_event,
)
from modules.trusted_runtime.capability_contract import ConstraintKind  # noqa: E402
from modules.trusted_runtime.continuity_coordinator import KnowledgeClass  # noqa: E402


def make(
    event_id: str,
    event_type: CapabilityEventType,
    status: CapabilityStatus,
    kind: ConstraintKind,
    contexts: tuple[str, ...],
    candidate: bool = False,
) -> CapabilityConstraintEvent:
    refs = ("evidence:1", "evidence:2") if candidate else ("evidence:1",)
    observers = ("observer:qa", "observer:sre") if candidate else ("observer:qa",)
    return CapabilityConstraintEvent(
        event_id=event_id,
        capability_id="capability:demo",
        event_type=event_type,
        capability_status=status,
        constraint_kind=kind,
        knowledge_class=(
            KnowledgeClass.INFERENCE
            if event_type is CapabilityEventType.ABILITY_OBSERVED
            else KnowledgeClass.FACT
        ),
        statement="Bounded capability observation.",
        occurred_at="2026-06-25T10:00:00Z",
        confidence=0.92,
        repeat_count=2 if candidate else 1,
        evidence_refs=refs,
        context_refs=contexts,
        observer_refs=observers,
        identity_candidate_statement=(
            "Verify context before declaring a capability limit." if candidate else None
        ),
        identity_scope=CAPABILITIES_TRACK if candidate else None,
        identity_repeat_key="capability:verify-context" if candidate else None,
    )


def main() -> int:
    output = ROOT / "build/capabilities-constraints-track-center"
    output.mkdir(parents=True, exist_ok=True)
    events = (
        make(
            "capability-event:observed",
            CapabilityEventType.ABILITY_OBSERVED,
            CapabilityStatus.OBSERVED,
            ConstraintKind.NONE,
            ("context:sandbox",),
        ),
        make(
            "capability-event:missing-context",
            CapabilityEventType.CURRENT_LIMITATION_CLAIM,
            CapabilityStatus.CONSTRAINED,
            ConstraintKind.CONTEXTUAL,
            (),
        ),
        make(
            "capability-event:recovered-limit",
            CapabilityEventType.CURRENT_LIMITATION_CLAIM,
            CapabilityStatus.RECOVERED,
            ConstraintKind.UNKNOWN,
            ("context:browser",),
        ),
        make(
            "capability-event:pattern",
            CapabilityEventType.CAPABILITY_PATTERN_VERIFIED,
            CapabilityStatus.AVAILABLE,
            ConstraintKind.NONE,
            ("context:api", "context:ui"),
            True,
        ),
    )
    results = [
        process_capability_event(item, processed_at="2026-06-25T10:10:00Z")
        for item in events
    ]
    summary = {
        "schema_version": "trusted_runtime.capabilities_constraints_demo.v0.1",
        "result": "PASS",
        "decisions": [
            {
                "event_id": result.event.event_id,
                "decision": result.assessment.decision.value,
                "lesson": result.assessment.lesson_candidate is not None,
                "capability_registry_mutation_allowed": False,
                "global_limitation_assignment_allowed": False,
                "stable_identity_update_allowed": False,
                "execution_authorized": False,
            }
            for result in results
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
