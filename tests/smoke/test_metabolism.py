import pytest
from unittest.mock import MagicMock
from codex.causal_memory.amygdala import Amygdala
from codex.causal_memory.metabolism import Metabolism

def test_metabolism_digestion():
    amy = MagicMock(spec=Amygdala)
    amy.last_silent_reflection = "Тишина и покой в системе."
    engine = Metabolism(amy)

    engine.digest_old_reflections()

    assert len(engine.waste_bin) == 1
    assert engine.waste_bin[0]["type"] == "reflection"
    assert "Тишина и покой" in engine.waste_bin[0]["content"]
    assert engine.nutrient_pool == pytest.approx(0.05)
    assert engine.nutrient_pool > 0.0

def test_metabolism_composting():
    amy = MagicMock(spec=Amygdala)
    engine = Metabolism(amy)

    engine.compost_pruned_nodes(5)

    assert len(engine.waste_bin) == 1
    assert engine.waste_bin[0]["type"] == "pruned"
    assert engine.waste_bin[0]["count"] == 5
    assert engine.nutrient_pool == pytest.approx(0.05)
    assert engine.nutrient_pool >= 0.05

def test_metabolism_feed_growth():
    amy = MagicMock(spec=Amygdala)
    amy.state = 0.5
    engine = Metabolism(amy)

    # Need at least 0.1 nutrient
    engine.nutrient_pool = 0.2
    boost = engine.feed_growth()

    assert boost > 0
    assert amy.state < 0.5
    assert engine.nutrient_pool < 0.2
    assert engine.nutrient_pool == pytest.approx(0.1)

def test_metabolism_persistence():
    amy = MagicMock(spec=Amygdala)
    engine = Metabolism(amy)
    engine.nutrient_pool = 0.42
    engine.waste_bin = [{"type": "test"}]

    data = engine.to_dict()
    assert data["nutrient_pool"] == 0.42
    assert len(data["waste_bin"]) == 1

    engine2 = Metabolism(amy)
    engine2.from_dict(data)
    assert engine2.nutrient_pool == 0.42
    assert len(engine2.waste_bin) == 1
