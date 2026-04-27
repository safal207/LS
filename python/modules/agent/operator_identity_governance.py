# -*- coding: utf-8 -*-
"""Operator identity governance signals inspired by LRI.

This module does not import the LRI reference implementation. It keeps a small,
deterministic LS-native safety layer that protects the operator from being
silently frozen into a profile or replaced by agent authorship.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _lower_join(*values: Any) -> str:
    return " ".join(str(value or "").lower() for value in values)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _metadata_text(metadata: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key, value in sorted(dict(metadata or {}).items()):
        if isinstance(value, (str, int, float, bool)):
            chunks.append(f"{key}:{value}")
        elif isinstance(value, (list, tuple)):
            chunks.append(f"{key}:{','.join(str(item) for item in value)}")
    return " ".join(chunks).lower()


@dataclass(frozen=True)
class OperatorIdentityGovernanceSignal:
    identity_governance_mode: str
    authority_boundary: str
    continuity_required: bool
    identity_drift_warning: bool
    identity_freezing_risk: bool
    authorship_boundary_risk: bool
    memory_consent_warning: bool
    risk_score: float
    reasons: list[str] = field(default_factory=list)
    source: str = "ls.operator_identity_governance.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OperatorIdentityGovernance:
    """Evaluate whether an agent output may pressure operator identity."""

    FREEZING_TERMS = (
        "you are",
        "you always",
        "you never",
        "your true self",
        "your real identity",
        "fixed profile",
        "profile says",
        "destiny",
    )
    AUTHORSHIP_TERMS = (
        "i decided for you",
        "i will decide",
        "i chose for you",
        "you must",
        "do this now",
        "no need to ask",
        "approve automatically",
    )
    MEMORY_TERMS = (
        "remember forever",
        "permanent memory",
        "store everything",
        "always remember",
        "track you",
        "profile permanently",
    )
    DRIFT_TERMS = (
        "ignore your earlier",
        "forget your boundary",
        "override your preference",
        "change your goal",
        "optimize you",
        "make you comply",
    )

    def evaluate(
        self,
        *,
        prompt: str,
        raw_output: str,
        final_output: str = "",
        metadata: dict[str, Any] | None = None,
        participants: list[Any] | None = None,
    ) -> OperatorIdentityGovernanceSignal:
        meta = dict(metadata or {})
        participants_list = _as_list(participants)
        text = _lower_join(prompt, raw_output, final_output, _metadata_text(meta))

        reasons: list[str] = []
        identity_freezing = self._has_any(text, self.FREEZING_TERMS)
        authorship_risk = self._has_any(text, self.AUTHORSHIP_TERMS)
        memory_warning = self._has_any(text, self.MEMORY_TERMS)
        drift_warning = self._has_any(text, self.DRIFT_TERMS)
        continuity_required = bool(
            meta.get("requires_continuity")
            or meta.get("operator_profile_update")
            or meta.get("memory_write")
            or memory_warning
            or drift_warning
        )

        if identity_freezing:
            reasons.append("identity_freezing_language_detected")
        if authorship_risk:
            reasons.append("agent_authorship_boundary_pressure")
        if memory_warning:
            reasons.append("memory_or_profile_persistence_needs_consent")
        if drift_warning:
            reasons.append("operator_preference_or_boundary_drift_detected")
        if continuity_required:
            reasons.append("continuity_check_required_before_identity_relevant_write")
        if self._participants_include_operator_and_agent(participants_list):
            reasons.append("human_agent_identity_boundary_present")

        risk_score = self._score(
            identity_freezing=identity_freezing,
            authorship_risk=authorship_risk,
            memory_warning=memory_warning,
            drift_warning=drift_warning,
            continuity_required=continuity_required,
        )
        mode = self._mode(risk_score)
        boundary = self._authority_boundary(
            authorship_risk=authorship_risk,
            memory_warning=memory_warning,
            drift_warning=drift_warning,
            identity_freezing=identity_freezing,
        )
        return OperatorIdentityGovernanceSignal(
            identity_governance_mode=mode,
            authority_boundary=boundary,
            continuity_required=continuity_required,
            identity_drift_warning=drift_warning,
            identity_freezing_risk=identity_freezing,
            authorship_boundary_risk=authorship_risk,
            memory_consent_warning=memory_warning,
            risk_score=risk_score,
            reasons=reasons,
        )

    @staticmethod
    def _has_any(text: str, terms: tuple[str, ...]) -> bool:
        return any(term in text for term in terms)

    @staticmethod
    def _participants_include_operator_and_agent(participants: list[Any]) -> bool:
        has_operator = False
        has_agent = False
        for participant in participants:
            if isinstance(participant, dict):
                blob = _lower_join(
                    participant.get("participant_id"),
                    participant.get("participant_type"),
                    participant.get("role"),
                )
            else:
                blob = str(participant or "").lower()
            has_operator = has_operator or any(term in blob for term in ("operator", "human", "user"))
            has_agent = has_agent or any(term in blob for term in ("agent", "model", "codex"))
        return has_operator and has_agent

    @staticmethod
    def _score(
        *,
        identity_freezing: bool,
        authorship_risk: bool,
        memory_warning: bool,
        drift_warning: bool,
        continuity_required: bool,
    ) -> float:
        score = 0.0
        if identity_freezing:
            score += 0.24
        if authorship_risk:
            score += 0.28
        if memory_warning:
            score += 0.24
        if drift_warning:
            score += 0.18
        if continuity_required:
            score += 0.06
        return round(min(score, 1.0), 3)

    @staticmethod
    def _mode(risk_score: float) -> str:
        if risk_score >= 0.62:
            return "hold_for_identity_review"
        if risk_score >= 0.32:
            return "identity_boundary_warning"
        return "observe"

    @staticmethod
    def _authority_boundary(
        *,
        authorship_risk: bool,
        memory_warning: bool,
        drift_warning: bool,
        identity_freezing: bool,
    ) -> str:
        if authorship_risk:
            return "agent_must_not_replace_operator_authority"
        if memory_warning:
            return "memory_write_requires_explicit_consent"
        if drift_warning:
            return "operator_preference_change_requires_continuity_check"
        if identity_freezing:
            return "profile_must_remain_revisable"
        return "advisory_only"


operator_identity_governance = OperatorIdentityGovernance()
