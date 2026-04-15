# -*- coding: utf-8 -*-
import json
import pytest
from codex.causal_memory.amygdala import Amygdala

def test_to_snapshot_basic():
    """Test that to_snapshot returns a dictionary with all expected keys and correct types."""
    amygdala = Amygdala(persist_state=False)
    snapshot = amygdala.to_snapshot()

    expected_keys = {
        "state", "resonance", "adaptive_bias", "personality_p",
        "protection_shift", "interaction_count", "pain_episodes",
        "phantom_pain", "resolution_strength", "endocrine",
        "metabolism", "immune", "last_silent_reflection", "last_proposal"
    }

    assert set(snapshot.keys()) == expected_keys
    assert isinstance(snapshot["state"], float)
    assert isinstance(snapshot["resonance"], float)
    assert isinstance(snapshot["adaptive_bias"], float)
    assert isinstance(snapshot["personality_p"], float)
    assert isinstance(snapshot["protection_shift"], float)
    assert isinstance(snapshot["interaction_count"], int)
    assert isinstance(snapshot["pain_episodes"], int)
    assert isinstance(snapshot["phantom_pain"], float)
    assert isinstance(snapshot["resolution_strength"], float)
    assert isinstance(snapshot["endocrine"], dict)
    assert isinstance(snapshot["metabolism"], dict)
    assert isinstance(snapshot["immune"], dict)

def test_to_snapshot_values():
    """Test that to_snapshot values match the Amygdala instance state."""
    amygdala = Amygdala(persist_state=False)
    amygdala.state = 0.7
    amygdala.adaptive_bias = 0.1
    amygdala.personality_p = 0.6
    amygdala.protection_shift = -0.05
    amygdala.interaction_count = 42
    amygdala.pain_episodes = 3
    amygdala.visceral.phantom_pain = 0.2
    amygdala.visceral.resolution_strength = 0.15
    amygdala.last_silent_reflection = "test reflection"
    amygdala.last_proposal = "test proposal"

    snapshot = amygdala.to_snapshot()

    assert snapshot["state"] == 0.7
    assert snapshot["resonance"] == 0.3 # 1.0 - 0.7
    assert snapshot["adaptive_bias"] == 0.1
    assert snapshot["personality_p"] == 0.6
    assert snapshot["protection_shift"] == -0.05
    assert snapshot["interaction_count"] == 42
    assert snapshot["pain_episodes"] == 3
    assert snapshot["phantom_pain"] == 0.2
    assert snapshot["resolution_strength"] == 0.15
    assert snapshot["last_silent_reflection"] == "test reflection"
    assert snapshot["last_proposal"] == "test proposal"

def test_to_snapshot_json_serializable():
    """Test that the snapshot can be serialized to JSON."""
    amygdala = Amygdala(persist_state=False)
    snapshot = amygdala.to_snapshot()
    try:
        json_str = json.dumps(snapshot)
        assert isinstance(json_str, str)
    except (TypeError, ValueError) as e:
        pytest.fail(f"Snapshot is not JSON serializable: {e}")

def test_from_snapshot():
    """Test that Amygdala state can be restored from a snapshot."""
    amygdala = Amygdala(persist_state=False)
    snapshot = {
        "state": 0.8,
        "adaptive_bias": 0.15,
        "personality_p": 0.4,
        "protection_shift": 0.05,
        "interaction_count": 100,
        "pain_episodes": 5,
        "phantom_pain": 0.45,
        "resolution_strength": 0.3,
        "endocrine": {
            "hormones": {
                "dopamine": 0.1,
                "serotonin": 0.2,
                "cortisol": 0.8,
                "oxytocin": 0.1
            },
            "mood_index": 0.2
        },
        "metabolism": {
            "waste_bin": [],
            "lessons": ["lesson 1"],
            "nutrient_pool": 0.5
        },
        "immune": {
            "antibodies": [{"pattern": "danger", "type": "regex", "strength": 0.9}]
        },
        "last_silent_reflection": "old reflection",
        "last_proposal": "old proposal"
    }

    amygdala.from_snapshot(snapshot)

    assert amygdala.state == 0.8
    assert amygdala.adaptive_bias == 0.15
    assert amygdala.personality_p == 0.4
    assert amygdala.protection_shift == 0.05
    assert amygdala.interaction_count == 100
    assert amygdala.pain_episodes == 5
    assert amygdala.phantom_pain == 0.45
    assert amygdala.visceral.resolution_strength == 0.3
    assert amygdala.endocrine.hormones["dopamine"] == 0.1
    assert amygdala.metabolism.lessons == ["lesson 1"]
    assert amygdala.metabolism.nutrient_pool == 0.5
    assert len(amygdala.immune.antibodies) == 1
    assert amygdala.immune.antibodies[0]["pattern"] == "danger"
    assert amygdala.last_silent_reflection == "old reflection"
    assert amygdala.last_proposal == "old proposal"

def test_snapshot_roundtrip():
    """Test that state is preserved after to_snapshot -> from_snapshot."""
    amygdala = Amygdala(persist_state=False)

    # Set some non-default values
    amygdala.state = 0.3
    amygdala.adaptive_bias = -0.1
    amygdala.personality_p = 0.9
    amygdala.interaction_count = 7
    amygdala.endocrine.hormones["dopamine"] = 0.8
    amygdala.metabolism.nutrient_pool = 1.2
    amygdala.immune.learn_threat("hack", strength=0.7)

    original_snapshot = amygdala.to_snapshot()

    # Create a new instance and restore from snapshot
    new_amygdala = Amygdala(persist_state=False)
    new_amygdala.from_snapshot(original_snapshot)

    new_snapshot = new_amygdala.to_snapshot()

    # Compare snapshots (except maybe timestamps if they were included, but they aren't in to_snapshot)
    assert new_snapshot == original_snapshot

    # Also check internal state specifically
    assert new_amygdala.state == amygdala.state
    assert new_amygdala.adaptive_bias == amygdala.adaptive_bias
    assert new_amygdala.personality_p == amygdala.personality_p
    assert new_amygdala.interaction_count == amygdala.interaction_count
    assert new_amygdala.endocrine.hormones == amygdala.endocrine.hormones
    assert new_amygdala.metabolism.nutrient_pool == amygdala.metabolism.nutrient_pool
    assert new_amygdala.immune.antibodies == amygdala.immune.antibodies
