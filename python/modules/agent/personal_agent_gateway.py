# -*- coding: utf-8 -*-
"""Personal agent gateway.

Turns raw agent output into one of four operator-facing modes:
- pass_through
- shape_response
- repair_before_send
- hold_or_escalate

Deterministic and advisory-first:
- no LLM calls,
- no mutation of caller-owned inputs,
- no direct routing side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_MAX_REASON_CHARS = 140
_MAX_EXCERPT_CHARS = 160

_ALLOWED_GATEWAY_MODES = {
    "pass_through",
    "shape_response",
    "repair_before_send",
    "hold_or_escalate",
}
_ALLOWED_POSTURES = {
    "aligned",
    "fragile",
    "repair",
    "escalate",
    "insufficient_context",
}
_ALLOWED_TRANSFORMATIONS = {
    "none",
    "tonal_wrap",
    "repair_wrap",
    "hold_notice",
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def _flatten(text: Any) -> str:
    return " ".join(str(text or "").split()).strip()


def _excerpt(text: Any, limit: int = _MAX_EXCERPT_CHARS) -> str:
    flat = _flatten(text)
    return flat[:limit]


def _prefers_slow_warm(pre_prompt: Any) -> bool:
    prompt = _norm(pre_prompt)
    return "slow" in prompt or "warm" in prompt or "soft" in prompt


def _shape_intro(*, resolution_direction: str, slow_warm: bool) -> str:
    if resolution_direction == "deescalate_then_translate":
        return (
            "Let's slow this down and translate the moving parts into one shared frame."
            if slow_warm
            else "Let's translate the moving parts into one shared frame before acting."
        )
    if resolution_direction == "stabilize_then_reframe":
        return "Let's steady the situation first, then reframe the next move."
    if resolution_direction == "translate_then_decide":
        return "Let's translate the key assumptions before deciding."
    if resolution_direction == "observe_and_stage":
        return "Let's take this one careful step at a time."
    return (
        "Let's keep this grounded, warm, and clear."
        if slow_warm
        else "Let's keep this grounded and clear."
    )


def _repair_intro(*, resolution_direction: str) -> str:
    if resolution_direction == "repair_then_resume":
        return "Before acting on this, let's lower tension and repair the scene first."
    return "Before acting on this, let's reduce tension and make the next step safer."


def _hold_notice(*, escalation_reason: str) -> str:
    reason = _flatten(escalation_reason) or "current signals point to escalation"
    return (
        "LS is holding the raw agent output for review because {reason}. "
        "Inspect raw_agent_output before acting."
    ).format(reason=reason)


def _quality_posture(
    *,
    risk_state: str,
    coordination_label: str,
) -> str:
    if risk_state == "escalate":
        return "escalate"
    if risk_state == "repair":
        return "repair"
    if coordination_label in {"fragile", "blocked"}:
        return "fragile"
    if coordination_label == "insufficient_context" and not risk_state:
        return "insufficient_context"
    return "aligned"


def _mode(
    *,
    raw_output: str,
    risk_state: str,
    requires_human_review: bool,
    coordination_label: str,
    harmonic_center: str,
    harmonic_interval_label: str,
) -> str:
    if not _flatten(raw_output):
        return "pass_through"
    if requires_human_review or risk_state == "escalate":
        return "hold_or_escalate"
    if risk_state == "repair" or harmonic_center == "repair":
        return "repair_before_send"
    if coordination_label in {"fragile", "blocked"} or harmonic_interval_label in {"fourth", "seventh", "tritone"}:
        return "shape_response"
    return "pass_through"


def _reason(
    *,
    gateway_mode: str,
    posture: str,
    risk_state: str,
    coordination_label: str,
    harmonic_center: str,
    harmonic_interval_label: str,
    resolution_direction: str,
) -> str:
    if gateway_mode == "hold_or_escalate":
        reason = "gateway held the raw output because escalation signals outweigh safe delivery"
    elif gateway_mode == "repair_before_send":
        reason = "gateway wrapped the output in repair mode because tension should be reduced before action"
    elif gateway_mode == "shape_response":
        reason = "gateway shaped the output because the scene is fragile and delivery should be softened"
    else:
        reason = "gateway passed the output through because current signals support direct delivery"

    details = [
        f"posture={posture}",
        f"risk={risk_state or 'unknown'}",
        f"coordination={coordination_label or 'unknown'}",
        f"harmonic={harmonic_center or 'unknown'}/{harmonic_interval_label or 'unknown'}",
        f"resolution={resolution_direction or 'unknown'}",
    ]
    return _flatten(f"{reason}; {'; '.join(details)}")[:_MAX_REASON_CHARS]


def _delivered_output(
    *,
    gateway_mode: str,
    raw_output: str,
    pre_prompt: str,
    resolution_direction: str,
    gateway_reason: str,
) -> tuple[str, str]:
    raw = str(raw_output or "")
    if gateway_mode == "pass_through":
        return raw, "none"

    slow_warm = _prefers_slow_warm(pre_prompt)
    if gateway_mode == "shape_response":
        intro = _shape_intro(resolution_direction=resolution_direction, slow_warm=slow_warm)
        return f"{intro}\n\n{raw}".strip(), "tonal_wrap"
    if gateway_mode == "repair_before_send":
        intro = _repair_intro(resolution_direction=resolution_direction)
        delivered = f"{intro}\n\nSafest next-step version:\n{raw}".strip()
        return delivered, "repair_wrap"

    delivered = _hold_notice(escalation_reason=gateway_reason)
    return delivered, "hold_notice"


@dataclass
class PersonalAgentGatewayDecision:
    gateway_mode: str = "pass_through"
    quality_posture: str = "insufficient_context"
    transformation_label: str = "none"
    delivered_output: str = ""
    delivered_output_changed: bool = False
    shaping_applied: bool = False
    repair_required: bool = False
    escalation_required: bool = False
    hold_required: bool = False
    coordination_advisory_label: str = "insufficient_context"
    harmonic_center: str = "insufficient_context"
    harmonic_interval_label: str = "unknown"
    resolution_direction: str = "unknown"
    raw_output_excerpt: str = ""
    delivered_output_excerpt: str = ""
    gateway_reason: str = "gateway has insufficient context"

    def to_dict(self) -> dict[str, Any]:
        mode = self.gateway_mode if self.gateway_mode in _ALLOWED_GATEWAY_MODES else "pass_through"
        posture = self.quality_posture if self.quality_posture in _ALLOWED_POSTURES else "insufficient_context"
        transform = self.transformation_label if self.transformation_label in _ALLOWED_TRANSFORMATIONS else "none"
        reason = _flatten(self.gateway_reason) or "gateway has insufficient context"
        return {
            "gateway_mode": mode,
            "quality_posture": posture,
            "transformation_label": transform,
            "delivered_output": str(self.delivered_output or ""),
            "delivered_output_changed": bool(self.delivered_output_changed),
            "shaping_applied": bool(self.shaping_applied),
            "repair_required": bool(self.repair_required),
            "escalation_required": bool(self.escalation_required),
            "hold_required": bool(self.hold_required),
            "coordination_advisory_label": str(self.coordination_advisory_label or "insufficient_context"),
            "harmonic_center": str(self.harmonic_center or "insufficient_context"),
            "harmonic_interval_label": str(self.harmonic_interval_label or "unknown"),
            "resolution_direction": str(self.resolution_direction or "unknown"),
            "raw_output_excerpt": _excerpt(self.raw_output_excerpt),
            "delivered_output_excerpt": _excerpt(self.delivered_output_excerpt),
            "gateway_reason": reason[:_MAX_REASON_CHARS],
        }


@dataclass
class PersonalAgentGatewayMetrics:
    calls_total: int = 0
    decisions_total: int = 0
    pass_through_total: int = 0
    shape_response_total: int = 0
    repair_before_send_total: int = 0
    hold_or_escalate_total: int = 0
    delivered_changed_total: int = 0
    escalation_required_total: int = 0
    repair_required_total: int = 0
    _raw_excerpt_len_sum: float = 0.0
    _delivered_excerpt_len_sum: float = 0.0

    @property
    def avg_raw_excerpt_length(self) -> float:
        if self.decisions_total <= 0:
            return 0.0
        return round(self._raw_excerpt_len_sum / self.decisions_total, 2)

    @property
    def avg_delivered_excerpt_length(self) -> float:
        if self.decisions_total <= 0:
            return 0.0
        return round(self._delivered_excerpt_len_sum / self.decisions_total, 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls_total": self.calls_total,
            "decisions_total": self.decisions_total,
            "pass_through_total": self.pass_through_total,
            "shape_response_total": self.shape_response_total,
            "repair_before_send_total": self.repair_before_send_total,
            "hold_or_escalate_total": self.hold_or_escalate_total,
            "delivered_changed_total": self.delivered_changed_total,
            "escalation_required_total": self.escalation_required_total,
            "repair_required_total": self.repair_required_total,
            "avg_raw_excerpt_length": self.avg_raw_excerpt_length,
            "avg_delivered_excerpt_length": self.avg_delivered_excerpt_length,
        }


def build_personal_agent_gateway_decision(
    *,
    raw_output: str,
    copilot_pre_prompt: str | None = None,
    coordination_advisory_summary: dict[str, Any] | None = None,
    harmonic_state_summary: dict[str, Any] | None = None,
    relational_policy_decision: dict[str, Any] | None = None,
) -> PersonalAgentGatewayDecision:
    summary = coordination_advisory_summary if isinstance(coordination_advisory_summary, dict) else {}
    harmonic = harmonic_state_summary if isinstance(harmonic_state_summary, dict) else {}
    relational = relational_policy_decision if isinstance(relational_policy_decision, dict) else {}

    risk_state = _norm(relational.get("risk_state"))
    coordination_label = _norm(summary.get("coordination_advisory_label"))
    harmonic_center = _norm(harmonic.get("harmonic_center"))
    harmonic_interval = _norm(harmonic.get("harmonic_interval_label"))
    resolution_direction = str(harmonic.get("resolution_direction") or "unknown")
    requires_human_review = bool(relational.get("requires_human_review"))

    posture = _quality_posture(
        risk_state=risk_state,
        coordination_label=coordination_label,
    )
    gateway_mode = _mode(
        raw_output=raw_output,
        risk_state=risk_state,
        requires_human_review=requires_human_review,
        coordination_label=coordination_label,
        harmonic_center=harmonic_center,
        harmonic_interval_label=harmonic_interval,
    )
    gateway_reason = _reason(
        gateway_mode=gateway_mode,
        posture=posture,
        risk_state=risk_state,
        coordination_label=coordination_label,
        harmonic_center=harmonic_center,
        harmonic_interval_label=harmonic_interval,
        resolution_direction=resolution_direction,
    )
    delivered_output, transformation_label = _delivered_output(
        gateway_mode=gateway_mode,
        raw_output=raw_output,
        pre_prompt=str(copilot_pre_prompt or ""),
        resolution_direction=resolution_direction,
        gateway_reason=gateway_reason,
    )

    delivered_changed = _flatten(delivered_output) != _flatten(raw_output)
    return PersonalAgentGatewayDecision(
        gateway_mode=gateway_mode,
        quality_posture=posture,
        transformation_label=transformation_label,
        delivered_output=delivered_output,
        delivered_output_changed=delivered_changed,
        shaping_applied=gateway_mode == "shape_response",
        repair_required=gateway_mode == "repair_before_send",
        escalation_required=gateway_mode == "hold_or_escalate",
        hold_required=gateway_mode == "hold_or_escalate",
        coordination_advisory_label=coordination_label or "insufficient_context",
        harmonic_center=harmonic_center or "insufficient_context",
        harmonic_interval_label=harmonic_interval or "unknown",
        resolution_direction=resolution_direction or "unknown",
        raw_output_excerpt=_excerpt(raw_output),
        delivered_output_excerpt=_excerpt(delivered_output),
        gateway_reason=gateway_reason,
    )
