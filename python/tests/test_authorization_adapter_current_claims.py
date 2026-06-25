from __future__ import annotations

from dataclasses import replace

import pytest

from test_trusted_runtime_authorization_evidence_adapters import (
    SUBJECT,
    _authority_result,
    _capability_result,
)
from trusted_runtime.authorization_evidence_adapters import (
    authority_evidence_from_result,
    capability_evidence_from_result,
)
from trusted_runtime.capabilities_constraints_track_center import (
    CapabilityEventType,
    process_capability_event,
)
from trusted_runtime.roles_permissions_track_center import (
    RolePermissionEventType,
    process_role_permission_event,
)


def test_historical_capability_event_cannot_become_current_evidence() -> None:
    current = _capability_result()
    historical = process_capability_event(
        replace(current.event, event_type=CapabilityEventType.CAPABILITY_VERIFIED),
        processed_at="2026-06-25T12:11:00Z",
    )
    with pytest.raises(ValueError, match="current capability claim"):
        capability_evidence_from_result(
            historical,
            subject_id=SUBJECT,
            subject_binding_ref="binding:agent-capability:test",
        )


def test_historical_permission_event_cannot_become_current_authority() -> None:
    current = _authority_result()
    historical = process_role_permission_event(
        replace(current.event, event_type=RolePermissionEventType.PERMISSION_GRANTED),
        processed_at="2026-06-25T12:11:00Z",
    )
    with pytest.raises(ValueError, match="current authority claim"):
        authority_evidence_from_result(historical)
