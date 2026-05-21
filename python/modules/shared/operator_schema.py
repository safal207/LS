from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Optional


@dataclass
class OperatorUtterance:
    """Speech-to-answer payload shared across STT and SmartEar."""

    type: str = "question"
    text: str = ""
    confidence: float = 0.0
    source: str = "unknown"
    words: list[dict[str, Any]] = field(default_factory=list)
    clean_text: Optional[str] = None
    intent: Optional[Any] = None
    why: Optional[Any] = None
    why_strategy: Optional[dict[str, Any]] = None
    operator_profile: Optional[dict[str, Any]] = None
    anchor_context: list[Any] = field(default_factory=list)
    timestamp: Optional[float] = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_item(self) -> dict[str, Any]:
        item: dict[str, Any] = {
            "type": self.type,
            "text": self.text,
            "confidence": self.confidence,
            "source": self.source,
            "words": list(self.words),
            "_words": list(self.words),
            "_asr_confidence": self.confidence,
            "clean_text": self.clean_text or self.text,
            "_clean_text": self.clean_text or self.text,
            "anchor_context": list(self.anchor_context),
        }
        if self.intent is not None:
            item["intent"] = self.intent
        if self.why is not None:
            item["why"] = self.why
        if self.why_strategy is not None:
            item["_why_strategy"] = dict(self.why_strategy)
        if self.operator_profile is not None:
            profile = dict(self.operator_profile)
            item["operator_profile"] = dict(profile)
            item["_operator_profile"] = dict(profile)
        if self.timestamp is not None:
            item["timestamp"] = self.timestamp
        if self.raw:
            item.update(self.raw)
        return item

    @classmethod
    def from_item(cls, item: Mapping[str, Any] | MutableMapping[str, Any]) -> "OperatorUtterance":
        data = dict(item)
        words = data.get("words") or data.get("_words") or []
        if not isinstance(words, list):
            words = []
        anchor_context = data.get("anchor_context") or data.get("_anchor_context") or []
        if not isinstance(anchor_context, list):
            anchor_context = []
        profile = data.get("operator_profile") or data.get("_operator_profile")
        return cls(
            type=str(data.get("type", "question")),
            text=str(data.get("text", "")),
            confidence=float(data.get("confidence", data.get("_asr_confidence", 0.0)) or 0.0),
            source=str(data.get("source", "unknown")),
            words=list(words),
            clean_text=data.get("clean_text") or data.get("_clean_text") or data.get("text", ""),
            intent=data.get("intent") or data.get("_intent"),
            why=data.get("why") or data.get("_why"),
            why_strategy=data.get("why_strategy") or data.get("_why_strategy"),
            operator_profile=profile,
            anchor_context=list(anchor_context),
            timestamp=data.get("timestamp"),
            raw={
                k: v
                for k, v in data.items()
                if k
                not in {
                    "type",
                    "text",
                    "confidence",
                    "source",
                    "words",
                    "_words",
                    "_asr_confidence",
                    "clean_text",
                    "_clean_text",
                    "intent",
                    "_intent",
                    "why",
                    "_why",
                    "why_strategy",
                    "_why_strategy",
                    "operator_profile",
                    "_operator_profile",
                    "anchor_context",
                    "_anchor_context",
                    "timestamp",
                }
            },
        )


def ensure_operator_item(item: Any, *, default_source: str = "unknown") -> dict[str, Any]:
    """Normalize any supported payload into the runtime dict contract."""
    if isinstance(item, OperatorUtterance):
        payload = item.to_item()
    elif isinstance(item, Mapping):
        payload = OperatorUtterance.from_item(item).to_item()
    else:
        payload = {
            "type": "question",
            "text": str(item) if item is not None else "",
            "confidence": 0.0,
            "source": default_source,
            "words": [],
            "_words": [],
            "_asr_confidence": 0.0,
            "clean_text": str(item) if item is not None else "",
            "_clean_text": str(item) if item is not None else "",
            "anchor_context": [],
        }
    payload.setdefault("source", default_source)
    payload.setdefault("clean_text", payload.get("text", ""))
    payload.setdefault("_clean_text", payload.get("clean_text", payload.get("text", "")))
    payload.setdefault("words", payload.get("_words", []))
    payload.setdefault("_words", payload.get("words", []))
    payload.setdefault("_asr_confidence", payload.get("confidence", 0.0))
    profile = payload.get("operator_profile") or payload.get("_operator_profile")
    if isinstance(profile, Mapping):
        profile_dict = dict(profile)
        payload.setdefault("operator_profile", dict(profile_dict))
        payload.setdefault("_operator_profile", dict(profile_dict))
    return payload


__all__ = ["OperatorUtterance", "ensure_operator_item"]
