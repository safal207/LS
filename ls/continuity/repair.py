from __future__ import annotations

_REPAIR_PROMPTS: dict[str, str] = {
    "missing_pr_context": (
        "I should not continue from an inferred PR state. Please attach the PR, "
        "provide the PR number, or restate the exact change set before I continue."
    ),
    "session_type_mismatch": (
        "I may have moved into problem-solving while you needed support. "
        "Do you want presence, analysis, or next steps right now?"
    ),
    "memory_write_without_consent": (
        "Before this becomes durable memory, I need explicit human review and consent."
    ),
    "action_without_causal_parent": (
        "Before this action can proceed, I need declared intent, source evidence, "
        "causal parent, reversibility status, and explicit approval."
    ),
    "none": "Shared context appears sufficient to continue.",
    "unknown": "I may be missing shared context. Please restate the last agreed point before I continue.",
}


def repair_prompt_for(rupture_type: str) -> str:
    """Return the stable repair prompt for a rupture type."""

    return _REPAIR_PROMPTS.get(rupture_type, _REPAIR_PROMPTS["unknown"])
