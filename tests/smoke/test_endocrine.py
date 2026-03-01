import pytest
import time
from codex.causal_memory.endocrine import EndocrineSystem
from codex.causal_memory.amygdala import Amygdala

def test_hormone_initial_levels():
    es = EndocrineSystem()
    assert es.hormones["dopamine"] == 0.5
    assert es.hormones["serotonin"] == 0.5
    assert es.hormones["cortisol"] == 0.3
    assert es.hormones["oxytocin"] == 0.4
    assert es.mood_index == 0.5

def test_hormone_update_from_interaction():
    es = EndocrineSystem()
    initial_dopamine = es.hormones["dopamine"]

    # Positive interaction: resonance=0.8, pain=0.0, harmony=0.8
    es.update_from_interaction(resonance=0.8, phantom_pain=0.0, harmony=0.8)

    assert es.hormones["dopamine"] > initial_dopamine
    assert es.hormones["serotonin"] > 0.5
    assert es.hormones["cortisol"] == 0.3 # no change since pain is 0
    assert es.hormones["oxytocin"] > 0.4
    assert es.mood_index > 0.5

def test_hormone_recovery_in_idle():
    es = EndocrineSystem()
    es.hormones["cortisol"] = 0.8
    es.update_from_idle()

    assert es.hormones["cortisol"] < 0.8
    assert es.hormones["serotonin"] > 0.5
    assert es.hormones["oxytocin"] > 0.4

def test_mood_influence_on_resonance():
    es = EndocrineSystem()
    base_res = 0.5

    # Neutral mood (0.5)
    assert es.influence_resonance(base_res) == 0.5

    # High mood
    es.hormones["dopamine"] = 0.9
    es.hormones["serotonin"] = 0.9
    es._update_mood()
    assert es.influence_resonance(base_res) > 0.5

    # Low mood
    es.hormones["dopamine"] = 0.1
    es.hormones["serotonin"] = 0.1
    es.hormones["cortisol"] = 0.9
    es._update_mood()
    assert es.influence_resonance(base_res) < 0.5

def test_amygdala_endocrine_integration():
    amy = Amygdala(persist_state=False)
    initial_dopamine = amy.endocrine.hormones["dopamine"]

    # Successful evaluation should update hormones
    amy.evaluate(new_resonance=0.9, axis_position=0.2, delta_axis=0.1, affect=0.5, harmony_score=0.8)

    assert amy.endocrine.hormones["dopamine"] > initial_dopamine
    assert amy.endocrine.mood_index > 0.5

def test_balance_after_high_pain():
    es = EndocrineSystem()
    # Simulate stress
    for _ in range(5):
        es.update_from_interaction(resonance=0.2, phantom_pain=0.8, harmony=0.1)

    assert es.hormones["cortisol"] > 0.5
    assert es.mood_index < 0.5

    # Recovery
    for _ in range(10):
        es.update_from_idle()

    assert es.hormones["cortisol"] < 0.4
    assert es.mood_index > 0.4
