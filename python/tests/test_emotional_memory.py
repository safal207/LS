# -*- coding: utf-8 -*-
"""Tests for Phase 2.4 — Emotional Memory & Long-term Bonding.

Covers:
  T-1  Model tests (EmotionalMemoryEntry)
  T-2  Store tests (MemoryGraphStore emotional methods)
  T-3  Builder tests (RelationalSelf with emotional_summary)
  T-6  Determinism tests
  T-7  Safety / boundary tests
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from modules.cognition.emotional_memory import EmotionalBondingEngine
from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import EmotionalMemoryEntry, RelationalSelf


# ──────────────────────────────────────────────────────────────
# T-1  Model tests
# ──────────────────────────────────────────────────────────────


class TestEmotionalMemoryEntryDefaults:
    def test_default_tone_is_neutral(self):
        entry = EmotionalMemoryEntry()
        assert entry.emotional_tone == "neutral"

    def test_default_valence_is_neutral(self):
        entry = EmotionalMemoryEntry()
        assert entry.valence == "neutral"

    def test_default_source_is_system_inference(self):
        entry = EmotionalMemoryEntry()
        assert entry.trigger_source == "system_inference"

    def test_default_schema_version(self):
        entry = EmotionalMemoryEntry()
        assert entry.schema_version == "1.0"

    def test_entry_id_is_unique(self):
        a = EmotionalMemoryEntry()
        b = EmotionalMemoryEntry()
        assert a.entry_id != b.entry_id

    def test_timestamp_is_set(self):
        entry = EmotionalMemoryEntry()
        assert entry.timestamp != ""


class TestEmotionalMemoryEntryClamping:
    def test_intensity_clamped_high(self):
        entry = EmotionalMemoryEntry(emotional_intensity=5.0)
        assert entry.emotional_intensity == 1.0

    def test_intensity_clamped_low(self):
        entry = EmotionalMemoryEntry(emotional_intensity=-1.0)
        assert entry.emotional_intensity == 0.0

    def test_confidence_clamped(self):
        entry = EmotionalMemoryEntry(confidence=99.0)
        assert entry.confidence == 1.0

    def test_bond_strength_clamped(self):
        entry = EmotionalMemoryEntry(bond_strength=-0.5)
        assert entry.bond_strength == 0.0

    def test_temporal_decay_clamped(self):
        entry = EmotionalMemoryEntry(temporal_decay=2.0)
        assert entry.temporal_decay == 1.0


class TestEmotionalMemoryEntryValidation:
    def test_invalid_tone_falls_back_to_neutral(self):
        entry = EmotionalMemoryEntry(emotional_tone="euphoric")
        assert entry.emotional_tone == "neutral"

    def test_invalid_valence_falls_back(self):
        entry = EmotionalMemoryEntry(valence="super_positive")
        assert entry.valence == "neutral"

    def test_invalid_trigger_source_falls_back(self):
        entry = EmotionalMemoryEntry(trigger_source="unknown_source")
        assert entry.trigger_source == "system_inference"

    def test_valid_tone_accepted(self):
        for tone in ("warm", "calm", "reflective", "joyful", "anxious",
                     "frustrated", "tense", "supportive", "uncertain", "neutral"):
            entry = EmotionalMemoryEntry(emotional_tone=tone)
            assert entry.emotional_tone == tone


class TestEmotionalMemoryEntrySerialisation:
    def test_to_dict_round_trip(self):
        entry = EmotionalMemoryEntry(
            emotional_tone="warm",
            emotional_intensity=0.7,
            valence="positive",
            confidence=0.85,
            bond_strength=0.6,
            trigger_source="user_feedback",
            summary="Test round-trip.",
        )
        d = entry.to_dict()
        restored = EmotionalMemoryEntry.from_dict(d)
        assert restored.emotional_tone == entry.emotional_tone
        assert restored.emotional_intensity == entry.emotional_intensity
        assert restored.confidence == entry.confidence
        assert restored.bond_strength == entry.bond_strength
        assert restored.summary == entry.summary

    def test_from_dict_with_missing_fields_uses_defaults(self):
        entry = EmotionalMemoryEntry.from_dict({})
        assert entry.emotional_tone == "neutral"
        assert entry.confidence == 0.5
        assert entry.trigger_source == "system_inference"

    def test_from_dict_clamps_out_of_range(self):
        entry = EmotionalMemoryEntry.from_dict({"emotional_intensity": 3.0, "confidence": -1.0})
        assert entry.emotional_intensity == 1.0
        assert entry.confidence == 0.0


# ──────────────────────────────────────────────────────────────
# T-1 / RelationalSelf emotional_summary field
# ──────────────────────────────────────────────────────────────


class TestRelationalSelfEmotionalSummaryField:
    def test_default_emotional_summary_is_empty(self):
        rs = RelationalSelf()
        assert rs.emotional_summary == {}

    def test_from_dict_preserves_emotional_summary(self):
        summary = {"dominant_tone": "warm", "bond_strength": 0.7}
        rs = RelationalSelf.from_dict({"emotional_summary": summary})
        assert rs.emotional_summary["dominant_tone"] == "warm"
        assert rs.emotional_summary["bond_strength"] == 0.7

    def test_from_dict_missing_emotional_summary_defaults_empty(self):
        rs = RelationalSelf.from_dict({"self_coherence_score": 0.8})
        assert rs.emotional_summary == {}

    def test_to_dict_includes_emotional_summary(self):
        rs = RelationalSelf(emotional_summary={"bond_trend": "warming"})
        d = rs.to_dict()
        assert d["emotional_summary"]["bond_trend"] == "warming"


# ──────────────────────────────────────────────────────────────
# EmotionalBondingEngine  (deterministic rules)
# ──────────────────────────────────────────────────────────────


class TestEmotionalBondingEngineToneInference:
    def setup_method(self):
        self.engine = EmotionalBondingEngine()

    def test_positive_feedback_high_scores_gives_warm(self):
        tone, _, valence, conf = self.engine.infer_tone(
            user_feedback="great",
            resonance_score=0.8,
            alignment_score=0.8,
        )
        assert tone == "warm"
        assert valence == "positive"
        assert conf >= 0.85

    def test_negation_suppresses_positive_match(self):
        tone, _, _, _ = self.engine.infer_tone(user_feedback="not good")
        assert tone not in ("warm", "joyful"), f"'not good' should not be positive, got {tone}"

    def test_negation_suppresses_frustration_match(self):
        tone, _, _, _ = self.engine.infer_tone(user_feedback="not frustrated at all")
        assert tone != "frustrated", f"negated frustration should not match"

    def test_positive_feedback_lower_scores_gives_joyful(self):
        tone, _, valence, _ = self.engine.infer_tone(
            user_feedback="good",
            resonance_score=0.5,
            alignment_score=0.5,
        )
        assert tone == "joyful"
        assert valence == "positive"

    def test_distress_feedback_gives_supportive(self):
        tone, _, valence, _ = self.engine.infer_tone(user_feedback="struggling")
        assert tone == "supportive"
        assert valence == "mixed"

    def test_frustration_feedback_gives_frustrated(self):
        tone, _, valence, _ = self.engine.infer_tone(user_feedback="frustrated")
        assert tone == "frustrated"
        assert valence == "negative"

    def test_fatigue_omni_high_coherence_gives_supportive(self):
        tone, _, _, _ = self.engine.infer_tone(omni_signal="fatigue", coherence_score=0.7)
        assert tone == "supportive"

    def test_fatigue_omni_low_coherence_gives_calm(self):
        tone, _, _, _ = self.engine.infer_tone(omni_signal="tired", coherence_score=0.3)
        assert tone == "calm"

    def test_contradiction_spike_gives_tense(self):
        tone, _, valence, _ = self.engine.infer_tone(contradiction_spike=True)
        assert tone == "tense"
        assert valence == "negative"

    def test_policy_blocked_gives_uncertain(self):
        tone, _, _, _ = self.engine.infer_tone(policy_blocked=True)
        assert tone == "uncertain"

    def test_reflective_context_gives_reflective(self):
        tone, _, _, _ = self.engine.infer_tone(reflective_context=True, coherence_score=0.6)
        assert tone == "reflective"

    def test_high_all_scores_gives_warm(self):
        tone, _, valence, _ = self.engine.infer_tone(
            resonance_score=0.9,
            alignment_score=0.9,
            coherence_score=0.85,
        )
        assert tone == "warm"
        assert valence == "positive"

    def test_no_signals_gives_neutral(self):
        tone, _, valence, conf = self.engine.infer_tone()
        assert tone == "neutral"
        assert valence == "neutral"
        assert conf == 0.50

    def test_intensity_in_range(self):
        for _ in range(5):
            _, intensity, _, _ = self.engine.infer_tone(
                resonance_score=0.9,
                alignment_score=0.9,
                user_feedback="great",
            )
            assert 0.0 <= intensity <= 1.0


class TestBilingualFeedbackLexicons:
    """T-8  Russian feedback lexicons in infer_tone()."""

    def setup_method(self):
        self.engine = EmotionalBondingEngine()

    def test_ru_positive_feedback_gives_joyful(self):
        tone, _, valence, _ = self.engine.infer_tone(user_feedback="спасибо")
        assert tone in ("joyful", "warm")
        assert valence == "positive"

    def test_ru_positive_high_scores_gives_warm(self):
        tone, _, valence, _ = self.engine.infer_tone(
            user_feedback="отлично",
            resonance_score=0.8,
            alignment_score=0.8,
        )
        assert tone == "warm"
        assert valence == "positive"

    def test_ru_distress_feedback_gives_supportive(self):
        tone, _, valence, _ = self.engine.infer_tone(user_feedback="запутался")
        assert tone == "supportive"
        assert valence == "mixed"

    def test_ru_frustration_feedback_gives_frustrated(self):
        tone, _, valence, _ = self.engine.infer_tone(user_feedback="бесит")
        assert tone == "frustrated"
        assert valence == "negative"

    def test_ru_negation_suppresses_positive(self):
        """«не помогло» should NOT fire positive tone."""
        tone, _, _, _ = self.engine.infer_tone(user_feedback="не помогло")
        assert tone not in ("warm", "joyful"), f"negated RU positive should not match, got {tone}"

    def test_ru_negation_suppresses_frustration(self):
        """«не бесит» should NOT fire frustrated tone."""
        tone, _, _, _ = self.engine.infer_tone(user_feedback="не бесит")
        assert tone != "frustrated", f"negated RU frustration should not match, got {tone}"

    def test_ru_feedback_помогло_positive(self):
        tone, _, valence, _ = self.engine.infer_tone(user_feedback="помогло")
        assert tone in ("joyful", "warm")
        assert valence == "positive"

    def test_mixed_ru_en_feedback_still_works(self):
        """Feedback string mixing languages should still be classified."""
        tone, _, valence, _ = self.engine.infer_tone(user_feedback="спасибо, very helpful")
        assert valence == "positive"


class TestEmotionalBondingEngineBondUpdate:
    def setup_method(self):
        self.engine = EmotionalBondingEngine()

    def test_max_step_not_exceeded_upward(self):
        new = self.engine.update_bond_strength(
            0.5, resonance_score=1.0, alignment_score=1.0, coherence_score=1.0, tone="warm"
        )
        assert new - 0.5 <= 0.08 + 1e-9

    def test_max_step_not_exceeded_downward(self):
        new = self.engine.update_bond_strength(
            0.5, resonance_score=0.0, alignment_score=0.0, tone="frustrated",
            contradiction_spike=True,
        )
        assert 0.5 - new <= 0.08 + 1e-9

    def test_result_clamped_to_01(self):
        new = self.engine.update_bond_strength(
            0.99, resonance_score=1.0, alignment_score=1.0, coherence_score=1.0, tone="warm"
        )
        assert 0.0 <= new <= 1.0

    def test_repair_after_rollback_can_increase_bond(self):
        before = 0.3
        # Repair after rupture: provide coherent resonance/alignment scores
        # alongside rollback flag to model a successful repair interaction
        after = self.engine.update_bond_strength(
            before,
            resonance_score=0.55,
            alignment_score=0.55,
            coherence_score=0.7,
            rollback_present=True,
            tone="supportive",
        )
        assert after >= before  # repair is net-positive

    def test_determinism(self):
        kwargs = dict(resonance_score=0.65, alignment_score=0.7, coherence_score=0.6, tone="calm")
        r1 = self.engine.update_bond_strength(0.5, **kwargs)
        r2 = self.engine.update_bond_strength(0.5, **kwargs)
        assert r1 == r2


class TestEmotionalBondingEngineDecay:
    def setup_method(self):
        self.engine = EmotionalBondingEngine()

    def test_fresh_timestamp_decay_near_one(self):
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        decay = self.engine.compute_temporal_decay(ts)
        assert decay >= 0.95

    def test_old_timestamp_decay_less_than_one(self):
        decay = self.engine.compute_temporal_decay("2020-01-01T00:00:00+00:00")
        assert decay < 0.5

    def test_decay_floor_is_respected(self):
        decay = self.engine.compute_temporal_decay("2000-01-01T00:00:00+00:00")
        assert decay >= 0.05

    def test_malformed_timestamp_returns_one(self):
        decay = self.engine.compute_temporal_decay("not-a-timestamp")
        assert decay == 1.0

    def test_determinism(self):
        ts = "2026-01-01T00:00:00+00:00"
        assert self.engine.compute_temporal_decay(ts) == self.engine.compute_temporal_decay(ts)

    def test_now_parameter_gives_exact_half_life(self):
        """With explicit now, 72h-old entry should give decay = 0.5 exactly."""
        from datetime import datetime, timezone, timedelta
        ref = datetime(2026, 4, 12, 12, 0, 0, tzinfo=timezone.utc)
        ts = (ref - timedelta(hours=72)).isoformat()
        decay = self.engine.compute_temporal_decay(ts, half_life_hours=72.0, now=ref)
        assert abs(decay - 0.5) < 0.001

    def test_now_parameter_determinism(self):
        from datetime import datetime, timezone
        ref = datetime(2026, 4, 12, 0, 0, 0, tzinfo=timezone.utc)
        ts = "2026-04-10T00:00:00+00:00"
        d1 = self.engine.compute_temporal_decay(ts, now=ref)
        d2 = self.engine.compute_temporal_decay(ts, now=ref)
        assert d1 == d2


class TestEmotionalBondingEngineAggregate:
    def setup_method(self):
        self.engine = EmotionalBondingEngine()

    def test_empty_entries_returns_stable_defaults(self):
        summary = self.engine.aggregate_emotional_summary([], 0.5, [])
        assert summary["dominant_tone"] == "neutral"
        assert summary["bond_strength"] == 0.5
        assert summary["bond_trend"] == "stable"
        assert summary["recent_entry_count"] == 0

    def test_dominant_tone_is_most_weighted(self):
        entries = [
            {"emotional_tone": "warm", "valence": "positive", "confidence": 0.9, "temporal_decay": 1.0},
            {"emotional_tone": "warm", "valence": "positive", "confidence": 0.8, "temporal_decay": 1.0},
            {"emotional_tone": "tense", "valence": "negative", "confidence": 0.4, "temporal_decay": 0.3},
        ]
        summary = self.engine.aggregate_emotional_summary(entries, 0.6, [])
        assert summary["dominant_tone"] == "warm"

    def test_warming_trend_detected(self):
        arc = [
            {"bond_strength": 0.3},
            {"bond_strength": 0.45},
            {"bond_strength": 0.62},
        ]
        entries = [{"emotional_tone": "warm", "valence": "positive", "confidence": 0.8, "temporal_decay": 1.0}]
        summary = self.engine.aggregate_emotional_summary(entries, 0.62, arc)
        assert summary["bond_trend"] == "warming"

    def test_cooling_trend_detected(self):
        arc = [
            {"bond_strength": 0.7},
            {"bond_strength": 0.55},
            {"bond_strength": 0.4},
        ]
        entries = [{"emotional_tone": "neutral", "valence": "neutral", "confidence": 0.5, "temporal_decay": 1.0}]
        summary = self.engine.aggregate_emotional_summary(entries, 0.4, arc)
        assert summary["bond_trend"] == "cooling"

    def test_notable_moments_excludes_neutral(self):
        entries = [
            {"emotional_tone": "neutral", "valence": "neutral", "confidence": 0.9, "temporal_decay": 1.0, "summary": ""},
            {"emotional_tone": "warm", "valence": "positive", "confidence": 0.8, "temporal_decay": 0.9, "summary": "Warm exchange."},
        ]
        summary = self.engine.aggregate_emotional_summary(entries, 0.5, [])
        tones_in_moments = [m["tone"] for m in summary["notable_moments"]]
        assert "neutral" not in tones_in_moments
        assert "warm" in tones_in_moments

    def test_determinism_same_inputs(self):
        entries = [
            {"emotional_tone": "calm", "valence": "neutral", "confidence": 0.7, "temporal_decay": 0.8, "summary": ""},
        ]
        arc = [{"bond_strength": 0.5}, {"bond_strength": 0.55}, {"bond_strength": 0.6}]
        r1 = self.engine.aggregate_emotional_summary(entries, 0.6, arc)
        r2 = self.engine.aggregate_emotional_summary(entries, 0.6, arc)
        assert r1 == r2


# ──────────────────────────────────────────────────────────────
# T-2  Store tests
# ──────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_store(tmp_path):
    return MemoryGraphStore(tmp_path / "cases.jsonl")


class TestStoreEmotionalMemory:
    def test_store_and_retrieve_entry(self, tmp_store):
        entry = EmotionalMemoryEntry(emotional_tone="warm", confidence=0.85)
        tmp_store.store_emotional_memory_entry(entry.to_dict())
        rows = tmp_store.get_emotional_memory(limit=10)
        assert len(rows) == 1
        assert rows[0]["emotional_tone"] == "warm"

    def test_multiple_entries_returned_in_order(self, tmp_store):
        for tone in ("neutral", "calm", "warm"):
            tmp_store.store_emotional_memory_entry(
                EmotionalMemoryEntry(emotional_tone=tone).to_dict()
            )
        rows = tmp_store.get_emotional_memory(limit=10)
        assert len(rows) == 3
        assert rows[-1]["emotional_tone"] == "warm"

    def test_malformed_jsonl_rows_skipped(self, tmp_store):
        path = tmp_store._emotional_memory_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write("NOT VALID JSON\n")
            f.write(json.dumps({"emotional_tone": "calm", "confidence": 0.7}) + "\n")
        rows = tmp_store.get_emotional_memory(limit=10)
        assert len(rows) == 1
        assert rows[0]["emotional_tone"] == "calm"

    def test_retention_cap_enforced(self, tmp_store):
        cap = MemoryGraphStore._EMOTIONAL_MEMORY_CAP
        for _ in range(cap + 10):
            tmp_store.store_emotional_memory_entry(EmotionalMemoryEntry().to_dict())
        rows = tmp_store.get_emotional_memory(limit=cap + 100)
        assert len(rows) <= cap

    def test_temporal_decay_refreshed_on_read(self, tmp_store):
        entry = EmotionalMemoryEntry(emotional_tone="warm", temporal_decay=0.0)
        tmp_store.store_emotional_memory_entry(entry.to_dict())
        rows = tmp_store.get_emotional_memory(limit=1)
        # fresh entry should have decay close to 1.0
        assert rows[0]["temporal_decay"] >= 0.9


class TestStoreEmotionalArc:
    def test_arc_appended_on_cycle_update(self, tmp_store):
        tmp_store.update_emotional_memory_from_cycle(
            cycle_id="c1", source="care_cycle",
            resonance_score=0.7, alignment_score=0.7,
        )
        arc = tmp_store.get_emotional_arc(limit=10)
        assert len(arc) == 1
        assert "bond_strength" in arc[0]
        assert arc[0]["cycle_id"] == "c1"

    def test_arc_cap_enforced(self, tmp_store):
        cap = MemoryGraphStore._EMOTIONAL_ARC_CAP
        for i in range(cap + 5):
            tmp_store._append_emotional_arc_point({"bond_strength": 0.5, "cycle_id": str(i)})
        arc = tmp_store.get_emotional_arc(limit=cap + 100)
        assert len(arc) <= cap

    def test_arc_malformed_rows_skipped(self, tmp_store):
        path = tmp_store._emotional_arc_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            f.write("GARBAGE\n")
            f.write(json.dumps({"bond_strength": 0.6}) + "\n")
        arc = tmp_store.get_emotional_arc(limit=10)
        assert len(arc) == 1

    def test_arc_atomic_write(self, tmp_store):
        # Verify no tmp files linger after write
        for _ in range(3):
            tmp_store._append_emotional_arc_point({"bond_strength": 0.5})
        tmp_files = list(tmp_store._emotional_arc_path().parent.glob("*.tmp"))
        assert len(tmp_files) == 0


class TestStoreEmotionalSummaryInSelf:
    def test_emotional_summary_written_to_relational_self(self, tmp_store):
        tmp_store.update_emotional_memory_from_cycle(
            cycle_id="c1", source="care_cycle",
            resonance_score=0.8, alignment_score=0.8,
        )
        rs = tmp_store.get_relational_self()
        assert rs.emotional_summary != {}
        assert "dominant_tone" in rs.emotional_summary
        assert "bond_strength" in rs.emotional_summary

    def test_emotional_summary_preserved_across_cognitive_update(self, tmp_store):
        tmp_store.update_emotional_memory_from_cycle(
            cycle_id="c1", source="care_cycle",
            resonance_score=0.8, alignment_score=0.8,
        )
        summary_before = dict(tmp_store.get_relational_self().emotional_summary)
        # Cognitive update should preserve emotional_summary
        tmp_store.update_self_from_cycle(cycle_id="c2", source="care_cycle")
        summary_after = dict(tmp_store.get_relational_self().emotional_summary)
        assert summary_after == summary_before


# ──────────────────────────────────────────────────────────────
# T-3  Builder tests
# ──────────────────────────────────────────────────────────────


class TestRelationalSelfBuilderEmotionalSummary:
    def test_current_returns_emotional_summary(self, tmp_store):
        from modules.cognition.relational_self import RelationalSelfBuilder

        tmp_store.update_emotional_memory_from_cycle(
            cycle_id="c1", source="care_cycle",
            resonance_score=0.75, alignment_score=0.75,
        )
        builder = RelationalSelfBuilder(store=tmp_store)
        rs = builder.current()
        assert isinstance(rs.emotional_summary, dict)
        assert "dominant_tone" in rs.emotional_summary

    def test_update_returns_emotional_summary(self, tmp_store):
        from modules.cognition.relational_self import RelationalSelfBuilder

        tmp_store.update_emotional_memory_from_cycle(
            cycle_id="c1", source="care_cycle",
            resonance_score=0.7, alignment_score=0.7,
        )
        builder = RelationalSelfBuilder(store=tmp_store)
        rs = builder.update(cycle_id="c2", source="test")
        assert isinstance(rs.emotional_summary, dict)


# ──────────────────────────────────────────────────────────────
# T-6  Determinism tests
# ──────────────────────────────────────────────────────────────


class TestDeterminism:
    def test_same_input_same_tone(self):
        engine = EmotionalBondingEngine()
        kwargs = dict(
            resonance_score=0.7,
            alignment_score=0.8,
            coherence_score=0.65,
            user_feedback="great",
        )
        r1 = engine.infer_tone(**kwargs)
        r2 = engine.infer_tone(**kwargs)
        assert r1 == r2

    def test_same_input_same_bond(self):
        engine = EmotionalBondingEngine()
        kwargs = dict(resonance_score=0.6, alignment_score=0.7, tone="calm")
        r1 = engine.update_bond_strength(0.4, **kwargs)
        r2 = engine.update_bond_strength(0.4, **kwargs)
        assert r1 == r2

    def test_same_entries_same_summary(self):
        engine = EmotionalBondingEngine()
        entries = [
            {"emotional_tone": "warm", "valence": "positive", "confidence": 0.85, "temporal_decay": 0.9, "summary": ""},
            {"emotional_tone": "calm", "valence": "neutral", "confidence": 0.7, "temporal_decay": 0.8, "summary": ""},
        ]
        arc = [{"bond_strength": 0.4}, {"bond_strength": 0.5}, {"bond_strength": 0.6}]
        r1 = engine.aggregate_emotional_summary(entries, 0.6, arc)
        r2 = engine.aggregate_emotional_summary(entries, 0.6, arc)
        assert r1 == r2


# ──────────────────────────────────────────────────────────────
# T-7  Safety / boundary tests
# ──────────────────────────────────────────────────────────────


class TestSafetyBoundaries:
    def test_emotional_context_does_not_alter_constitution_flag(self, tmp_store):
        """Constitution outcome must be independent of emotional state."""
        from modules.graph.models import RelationalSelf
        from modules.council.council_engine import RelationalCouncilEngine

        # Create a RelationalSelf with a "warm" emotional_summary
        rs = RelationalSelf(
            self_coherence_score=0.2,  # below threshold → breach
            emotional_summary={
                "dominant_tone": "warm",
                "bond_strength": 0.99,
                "bond_trend": "warming",
                "confidence": 0.95,
            },
        )
        engine = RelationalCouncilEngine(coherence_guard_threshold=0.4)
        result = engine.run_mode(mode="self-preservation", relational_self=rs)
        # Even with a "warm" bond, coherence breach must still block
        assert result["blocked"] is True

    def test_emotional_context_present_in_output_but_not_gate(self, tmp_store):
        """emotional_context key is informational; constitution_override must be False."""
        from modules.graph.models import RelationalSelf
        from modules.council.council_engine import RelationalCouncilEngine

        rs = RelationalSelf(
            self_coherence_score=0.8,
            emotional_summary={"dominant_tone": "tense", "bond_strength": 0.1},
        )
        engine = RelationalCouncilEngine()
        result = engine.run_mode(mode="self-preservation", relational_self=rs)
        ctx = result.get("emotional_context", {})
        if ctx:
            assert ctx.get("constitution_override") is False

    def test_schema_version_present_in_entry(self):
        entry = EmotionalMemoryEntry()
        d = entry.to_dict()
        assert d["schema_version"] == "1.0"

    def test_negative_event_does_not_break_schema(self, tmp_store):
        tmp_store.update_emotional_memory_from_cycle(
            cycle_id="neg1", source="care_cycle",
            resonance_score=0.1, alignment_score=0.1,
            contradiction_spike=True,
        )
        rows = tmp_store.get_emotional_memory(limit=5)
        assert len(rows) == 1
        entry = EmotionalMemoryEntry.from_dict(rows[0])
        assert entry.schema_version == "1.0"
        assert 0.0 <= entry.bond_strength <= 1.0

    def test_emotional_layer_does_not_appear_in_existing_mcp_keys(self, tmp_store):
        """Existing MCP consumers must not be broken by new emotional fields."""
        rs = tmp_store.get_relational_self()
        d = rs.to_dict()
        # Core existing keys remain
        assert "self_coherence_score" in d
        assert "core_nodes" in d
        assert "core_edges" in d
        # emotional_summary is additive — present but empty by default
        assert "emotional_summary" in d
