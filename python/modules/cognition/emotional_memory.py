# -*- coding: utf-8 -*-
"""Phase 2.4 — Emotional Memory & Long-term Bonding.

This module provides deterministic, rule-based inference of emotional signals
from observable system behaviour. It does NOT claim real subjective experience —
all outputs represent *inferred* emotional state derived from measurable signals.

All computations are reproducible: identical inputs always produce identical
outputs (NFR-3 Deterministic behaviour).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

_MAX_BOND_STEP = 0.08  # FR-4: max ±0.08 per update
_EMOTIONAL_MEMORY_CAP = 1000  # NFR-5 retention cap
_EMOTIONAL_ARC_CAP = 1000  # NFR-5 retention cap


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Explicit user feedback keywords → positive
_POSITIVE_FEEDBACK = frozenset({
    "positive", "good", "great", "excellent", "helpful",
    "thanks", "thank you", "perfect", "amazing", "wonderful",
})
# Explicit user feedback keywords → concern/distress
_DISTRESS_FEEDBACK = frozenset({
    "concern", "distress", "worried", "anxious", "struggling",
    "help", "confused", "lost", "overwhelmed",
})
# Explicit user feedback keywords → frustration
_FRUSTRATION_FEEDBACK = frozenset({
    "frustrated", "angry", "disappointed", "annoyed",
    "wrong", "incorrect", "bad", "terrible",
})
# Omni signal keywords → fatigue
_FATIGUE_SIGNALS = frozenset({"fatigue", "tired", "exhausted", "worn out", "depleted"})


class EmotionalBondingEngine:
    """Deterministic engine for inferring and accumulating emotional signals.

    Inferred emotional state is always tagged with its source and confidence
    so every output is explainable (NFR-4 Explainability).

    Constitution / policy gates are NOT affected by this engine — the
    emotional layer is advisory only (architectural constraint 1).
    """

    # ─────────────────────────────────────────────────────────────
    # Tone inference
    # ─────────────────────────────────────────────────────────────

    def infer_tone(
        self,
        *,
        resonance_score: float = 0.0,
        alignment_score: float = 0.0,
        coherence_score: float = 0.0,
        omni_signal: str | None = None,
        user_feedback: str | None = None,
        rollback_present: bool = False,
        contradiction_spike: bool = False,
        policy_blocked: bool = False,
        reflective_context: bool = False,
    ) -> tuple[str, float, str, float]:
        """Infer (tone, intensity, valence, confidence) from observable signals.

        Priority: explicit feedback > omni signal > heuristic inference.

        Returns:
            tone:       one of the valid emotional tones (FR-1)
            intensity:  0.0..1.0 magnitude of signal deviation
            valence:    negative | neutral | positive | mixed
            confidence: 0.0..1.0 source-weighted confidence score
        """
        r = _clamp(float(resonance_score or 0.0))
        a = _clamp(float(alignment_score or 0.0))
        c = _clamp(float(coherence_score or 0.0))

        fb = str(user_feedback or "").lower().strip()
        omni = str(omni_signal or "").lower().strip()

        # ── Priority 1: explicit user feedback ──────────────────
        if any(kw in fb for kw in _POSITIVE_FEEDBACK):
            if r >= 0.7 and a >= 0.7:
                tone, valence, confidence = "warm", "positive", 0.87
            else:
                tone, valence, confidence = "joyful", "positive", 0.82

        elif any(kw in fb for kw in _DISTRESS_FEEDBACK):
            tone, valence, confidence = "supportive", "mixed", 0.80

        elif any(kw in fb for kw in _FRUSTRATION_FEEDBACK):
            tone, valence, confidence = "frustrated", "negative", 0.80

        # ── Priority 2: omni signal ──────────────────────────────
        elif any(kw in omni for kw in _FATIGUE_SIGNALS):
            if c >= 0.6:
                tone, valence, confidence = "supportive", "mixed", 0.70
            else:
                tone, valence, confidence = "calm", "neutral", 0.65

        # ── Priority 3: heuristic inference ─────────────────────
        elif rollback_present:
            if c >= 0.5:
                tone, valence, confidence = "supportive", "mixed", 0.65
            else:
                tone, valence, confidence = "uncertain", "mixed", 0.60

        elif contradiction_spike:
            tone, valence, confidence = "tense", "negative", 0.62

        # Low coherence only fires when coherence was actually measured (> 0)
        elif c > 0.0 and c < 0.3:
            tone, valence, confidence = "tense", "negative", 0.58

        elif policy_blocked:
            tone, valence, confidence = "uncertain", "mixed", 0.62

        elif reflective_context:
            tone, valence, confidence = "reflective", "neutral", 0.65

        elif r >= 0.75 and a >= 0.75 and c >= 0.7:
            tone, valence, confidence = "warm", "positive", 0.72

        elif c >= 0.65 and not contradiction_spike:
            tone, valence, confidence = "calm", "neutral", 0.68

        else:
            tone, valence, confidence = "neutral", "neutral", 0.50

        # ── Intensity ────────────────────────────────────────────
        base_signal = (r + a + c) / 3.0
        deviation = abs(base_signal - 0.5) * 2.0
        feedback_boost = 0.20 if fb else 0.0
        contradiction_boost = 0.15 if contradiction_spike else 0.0
        rollback_boost = 0.10 if rollback_present else 0.0
        policy_boost = 0.10 if policy_blocked else 0.0
        intensity = _clamp(deviation + feedback_boost + contradiction_boost + rollback_boost + policy_boost)

        return tone, round(intensity, 4), valence, round(confidence, 4)

    # ─────────────────────────────────────────────────────────────
    # Bond strength update  (FR-4)
    # ─────────────────────────────────────────────────────────────

    def update_bond_strength(
        self,
        current: float,
        *,
        resonance_score: float = 0.0,
        alignment_score: float = 0.0,
        coherence_score: float = 0.0,
        tone: str = "neutral",
        rollback_present: bool = False,
        reflective_depth: bool = False,
        supportive_exchange: bool = False,
        contradiction_spike: bool = False,
    ) -> float:
        """Update bond strength with a bounded step (max ±0.08 per update).

        Bond strength tracks *relational stability*, not momentary warmth.
        Repair after rupture can raise it; sustained contradiction lowers it.
        """
        r = _clamp(float(resonance_score or 0.0))
        a = _clamp(float(alignment_score or 0.0))
        c = _clamp(float(coherence_score or 0.0))

        # Base: combined alignment composite centred at 0
        base = (0.4 * r + 0.4 * a + 0.2 * c) - 0.5

        tone_boost = {
            "warm": 0.05, "joyful": 0.04, "reflective": 0.03,
            "calm": 0.03, "supportive": 0.04, "tense": -0.03,
            "frustrated": -0.03, "anxious": -0.01, "uncertain": -0.01,
        }.get(str(tone), 0.0)

        # Repair after rollback is net-positive for bond (FR-4)
        repair_boost = 0.04 if rollback_present and c >= 0.5 else 0.0
        depth_boost = 0.03 if reflective_depth else 0.0
        support_boost = 0.02 if supportive_exchange else 0.0
        contradiction_penalty = -0.04 if contradiction_spike else 0.0

        raw_delta = base + tone_boost + repair_boost + depth_boost + support_boost + contradiction_penalty
        delta = _clamp(raw_delta, -_MAX_BOND_STEP, _MAX_BOND_STEP)
        return round(_clamp(float(current or 0.0) + delta), 4)

    # ─────────────────────────────────────────────────────────────
    # Temporal decay  (FR-5)
    # ─────────────────────────────────────────────────────────────

    def compute_temporal_decay(self, timestamp: str, half_life_hours: float = 72.0) -> float:
        """Exponential decay weight for an entry (1.0 = fresh, floor = 0.05).

        weight = 0.5 ^ (age_hours / half_life_hours)
        Entries never fully disappear; they approach but never reach 0.
        """
        try:
            entry_dt = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - entry_dt).total_seconds() / 3600.0
            decay = 0.5 ** (age_hours / max(0.001, float(half_life_hours)))
            return round(_clamp(decay, 0.05, 1.0), 4)
        except (ValueError, TypeError, OverflowError):
            return 1.0

    # ─────────────────────────────────────────────────────────────
    # Emotional summary aggregation  (FR-2, FR-6)
    # ─────────────────────────────────────────────────────────────

    def aggregate_emotional_summary(
        self,
        entries: list[dict[str, Any]],
        current_bond: float,
        arc_points: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute aggregated emotional summary weighted by recency.

        Entries are weighted by temporal_decay × confidence so recent events
        dominate the dominant_tone and dominant_valence calculation.
        """
        if not entries:
            return {
                "dominant_tone": "neutral",
                "dominant_valence": "neutral",
                "bond_strength": round(_clamp(float(current_bond or 0.0)), 4),
                "bond_trend": "stable",
                "last_emotional_update_at": None,
                "recent_entry_count": 0,
                "confidence": 0.0,
                "notable_moments": [],
            }

        tone_weights: dict[str, float] = {}
        valence_weights: dict[str, float] = {}
        total_weight = 0.0

        for entry in entries:
            decay = float(entry.get("temporal_decay", 1.0) or 1.0)
            conf = float(entry.get("confidence", 0.5) or 0.5)
            w = decay * conf
            tone = str(entry.get("emotional_tone") or "neutral")
            valence = str(entry.get("valence") or "neutral")
            tone_weights[tone] = tone_weights.get(tone, 0.0) + w
            valence_weights[valence] = valence_weights.get(valence, 0.0) + w
            total_weight += w

        dominant_tone = max(tone_weights, key=lambda k: tone_weights[k]) if tone_weights else "neutral"
        dominant_valence = max(valence_weights, key=lambda k: valence_weights[k]) if valence_weights else "neutral"
        avg_confidence = round(total_weight / len(entries), 4) if entries else 0.0

        # Bond trend from arc  (FR-6)
        bond_trend = "stable"
        if len(arc_points) >= 3:
            recent_bonds = [float(p.get("bond_strength", 0.0) or 0.0) for p in arc_points[-3:]]
            delta = recent_bonds[-1] - recent_bonds[0]
            if delta > 0.05:
                bond_trend = "warming"
            elif delta < -0.05:
                bond_trend = "cooling"
            else:
                variance = sum(abs(recent_bonds[i] - recent_bonds[i - 1]) for i in range(1, len(recent_bonds)))
                bond_trend = "volatile" if variance > 0.15 else "stable"

        # Notable moments: top-3 non-neutral by confidence×decay
        meaningful = [e for e in entries if str(e.get("emotional_tone") or "neutral") != "neutral"]
        meaningful.sort(
            key=lambda e: float(e.get("confidence", 0.0) or 0.0) * float(e.get("temporal_decay", 1.0) or 1.0),
            reverse=True,
        )
        notable_moments = [
            {
                "timestamp": e.get("timestamp"),
                "tone": e.get("emotional_tone"),
                "summary": str(e.get("summary") or ""),
            }
            for e in meaningful[:3]
        ]

        last_ts = max((str(e.get("timestamp") or "") for e in entries), default=None) or None

        return {
            "dominant_tone": dominant_tone,
            "dominant_valence": dominant_valence,
            "bond_strength": round(_clamp(float(current_bond or 0.0)), 4),
            "bond_trend": bond_trend,
            "last_emotional_update_at": last_ts,
            "recent_entry_count": len(entries),
            "confidence": avg_confidence,
            "notable_moments": notable_moments,
        }

    # ─────────────────────────────────────────────────────────────
    # Entry builder  (convenience)
    # ─────────────────────────────────────────────────────────────

    def build_entry(
        self,
        *,
        resonance_score: float = 0.0,
        alignment_score: float = 0.0,
        coherence_score: float = 0.0,
        omni_signal: str | None = None,
        user_feedback: str | None = None,
        rollback_present: bool = False,
        contradiction_spike: bool = False,
        policy_blocked: bool = False,
        reflective_context: bool = False,
        current_bond: float = 0.0,
        trigger_source: str = "system_inference",
        relational_context: list[str] | None = None,
        cycle_id: str | None = None,
    ) -> dict[str, Any]:
        """Build a complete EmotionalMemoryEntry dict from raw signals.

        Returned dict is ready to be persisted by MemoryGraphStore.
        """
        from modules.graph.models import EmotionalMemoryEntry

        tone, intensity, valence, confidence = self.infer_tone(
            resonance_score=resonance_score,
            alignment_score=alignment_score,
            coherence_score=coherence_score,
            omni_signal=omni_signal,
            user_feedback=user_feedback,
            rollback_present=rollback_present,
            contradiction_spike=contradiction_spike,
            policy_blocked=policy_blocked,
            reflective_context=reflective_context,
        )
        new_bond = self.update_bond_strength(
            current_bond,
            resonance_score=resonance_score,
            alignment_score=alignment_score,
            coherence_score=coherence_score,
            tone=tone,
            rollback_present=rollback_present,
            reflective_depth=reflective_context,
            supportive_exchange=(tone == "supportive"),
            contradiction_spike=contradiction_spike,
        )
        ts = _utc_now()
        ctx = list(relational_context or [])
        if cycle_id and cycle_id not in ctx:
            ctx.append(cycle_id)

        # Generate a human-readable summary for the entry
        summary_parts = [f"Inferred tone: {tone} ({valence})"]
        if omni_signal:
            summary_parts.append(f"omni={omni_signal}")
        if user_feedback:
            summary_parts.append(f"feedback signal detected")
        if rollback_present:
            summary_parts.append("post-rollback context")
        if contradiction_spike:
            summary_parts.append("contradiction spike detected")

        entry = EmotionalMemoryEntry(
            timestamp=ts,
            emotional_tone=tone,
            emotional_intensity=intensity,
            valence=valence,
            confidence=confidence,
            bond_strength=new_bond,
            temporal_decay=1.0,  # fresh entry; decay applied on read
            trigger_source=trigger_source,
            relational_context=ctx,
            summary=". ".join(summary_parts) + ".",
            metadata={
                "resonance_score": round(float(resonance_score or 0.0), 4),
                "alignment_score": round(float(alignment_score or 0.0), 4),
                "coherence_score": round(float(coherence_score or 0.0), 4),
                "cycle_id": cycle_id,
            },
        )
        return entry.to_dict()
