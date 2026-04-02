import pytest
from codex.causal_memory.endocrine import EndocrineSystem

def test_init():
    """Verify initial hormone levels and mood index."""
    es = EndocrineSystem()
    assert es.hormones["dopamine"] == 0.5
    assert es.hormones["serotonin"] == 0.5
    assert es.hormones["cortisol"] == 0.3
    assert es.hormones["oxytocin"] == 0.4
    assert es.mood_index == 0.5

def test_update_from_interaction():
    """Verify hormone updates with specific inputs."""
    es = EndocrineSystem()
    # resonance=0.5, phantom_pain=0.2, harmony=0.4
    # dopamine: 0.5 + 0.5 * 0.1 = 0.55
    # serotonin: 0.5 + 0.4 * 0.08 = 0.532
    # cortisol: 0.3 + 0.2 * 0.15 = 0.33
    # oxytocin: 0.4 + (1 - 0.2) * 0.05 = 0.44
    es.update_from_interaction(resonance=0.5, phantom_pain=0.2, harmony=0.4)

    assert es.hormones["dopamine"] == pytest.approx(0.55)
    assert es.hormones["serotonin"] == pytest.approx(0.532)
    assert es.hormones["cortisol"] == pytest.approx(0.33)
    assert es.hormones["oxytocin"] == pytest.approx(0.44)

    # Mood index calculation:
    # mood = 0.55 * 0.3 + 0.532 * 0.3 + (1 - 0.33) * 0.2 + 0.44 * 0.2
    # mood = 0.165 + 0.1596 + 0.134 + 0.088 = 0.5466
    assert es.mood_index == pytest.approx(0.5466)

def test_update_from_interaction_clamping():
    """Verify that hormone values are clamped between 0.0 and 1.0."""
    es = EndocrineSystem()

    # Test upper clamping
    es.update_from_interaction(resonance=10.0, phantom_pain=10.0, harmony=10.0)
    for h in es.hormones:
        assert es.hormones[h] <= 1.0

    # Test lower clamping
    es.hormones["dopamine"] = -0.5
    es._normalize()
    assert es.hormones["dopamine"] == 0.0

def test_update_from_idle():
    """Verify hormone recovery logic."""
    es = EndocrineSystem()
    # Initial: cortisol 0.3, oxytocin 0.4, serotonin 0.5
    # Idle:
    # cortisol: 0.3 * 0.9 = 0.27
    # oxytocin: 0.4 + 0.05 = 0.45
    # serotonin: 0.5 + 0.03 = 0.53
    es.update_from_idle()

    assert es.hormones["cortisol"] == pytest.approx(0.27)
    assert es.hormones["oxytocin"] == pytest.approx(0.45)
    assert es.hormones["serotonin"] == pytest.approx(0.53)

def test_influence_resonance():
    """Verify how mood index affects base resonance."""
    es = EndocrineSystem()
    base_res = 1.0

    # Neutral mood (0.5)
    # influence = 1.0 * (1 + (0.5 - 0.5) * 0.2) = 1.0
    assert es.influence_resonance(base_res) == pytest.approx(1.0)

    # High mood (0.7)
    es.mood_index = 0.7
    # influence = 1.0 * (1 + (0.7 - 0.5) * 0.2) = 1.0 * (1 + 0.04) = 1.04
    assert es.influence_resonance(base_res) == pytest.approx(1.04)

    # Low mood (0.3)
    es.mood_index = 0.3
    # influence = 1.0 * (1 + (0.3 - 0.5) * 0.2) = 1.0 * (1 - 0.04) = 0.96
    assert es.influence_resonance(base_res) == pytest.approx(0.96)

def test_serialization():
    """Verify to_dict and from_dict methods correctly handle the state."""
    es = EndocrineSystem()
    es.hormones["dopamine"] = 0.8
    es.mood_index = 0.7

    data = es.to_dict()
    assert data["hormones"]["dopamine"] == 0.8
    assert data["mood_index"] == 0.7

    new_es = EndocrineSystem()
    new_es.from_dict(data)
    assert new_es.hormones["dopamine"] == 0.8
    assert new_es.mood_index == 0.7

    # Test from_dict with None
    es.from_dict(None)
    assert es.mood_index == 0.7 # Should not change
