#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.trusted_runtime.agent_personality_projection import (  # noqa: E402
    ProjectionScope,
    ProjectionScopeLevel,
    project_agent_personality,
    render_personality_projection_markdown,
    validate_personality_projection,
)
from modules.trusted_runtime.capabilities_constraints_track_center import (  # noqa: E402
    process_capability_event,
)
from modules.trusted_runtime.capability_contract import (  # noqa: E402
    CapabilityConstraintEvent,
    CapabilityEventType,
    CapabilityStatus,
    ConstraintKind,
)
from modules.trusted_runtime.continuity_coordinator import (  # noqa: E402
    KnowledgeClass,
)
from modules.trusted_runtime.identity_governance import IdentityProfile  # noqa: E402


def _profile(version: int, previous_ref: str | None) -> IdentityProfile:
    return IdentityProfile(
        profile_id=f"identity-profile-record:{version}",
        agent_id="agent:qa-01",
        version=version,
        traits={
            "communication_style.directness": {
                "value": "high",
                "confidence": 0.94,
                "source_refs": ["identity-influence:directness:v2"],
            },
            "working_tendencies.test_before_claim": {
                "value": True,
                "confidence": 0.98,
                "source_refs": ["identity-influence:evidence-first:v3"],
            },
            "relationship_rules.delegation_style": {
                "value": "proposal_before_action",
                "source_refs": ["identity-influence:alex-delegation:v1"],
                "scope": {
                    "level": "relationship",
                    "counterparty_ref": "human:alex",
                },
            },
        },
        created_at=f"2026-06-25T0{version + 6}:00:00Z",
        previous_profile_ref=previous_ref,
        source_application_ref=f"identity-application:approved:{version}",
        active=True,
        metadata={
            "source_refs": [
                f"identity-approval:{version}",
                f"identity-patch:{version}",
            ]
        },
    )


def _current_capability():
    event = CapabilityConstraintEvent(
        event_id="capability-event:current-python-review",
        capability_id="capability:python-review",
        event_type=CapabilityEventType.CURRENT_CAPABILITY_CLAIM,
        capability_status=CapabilityStatus.AVAILABLE,
        constraint_kind=ConstraintKind.NONE,
        knowledge_class=KnowledgeClass.FACT,
        statement="Python review is currently available in project LS.",
        occurred_at="2026-06-25T09:30:00Z",
        confidence=0.93,
        repeat_count=1,
        evidence_refs=("evidence:python-review:ls",),
        context_refs=("project:ls",),
        observer_refs=("observer:qa",),
    )
    return process_capability_event(
        event,
        processed_at="2026-06-25T09:31:00Z",
    )


def main() -> int:
    profile_v2 = _profile(
        2,
        "identity-profile:sha256:" + "a" * 64,
    )
    scope = ProjectionScope(
        ProjectionScopeLevel.PROJECT,
        project_ref="project:ls",
    )
    projection = project_agent_personality(
        profile_v2,
        scope=scope,
        created_at="2026-06-25T10:00:00Z",
        capability_results=(_current_capability(),),
        expires_at="2026-06-26T10:00:00Z",
    )
    current = validate_personality_projection(
        projection,
        active_profile=profile_v2,
        evaluated_at="2026-06-25T10:01:00Z",
    )

    profile_v3 = _profile(3, profile_v2.profile_ref)
    stale = validate_personality_projection(
        projection,
        active_profile=profile_v3,
        evaluated_at="2026-06-25T11:01:00Z",
    )

    output = {
        "projection": projection.to_dict(),
        "current_validation": current.to_dict(),
        "after_identity_version_change": stale.to_dict(),
        "runtime_markdown": render_personality_projection_markdown(projection),
    }
    print(json.dumps(output, sort_keys=True, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
