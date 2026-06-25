from __future__ import annotations

from dataclasses import replace

import pytest

from test_trusted_runtime_authorization_decision_gate import _evaluate, _request
from trusted_runtime.authorization_contract import (
    ApprovalState,
    AuthorityState,
    AuthorizationDecision,
    AuthorizationReason,
    CapabilityState,
    PolicyEffect,
)


@pytest.mark.parametrize(
    ("request", "mismatch_reason", "blocked_reason"),
    [
        (
            replace(
                _request(),
                policy=replace(
                    _request().policy,
                    effect=PolicyEffect.DENY,
                    scope_ref="scope:staging",
                ),
            ),
            AuthorizationReason.POLICY_SCOPE_MISMATCH,
            AuthorizationReason.POLICY_DENIED,
        ),
        (
            replace(
                _request(),
                authority=replace(
                    _request().authority,
                    state=AuthorityState.REVOKED,
                    scope_ref="scope:staging",
                ),
            ),
            AuthorizationReason.AUTHORITY_SCOPE_MISMATCH,
            AuthorizationReason.AUTHORITY_REVOKED,
        ),
        (
            replace(
                _request(),
                capability=replace(
                    _request().capability,
                    state=CapabilityState.UNAVAILABLE,
                    capability_id="capability:other",
                ),
            ),
            AuthorizationReason.CAPABILITY_MISMATCH,
            AuthorizationReason.CAPABILITY_UNAVAILABLE,
        ),
        (
            replace(
                _request(),
                approval=replace(
                    _request().approval,
                    state=ApprovalState.DENIED,
                    scope_ref="scope:staging",
                ),
            ),
            AuthorizationReason.APPROVAL_SCOPE_MISMATCH,
            AuthorizationReason.APPROVAL_DENIED,
        ),
    ],
)
def test_irrelevant_negative_evidence_escalates_instead_of_blocking(
    request,
    mismatch_reason: AuthorizationReason,
    blocked_reason: AuthorizationReason,
) -> None:
    result = _evaluate(request)
    assert result.decision is AuthorizationDecision.ESCALATE
    assert mismatch_reason in result.reason_codes
    assert blocked_reason not in result.reason_codes
