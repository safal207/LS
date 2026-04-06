from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence


NODE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "crisis_node": ("хочу умереть", "хочу исчезнуть", "умереть", "suicide", "kill myself", "self-harm"),
    "interest_node": ("интерес", "любопыт", "увлека", "зажи", "curious", "interest"),
    "pain_node": ("боль", "тяжело", "страда", "frustrat", "hurt", "болит"),
    "goal_node": ("хочу", "цель", "постро", "достич", "goal", "build", "launch", "стартап"),
    "risk_node": ("риск", "бою", "потер", "опас", "risk", "fear", "lose"),
    "conflict_node": ("конфликт", "спор", "противореч", "tension", "conflict"),
    "unfinished_node": ("незаверш", "не закончил", "вися", "pending", "unfinished", "loop"),
    "identity_node": ("кто я", "я такой", "моя роль", "identity", "creator", "создател"),
    "care_node": ("семья", "ребен", "ребён", "дорого", "честь", "care", "important to me"),
    "novelty_node": ("новое", "впервые", "fresh", "novel", "новиз"),
}

STYLE_MAP: dict[str, str] = {
    "crisis_node": "safety_first_grounding",
    "goal_node": "supportive_precision",
    "identity_node": "reflective_validation",
    "pain_node": "gentle_grounding",
    "risk_node": "risk_alignment",
    "conflict_node": "bridge_building",
    "unfinished_node": "closure_scaffolding",
    "care_node": "value_respecting",
    "interest_node": "curiosity_amplification",
    "novelty_node": "guided_exploration",
}

DEFAULT_AVOID_STYLES: tuple[str, ...] = ("pressure", "over-abstraction")
SENSITIVE_MARKERS: tuple[str, ...] = (
    "травм",
    "panic",
    "паник",
    "abuse",
    "self-harm",
    "суицид",
    "умереть",
    "исчезнуть",
    "kill myself",
    "хочу умереть",
)


@dataclass(frozen=True)
class ResonantEntryInput:
    user_utterance: str
    recent_memory: Sequence[str] = ()
    task_intent: str = ""
    emotional_semantic_markers: Mapping[str, float] = field(default_factory=dict)
    current_scene_context: str = ""


@dataclass(frozen=True)
class ResonantEntryResult:
    entry_node_type: str
    entry_node_label: str
    resonance_score: float
    openness_estimate: str
    emotional_charge: float
    task_relevance: float
    identity_proximity: float
    recommended_entry_style: str
    avoid_styles: list[str]
    next_contact_move: str
    confidence: float
    supporting_signals: list[str]
    contra_signals: list[str]
    deepening_risk: float
    safety_blocked: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_node_type": self.entry_node_type,
            "entry_node_label": self.entry_node_label,
            "resonance_score": round(self.resonance_score, 3),
            "openness_estimate": self.openness_estimate,
            "emotional_charge": round(self.emotional_charge, 3),
            "task_relevance": round(self.task_relevance, 3),
            "identity_proximity": round(self.identity_proximity, 3),
            "recommended_entry_style": self.recommended_entry_style,
            "avoid_styles": self.avoid_styles,
            "next_contact_move": self.next_contact_move,
            "confidence": round(self.confidence, 3),
            "supporting_signals": self.supporting_signals,
            "contra_signals": self.contra_signals,
            "deepening_risk": round(self.deepening_risk, 3),
            "safety_blocked": self.safety_blocked,
        }


class ResonantEntryModule:
    """Detect the safest high-energy entry point for progressive context deepening."""

    def detect(self, payload: ResonantEntryInput) -> ResonantEntryResult:
        crisis_match = self._detect_crisis(payload.user_utterance)
        if crisis_match:
            return ResonantEntryResult(
                entry_node_type="crisis_node",
                entry_node_label=f"crisis_node:{crisis_match}",
                resonance_score=1.0,
                openness_estimate="low",
                emotional_charge=1.0,
                task_relevance=1.0,
                identity_proximity=0.8,
                recommended_entry_style=STYLE_MAP["crisis_node"],
                avoid_styles=list(DEFAULT_AVOID_STYLES),
                next_contact_move="Prioritize immediate safety, supportive grounding, and crisis escalation protocol.",
                confidence=1.0,
                supporting_signals=[crisis_match],
                contra_signals=[],
                deepening_risk=1.0,
                safety_blocked=True,
            )

        corpus = " ".join(
            [payload.user_utterance, payload.task_intent, payload.current_scene_context, *payload.recent_memory]
        ).lower()

        scores: dict[str, float] = {}
        support: dict[str, list[str]] = {}
        sensitive_context = self._has_sensitive_context(payload.user_utterance)
        for node_type, keywords in NODE_KEYWORDS.items():
            hits = [kw for kw in keywords if kw in corpus]
            repetition = sum(corpus.count(kw) for kw in hits)
            marker_bonus = payload.emotional_semantic_markers.get(node_type, 0.0)
            emotional_charge = self._estimate_emotional_charge(payload.user_utterance)
            base = min(1.0, (repetition * 0.18) + marker_bonus + (emotional_charge * 0.2))
            task_relevance = min(1.0, self._task_relevance(payload.task_intent, hits))
            openness = self._openness_signal(node_type, payload.user_utterance)
            safety = self._safety_multiplier(node_type, payload.user_utterance)
            score = (base * 0.45) + (task_relevance * 0.35) + (openness * 0.2)
            score *= safety
            if sensitive_context and node_type in {"goal_node", "identity_node"}:
                score *= 0.45
            scores[node_type] = max(0.0, min(1.0, score))
            support[node_type] = hits

        entry_node = max(scores, key=scores.get)
        resonance_score = scores[entry_node]
        emotional_charge = self._estimate_emotional_charge(payload.user_utterance)
        task_relevance = self._task_relevance(payload.task_intent, support[entry_node])
        identity_proximity = 1.0 if entry_node == "identity_node" else (0.65 if "я " in payload.user_utterance.lower() else 0.35)
        deepening_risk = 1.0 - self._safety_multiplier(entry_node, payload.user_utterance)

        openness_estimate = "high" if resonance_score >= 0.75 else "medium" if resonance_score >= 0.45 else "low"
        style = STYLE_MAP.get(entry_node, "supportive_precision")
        next_move = self._next_move(entry_node, payload.user_utterance)
        contra = self._contra_signals(entry_node, payload.user_utterance)
        confidence = min(1.0, resonance_score * (0.8 + (len(support[entry_node]) * 0.05)))

        return ResonantEntryResult(
            entry_node_type=entry_node,
            entry_node_label=self._label(entry_node, payload.user_utterance),
            resonance_score=resonance_score,
            openness_estimate=openness_estimate,
            emotional_charge=emotional_charge,
            task_relevance=task_relevance,
            identity_proximity=identity_proximity,
            recommended_entry_style=style,
            avoid_styles=list(DEFAULT_AVOID_STYLES),
            next_contact_move=next_move,
            confidence=confidence,
            supporting_signals=support[entry_node],
            contra_signals=contra,
            deepening_risk=deepening_risk,
            safety_blocked=False,
        )

    @staticmethod
    def _estimate_emotional_charge(text: str) -> float:
        lowered = text.lower()
        markers = ["!", "очень", "сильно", "устал", "не могу", "боюсь", "hate", "urgent"]
        raw = sum(lowered.count(marker) for marker in markers)
        return min(1.0, raw * 0.18)

    @staticmethod
    def _task_relevance(task_intent: str, hits: Sequence[str]) -> float:
        if not task_intent:
            return 0.25 if hits else 0.0
        lowered = task_intent.lower()
        if not hits:
            return 0.15
        overlap = sum(1 for hit in hits if hit in lowered)
        return min(1.0, 0.2 + (overlap * 0.35))

    @staticmethod
    def _openness_signal(node_type: str, utterance: str) -> float:
        lowered = utterance.lower()
        if "?" in utterance or "как" in lowered or "help" in lowered:
            return 0.8
        if node_type in {"risk_node", "pain_node"}:
            return 0.45
        return 0.6

    @staticmethod
    def _safety_multiplier(node_type: str, utterance: str) -> float:
        lowered = utterance.lower()
        if any(marker in lowered for marker in SENSITIVE_MARKERS) and node_type in {"pain_node", "risk_node"}:
            return 0.65
        if node_type == "risk_node" and "бою" in lowered:
            return 0.8
        return 1.0

    @staticmethod
    def _label(node_type: str, utterance: str) -> str:
        seed = utterance.strip().split(".")[0][:80]
        return f"{node_type}:{seed}" if seed else node_type

    @staticmethod
    def _next_move(node_type: str, utterance: str) -> str:
        if node_type == "goal_node":
            return "Connect the immediate blocker to the explicit long-term goal."
        if node_type == "identity_node":
            return "Reflect identity intent and ask for one concrete next action."
        if node_type in {"pain_node", "risk_node"}:
            return "Stabilize safety first, then narrow to one controllable step."
        if node_type == "unfinished_node":
            return "Name the open loop and propose a bounded closure step."
        if node_type == "conflict_node":
            return "Clarify both sides of tension before offering synthesis."
        if "?" in utterance:
            return "Answer the immediate question and confirm resonance before deepening."
        return "Mirror the active node and expand context progressively."

    @staticmethod
    def _contra_signals(node_type: str, utterance: str) -> list[str]:
        lowered = utterance.lower()
        signals: list[str] = []
        if node_type == "goal_node" and "не знаю" in lowered:
            signals.append("goal_ambiguity")
        if node_type in {"pain_node", "risk_node"} and "норм" in lowered:
            signals.append("possible_deflection")
        if len(lowered.split()) < 4:
            signals.append("low_context_density")
        return signals

    @staticmethod
    def _has_sensitive_context(utterance: str) -> bool:
        lowered = utterance.lower()
        return any(marker in lowered for marker in SENSITIVE_MARKERS)

    @staticmethod
    def _detect_crisis(utterance: str) -> Optional[str]:
        lowered = utterance.lower()
        crisis_markers = ("хочу умереть", "хочу исчезнуть", "kill myself", "suicide", "self-harm")
        for marker in crisis_markers:
            if marker in lowered:
                return marker
        return None
