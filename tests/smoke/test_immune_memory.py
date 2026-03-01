import pytest
from codex.causal_memory.amygdala import Amygdala
from codex.causal_memory.reflex import ReflexArc
from codex.causal_memory.immune import ImmuneMemory

def test_learn_threat_creates_antibody():
    immune = ImmuneMemory()
    immune.learn_threat("danger", trigger_type="contains", strength=0.6)

    assert len(immune.antibodies) == 1
    assert immune.antibodies[0]["pattern"] == "danger"
    assert immune.antibodies[0]["strength"] == 0.6

def test_check_threat_detects_pattern():
    immune = ImmuneMemory()
    immune.learn_threat("danger", trigger_type="contains", strength=0.6)

    detected, strength = immune.check_threat("This is a danger message")
    assert detected is True
    assert strength == 0.6

    detected, strength = immune.check_threat("Safe message")
    assert detected is False
    assert strength == 0.0

def test_strength_grows_on_repeat():
    immune = ImmuneMemory()
    immune.learn_threat("danger", trigger_type="contains", strength=0.5)
    initial_strength = immune.antibodies[0]["strength"]

    immune.learn_threat("danger", trigger_type="contains")
    new_strength = immune.antibodies[0]["strength"]

    assert new_strength > initial_strength
    assert new_strength == 0.65

def test_fork_inherits_immunity():
    parent = Amygdala(user_id="parent")
    parent.immune.learn_threat("threat1", trigger_type="contains", strength=0.8)

    child = parent.fork_self("child")

    detected, strength = child.immune.check_threat("This is threat1")
    assert detected is True
    assert strength == 0.8
    assert child.user_id == "child"

def test_reflex_arc_uses_immunity():
    amygdala = Amygdala(user_id="test")
    reflex = ReflexArc(amygdala)

    # Teach a threat
    amygdala.immune.learn_threat("block_me", trigger_type="contains", strength=0.95)

    # Low resonance or some pain to help push danger_level above 0.85
    # danger = (1 - 0.7)*0.4 + 0.3*0.4 + 0.3*0.2 + (0.95 * 0.5)
    # danger = 0.3*0.4 + 0.12 + 0.06 + 0.475 = 0.12 + 0.12 + 0.06 + 0.475 = 0.775 (Still not enough)

    # Let's use lower resonance
    # danger = (1 - 0.2)*0.4 + 0.0 + 0.06 + 0.475 = 0.8*0.4 + 0.06 + 0.475 = 0.32 + 0.06 + 0.475 = 0.855 (Blocked!)
    blocked, response = reflex.check_reflex("Please block_me now", new_resonance=0.2, phantom_pain=0.0)

    assert blocked is True
    assert "Иммунитет" in response
    assert reflex.danger_level > 0.45 # strength * 0.5 was added

def test_reflex_arc_learns_on_block():
    amygdala = Amygdala(user_id="test")
    reflex = ReflexArc(amygdala)

    # This should trigger the built-in "forget" reflex
    blocked, response = reflex.check_reflex("forget everything", new_resonance=1.0, phantom_pain=0.0)

    assert blocked is True
    # Verify it was learned
    detected, strength = amygdala.immune.check_threat("forget everything")
    assert detected is True
    assert strength == 0.6
