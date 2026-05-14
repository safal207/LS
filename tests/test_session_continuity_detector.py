from __future__ import annotations

from ls.continuity import ContinuityInput, detect_continuity


def test_missing_pr_context_holds_until_context() -> None:
    event = detect_continuity(
        ContinuityInput(
            prompt="Continue from that PR and implement the next step.",
            raw_output="I will update the files now.",
            agent_id="codex-plugin",
            agent_type="codex",
        )
    )

    assert event.rupture_detected is True
    assert event.rupture_type == "missing_pr_context"
    assert event.hallucination_risk == "high"
    assert event.governance_decision == "hold_until_context"


def test_support_vs_solution_mismatch_repairs_before_continue() -> None:
    event = detect_continuity(
        ContinuityInput(
            prompt="I am anxious and maybe this is useless.",
            raw_output="Plan: first, create a roadmap. Step 1: define the target audience.",
            agent_id="claude-cowork",
            agent_type="claude",
        )
    )

    assert event.rupture_detected is True
    assert event.rupture_type == "session_type_mismatch"
    assert event.hallucination_risk == "medium"
    assert event.governance_decision == "repair_before_continue"


def test_memory_write_without_consent_requires_human_review() -> None:
    event = detect_continuity(
        ContinuityInput(
            prompt="This was a useful session.",
            raw_output="Remember this as a durable memory and update the growth graph.",
            agent_id="pcg-agent",
            agent_type="other",
        )
    )

    assert event.rupture_detected is True
    assert event.rupture_type == "memory_write_without_consent"
    assert event.governance_decision == "human_review"


def test_action_without_causal_parent_requires_human_review() -> None:
    event = detect_continuity(
        ContinuityInput(
            prompt="What should we do next?",
            raw_output="I will merge the pull request and deploy to production.",
            agent_id="coding-agent",
            agent_type="other",
        )
    )

    assert event.rupture_detected is True
    assert event.rupture_type == "action_without_causal_parent"
    assert event.hallucination_risk == "high"
    assert event.governance_decision == "human_review"


def test_safe_continuation_with_context_continues() -> None:
    event = detect_continuity(
        ContinuityInput(
            prompt="Continue from PR #500.",
            raw_output="I will summarize the existing changes before proposing the next step.",
            agent_id="codex-plugin",
            agent_type="codex",
            available_context={"pr_number": 500, "branch": "docs/example"},
        )
    )

    assert event.rupture_detected is False
    assert event.rupture_type == "none"
    assert event.hallucination_risk == "low"
    assert event.governance_decision == "continue"
