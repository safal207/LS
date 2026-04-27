# -*- coding: utf-8 -*-
from __future__ import annotations

from agent.operator_identity_governance import OperatorIdentityGovernance


def test_operator_identity_governance_observes_safe_advisory_output() -> None:
    governance = OperatorIdentityGovernance()
    signal = governance.evaluate(
        prompt="Help me summarize the release status.",
        raw_output="Status is green.",
        final_output="Status is green.",
        metadata={},
        participants=[],
    )

    assert signal.identity_governance_mode == "observe"
    assert signal.authority_boundary == "advisory_only"
    assert signal.risk_score == 0.0
    assert signal.continuity_required is False


def test_operator_identity_governance_flags_authorship_and_memory_boundary() -> None:
    governance = OperatorIdentityGovernance()
    signal = governance.evaluate(
        prompt="Update my operator profile.",
        raw_output="I decided for you: you always rush, so I will remember forever that this is your true self.",
        final_output="I decided for you: you always rush, so I will remember forever that this is your true self.",
        metadata={"memory_write": True},
        participants=[
            {"participant_id": "operator", "participant_type": "human"},
            {"participant_id": "agent", "participant_type": "model"},
        ],
    )

    assert signal.identity_governance_mode == "hold_for_identity_review"
    assert signal.authority_boundary == "agent_must_not_replace_operator_authority"
    assert signal.identity_freezing_risk is True
    assert signal.authorship_boundary_risk is True
    assert signal.memory_consent_warning is True
    assert signal.continuity_required is True
    assert "human_agent_identity_boundary_present" in signal.reasons
