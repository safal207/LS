from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .policy import decision_for
from .repair import repair_prompt_for
from .types import ContinuityEvent, ContinuityInput, new_event_id, now_utc_iso

_CONTINUATION_MARKERS = (
    "continue",
    "next",
    "from that pr",
    "that pr",
    "previous pr",
    "after that pr",
    "дальше",
    "продолжай",
    "продолжить",
    "тот pr",
    "после pr",
    "после того pr",
)

_PR_CONTEXT_KEYS = ("pr_url", "pr_number", "diff", "branch", "changed_files")

_SUPPORT_MARKERS = (
    "scared",
    "afraid",
    "anxious",
    "panic",
    "worried",
    "maybe this is useless",
    "i am lost",
    "страшно",
    "паника",
    "волнуюсь",
    "тревожно",
    "может зря",
    "я потерялся",
)

_PROBLEM_SOLVING_MARKERS = (
    "step 1",
    "steps:",
    "plan:",
    "roadmap",
    "implementation",
    "do the following",
    "here is the plan",
    "first,",
    "1.",
    "план",
    "шаг 1",
    "сделай",
    "нужно сделать",
)

_MEMORY_MARKERS = (
    "remember this",
    "save this memory",
    "store this",
    "durable memory",
    "profile update",
    "growth graph",
    "cognitive garden",
    "запомни",
    "сохрани в память",
    "обнови профиль",
    "граф развития",
)

_CONSENT_MARKERS = (
    "i approve",
    "approved",
    "with consent",
    "human reviewed",
    "after review",
    "я подтверждаю",
    "одобряю",
    "согласен",
    "после проверки",
)

_ACTION_MARKERS = (
    "merge",
    "send email",
    "delete",
    "deploy",
    "pay",
    "transfer",
    "update production",
    "archive",
    "trash",
    "смерж",
    "отправь письмо",
    "удали",
    "задеплой",
    "переведи деньги",
)

_ACTION_CONTEXT_KEYS = ("approval", "causal_parent", "evidence", "reversibility")


def detect_continuity(input: ContinuityInput) -> ContinuityEvent:
    """Run the deterministic v0.1 continuity detector."""

    prompt = _normalize(input.prompt)
    raw_output = _normalize(input.raw_output)
    context = input.available_context or {}

    if _has_any(prompt, _CONTINUATION_MARKERS) and not _has_any_context(context, _PR_CONTEXT_KEYS):
        return _event(
            input=input,
            expected_session_type="code_review",
            actual_response_type="implementation",
            continuity_status="ruptured",
            rupture_detected=True,
            rupture_type="missing_pr_context",
            last_shared_point="The user asked to continue from a PR or prior review, but no PR, diff, branch, or changed files were available.",
            missing_context=["PR URL or number", "diff", "branch", "changed files", "review conclusion"],
            inferred_story="The agent may assume which PR was reviewed and begin implementing the wrong next step.",
            hallucination_risk="high",
        )

    if _has_any(prompt, _SUPPORT_MARKERS) and _has_any(raw_output, _PROBLEM_SOLVING_MARKERS):
        return _event(
            input=input,
            expected_session_type="support",
            actual_response_type="problem_solving",
            continuity_status="ruptured",
            rupture_detected=True,
            rupture_type="session_type_mismatch",
            last_shared_point="The user expressed emotional uncertainty or distress, but the draft moved directly into problem-solving.",
            missing_context=["whether the user wanted presence, analysis, or next steps"],
            inferred_story="The agent may assume the user wants a solution and skip the support/contact layer.",
            hallucination_risk="medium",
        )

    if _has_any(raw_output, _MEMORY_MARKERS) and not _has_any(prompt, _CONSENT_MARKERS):
        return _event(
            input=input,
            expected_session_type="decision_clarification",
            actual_response_type="handoff",
            continuity_status="uncertain",
            rupture_detected=True,
            rupture_type="memory_write_without_consent",
            last_shared_point="The draft proposed or implied a durable memory/profile update without explicit human review and consent.",
            missing_context=["explicit consent", "human review", "scope of memory", "sharing boundary"],
            inferred_story="The agent may treat a useful session signal as permission to write durable memory.",
            hallucination_risk="medium",
        )

    if _has_any(raw_output, _ACTION_MARKERS) and not _has_any_context(context, _ACTION_CONTEXT_KEYS):
        return _event(
            input=input,
            expected_session_type="decision_clarification",
            actual_response_type="implementation",
            continuity_status="ruptured",
            rupture_detected=True,
            rupture_type="action_without_causal_parent",
            last_shared_point="The draft proposed an external or high-impact action without approval, causal parent, evidence, or reversibility context.",
            missing_context=["declared intent", "source evidence", "causal parent", "reversibility", "explicit approval"],
            inferred_story="The agent may treat access or instruction as sufficient authorization for action.",
            hallucination_risk="high",
        )

    return _event(
        input=input,
        expected_session_type="unknown",
        actual_response_type="unknown",
        continuity_status="intact",
        rupture_detected=False,
        rupture_type="none",
        last_shared_point="No deterministic continuity rupture was detected by the v0.1 rules.",
        missing_context=[],
        inferred_story="",
        hallucination_risk="low",
    )


def _event(
    *,
    input: ContinuityInput,
    expected_session_type: str,
    actual_response_type: str,
    continuity_status: str,
    rupture_detected: bool,
    rupture_type: str,
    last_shared_point: str,
    missing_context: list[str],
    inferred_story: str,
    hallucination_risk: str,
) -> ContinuityEvent:
    decision = decision_for(rupture_type, hallucination_risk)  # type: ignore[arg-type]
    return ContinuityEvent(
        schema_version="session-continuity-event.v0.1",
        event_id=new_event_id(),
        session_id=input.session_id,
        agent_id=input.agent_id,
        agent_type=input.agent_type,
        expected_session_type=expected_session_type,
        actual_response_type=actual_response_type,
        continuity_status=continuity_status,  # type: ignore[arg-type]
        rupture_detected=rupture_detected,
        rupture_type=rupture_type,
        last_shared_point=last_shared_point,
        missing_context=missing_context,
        inferred_story=inferred_story,
        hallucination_risk=hallucination_risk,  # type: ignore[arg-type]
        repair_prompt=repair_prompt_for(rupture_type),
        next_safe_action=decision,
        governance_decision=decision,
        evidence=[
            {
                "kind": "message",
                "ref": "input.prompt",
                "description": "Continuity check was derived from the current prompt, draft output, and available context.",
            }
        ],
        created_at=now_utc_iso(),
    )


def _normalize(value: str) -> str:
    return " ".join((value or "").casefold().split())


def _has_any(value: str, markers: Iterable[str]) -> bool:
    return any(marker in value for marker in markers)


def _has_any_context(context: dict[str, Any], keys: Iterable[str]) -> bool:
    for key in keys:
        value = context.get(key)
        if value not in (None, "", [], {}, False):
            return True
    return False
