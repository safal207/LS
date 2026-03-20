"""IntentLayer — structured intent extraction from interpreted text.

Sits between SmartEar (Interpretation) and AgentLoop (Decision).

Instead of passing raw text to the LLM, the system first answers:
    "What does the user *want*?"

This produces a typed, structured intent that allows:
* Precise LLM routing (definition vs. howto vs. debug)
* Reduced hallucination (entity is pinned)
* Better UX (system can acknowledge intent before responding)

Architecture::

    perception output
        ↓
    IntentLayer.extract(text)
        ↓
    IntentResult(type, entity, params, confidence)
        ↓
    Decision / AgentLoop

Intent types
------------
definition  — "что такое X", "what is X", "explain X"
howto       — "как сделать X", "how to X", "покажи как"
comparison  — "сравни X и Y", "X vs Y", "что лучше"
command     — "запусти X", "открой X", "run X"
debug       — "почему X не работает", "ошибка X", "fix X"
opinion     — "что лучше для Y", "стоит ли X"
unknown     — fallback when no pattern matches

Usage::

    layer = IntentLayer()
    result = layer.extract("что такое React")
    # IntentResult(type='definition', entity='React', confidence=0.92)

    item["_intent"] = result.to_dict()
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IntentType constants
# ---------------------------------------------------------------------------

class IntentType:
    DEFINITION  = "definition"
    HOWTO       = "howto"
    COMPARISON  = "comparison"
    COMMAND     = "command"
    DEBUG       = "debug"
    OPINION     = "opinion"
    UNKNOWN     = "unknown"


# ---------------------------------------------------------------------------
# IntentResult
# ---------------------------------------------------------------------------

@dataclass
class IntentResult:
    """Structured intent extracted from a single utterance.

    Attributes:
        type:       One of IntentType constants.
        entity:     Primary subject of the utterance (e.g. "React", "Docker").
        params:     Additional parameters (domain, language, target, etc.)
        confidence: Extraction confidence 0.0–1.0.
        raw_text:   Original text before intent extraction.
    """
    type:       str
    entity:     str
    params:     Dict[str, str] = field(default_factory=dict)
    confidence: float = 0.0
    raw_text:   str = ""

    def to_dict(self) -> dict:
        return {
            "type":       self.type,
            "entity":     self.entity,
            "params":     self.params,
            "confidence": round(self.confidence, 4),
            "raw_text":   self.raw_text,
        }

    def __repr__(self) -> str:
        return (
            f"IntentResult(type={self.type!r}, entity={self.entity!r}, "
            f"conf={self.confidence:.2f})"
        )


# ---------------------------------------------------------------------------
# Pattern bank
# ---------------------------------------------------------------------------

# Each entry: (pattern, intent_type, confidence_base)
# Patterns are tried in order; first match wins.
# Entity is extracted via first capture group when present.
_PATTERNS_RU: List[Tuple[re.Pattern, str, float]] = [
    # Debug / errors
    (re.compile(r"почему\s+(.+?)\s+не\s+работает", re.I),   IntentType.DEBUG,      0.92),
    (re.compile(r"(ошибка|error|exception|traceback)\s+(.+)", re.I), IntentType.DEBUG, 0.90),
    (re.compile(r"как\s+исправить\s+(.+)", re.I),            IntentType.DEBUG,      0.88),
    (re.compile(r"почему\s+(.+?)\s+падает", re.I),           IntentType.DEBUG,      0.87),
    (re.compile(r"fix\s+(.+)", re.I),                        IntentType.DEBUG,      0.85),

    # Comparison
    (re.compile(r"сравни\s+(.+?)\s+и\s+(.+)", re.I),        IntentType.COMPARISON, 0.93),
    (re.compile(r"(.+?)\s+vs\.?\s+(.+)", re.I),              IntentType.COMPARISON, 0.90),
    (re.compile(r"(.+?)\s+или\s+(.+?)\?", re.I),             IntentType.COMPARISON, 0.85),
    (re.compile(r"разница\s+между\s+(.+?)\s+и\s+(.+)", re.I), IntentType.COMPARISON, 0.92),
    (re.compile(r"difference\s+between\s+(.+?)\s+and\s+(.+)", re.I), IntentType.COMPARISON, 0.92),

    # HowTo
    (re.compile(r"как\s+(?:правильно\s+)?(.+)", re.I),       IntentType.HOWTO,      0.88),
    (re.compile(r"how\s+to\s+(.+)", re.I),                   IntentType.HOWTO,      0.90),
    (re.compile(r"покажи\s+(?:мне\s+)?как\s+(.+)", re.I),    IntentType.HOWTO,      0.91),
    (re.compile(r"объясни\s+как\s+(.+)", re.I),              IntentType.HOWTO,      0.89),

    # Command
    (re.compile(r"запусти\s+(.+)", re.I),                    IntentType.COMMAND,    0.93),
    (re.compile(r"открой\s+(.+)", re.I),                     IntentType.COMMAND,    0.90),
    (re.compile(r"выполни\s+(.+)", re.I),                    IntentType.COMMAND,    0.90),
    (re.compile(r"(?:run|start|open|execute)\s+(.+)", re.I), IntentType.COMMAND,    0.91),

    # Opinion
    (re.compile(r"(?:что|какой)\s+лучше\s+(.+)", re.I),      IntentType.OPINION,    0.85),
    (re.compile(r"стоит\s+ли\s+(?:использовать\s+)?(.+)", re.I), IntentType.OPINION, 0.83),
    (re.compile(r"what(?:'s|\s+is)\s+better\s+(.+)", re.I),  IntentType.OPINION,    0.85),

    # Definition (last: broadest match)
    (re.compile(r"что\s+такое\s+(.+)", re.I),                IntentType.DEFINITION, 0.95),
    (re.compile(r"что\s+(?:это|есть)\s+(.+)", re.I),         IntentType.DEFINITION, 0.90),
    (re.compile(r"what\s+is\s+(.+)", re.I),                  IntentType.DEFINITION, 0.95),
    (re.compile(r"explain\s+(.+)", re.I),                    IntentType.DEFINITION, 0.88),
    (re.compile(r"расскажи\s+(?:про|о)\s+(.+)", re.I),       IntentType.DEFINITION, 0.87),
]

# Cleanup noise in extracted entity
_ENTITY_NOISE = re.compile(
    r"\b(такое|это|есть|please|мне|please|подробно|кратко|быстро|"
    r"exactly|please|quickly|briefly|мне|нам)\b",
    re.I,
)

# IT domain keyword → domain tag mapping
_DOMAIN_TAGS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\b(react|vue|angular|svelte|next\.?js|nuxt)\b", re.I), "web_dev"),
    (re.compile(r"\b(docker|kubernetes|k8s|helm|compose|pod)\b", re.I),  "devops"),
    (re.compile(r"\b(python|typescript|javascript|rust|golang|java)\b", re.I), "lang"),
    (re.compile(r"\b(sql|postgres|mongodb|redis|mysql)\b", re.I),        "db"),
    (re.compile(r"\b(git|github|gitlab|ci/cd|pipeline)\b", re.I),        "vcs"),
    (re.compile(r"\b(llm|gpt|claude|llama|transformer|embedding)\b", re.I), "ai"),
    (re.compile(r"\b(api|rest|grpc|graphql|websocket)\b", re.I),         "api"),
]


# ---------------------------------------------------------------------------
# IntentLayer
# ---------------------------------------------------------------------------

class IntentLayer:
    """Extracts structured intent from a resolved utterance.

    Rule-based with confidence scoring.  Designed for zero-dependency
    operation; ML-based extraction can be added later via ``ml_model``.

    Args:
        min_confidence: Intents below this threshold are typed as UNKNOWN.
        ml_model:       Optional callable ``(text) → IntentResult``
                        that overrides rule-based logic when provided.
    """

    def __init__(
        self,
        min_confidence: float = 0.0,
        ml_model=None,
    ) -> None:
        self.min_confidence = min_confidence
        self._ml_model = ml_model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(self, text: str) -> IntentResult:
        """Extract intent from *text*.

        Returns an :class:`IntentResult`.  Never raises.
        """
        if not text or not text.strip():
            return IntentResult(
                type=IntentType.UNKNOWN, entity="", confidence=0.0, raw_text=text
            )

        text = text.strip()

        # ML model takes priority when present
        if self._ml_model is not None:
            try:
                result = self._ml_model(text)
                if isinstance(result, IntentResult):
                    result.raw_text = text
                    return result
            except Exception as exc:
                logger.debug("IntentLayer: ML model failed, falling back: %s", exc)

        return self._rule_based(text)

    def process_item(self, item: dict) -> dict:
        """Enrich a SmartEar item dict in-place with ``_intent`` field.

        Reads ``item["text"]`` (final resolved text), runs extraction,
        and sets ``item["_intent"]`` to the serialized IntentResult.

        Returns the same item (mutated).
        """
        text = item.get("text", "")
        result = self.extract(text)
        item["_intent"] = result.to_dict()
        logger.debug("IntentLayer: %r → %s", text[:60], result)
        return item

    # ------------------------------------------------------------------
    # Internal rule-based engine
    # ------------------------------------------------------------------

    def _rule_based(self, text: str) -> IntentResult:
        best_type = IntentType.UNKNOWN
        best_entity = ""
        best_confidence = 0.0
        best_params: Dict[str, str] = {}

        for pattern, intent_type, conf_base in _PATTERNS_RU:
            m = pattern.search(text)
            if m is None:
                continue

            # Entity: first non-empty group
            groups = [g for g in m.groups() if g]
            entity = self._clean_entity(groups[0]) if groups else ""

            # For comparison, second group becomes 'target'
            params: Dict[str, str] = {}
            if intent_type == IntentType.COMPARISON and len(groups) >= 2:
                params["target"] = self._clean_entity(groups[1])

            # Domain detection
            domain = self._detect_domain(text)
            if domain:
                params["domain"] = domain

            # Confidence: penalise short entity
            confidence = conf_base
            if not entity or len(entity) < 2:
                confidence *= 0.7

            if confidence > best_confidence:
                best_type = intent_type
                best_entity = entity
                best_confidence = confidence
                best_params = params

        if best_confidence < self.min_confidence:
            best_type = IntentType.UNKNOWN
            best_confidence = 0.0

        return IntentResult(
            type=best_type,
            entity=best_entity,
            params=best_params,
            confidence=round(best_confidence, 4),
            raw_text=text,
        )

    def _clean_entity(self, raw: str) -> str:
        """Remove noise words and normalize whitespace."""
        cleaned = _ENTITY_NOISE.sub("", raw).strip()
        # Collapse multiple spaces
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        # Strip trailing punctuation
        cleaned = cleaned.rstrip("?.!,;:")
        return cleaned.strip()

    def _detect_domain(self, text: str) -> Optional[str]:
        for pattern, domain in _DOMAIN_TAGS:
            if pattern.search(text):
                return domain
        return None
