from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PolicyAssessment:
    score: int
    floor_decision: str
    signals: list[str] = field(default_factory=list)


DESTRUCTIVE_TERMS = {
    "delete", "drop", "destroy", "erase", "terminate", "revoke", "wipe",
    "удалить", "стереть", "уничтожить", "отозвать",
}
PRODUCTION_TERMS = {"prod", "production", "live", "боевой", "прод"}
SECRET_TERMS = {"secret", "token", "password", "credential", "api key", "ключ", "пароль"}
MONEY_TERMS = {"payment", "refund", "transfer", "invoice", "purchase", "оплат", "перевод", "возврат"}
EXTERNAL_TERMS = {"email", "message", "publish", "post", "deploy", "send", "письмо", "сообщение", "публика", "деплой"}


def _contains(text: str, terms: set[str]) -> bool:
    lowered = text.casefold()
    return any(term in lowered for term in terms)


def assess_policy(payload: dict[str, Any]) -> PolicyAssessment:
    """Calculate a deterministic minimum safety decision.

    The model can make the result stricter, but never weaker than this floor.
    """
    text = " ".join(
        str(payload.get(key, ""))
        for key in ("action", "resource", "context", "requested_effect")
    )
    score = 0
    signals: list[str] = []

    if _contains(text, DESTRUCTIVE_TERMS):
        score += 55
        signals.append("destructive_operation")
    if _contains(text, PRODUCTION_TERMS):
        score += 25
        signals.append("production_target")
    if _contains(text, SECRET_TERMS):
        score += 40
        signals.append("credential_or_secret_access")
    if _contains(text, MONEY_TERMS):
        score += 40
        signals.append("financial_side_effect")
    if _contains(text, EXTERNAL_TERMS):
        score += 25
        signals.append("external_side_effect")

    metadata = payload.get("metadata") or {}
    if metadata.get("reversible") is False:
        score += 25
        signals.append("irreversible")
    if metadata.get("has_test_evidence") is False:
        score += 15
        signals.append("missing_test_evidence")
    if metadata.get("user_consent") is False:
        score += 30
        signals.append("missing_user_consent")

    score = min(score, 100)
    if score >= 70:
        floor = "BLOCK"
    elif score >= 25:
        floor = "HUMAN_APPROVAL"
    else:
        floor = "ALLOW"
    return PolicyAssessment(score=score, floor_decision=floor, signals=signals)


def stricter_decision(policy_floor: str, model_decision: str) -> str:
    order = {"ALLOW": 0, "HUMAN_APPROVAL": 1, "BLOCK": 2}
    normalized = model_decision if model_decision in order else "HUMAN_APPROVAL"
    return max((policy_floor, normalized), key=order.__getitem__)
