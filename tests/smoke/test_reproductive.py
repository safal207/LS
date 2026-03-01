import pytest
import os
import shutil
from pathlib import Path
from codex.causal_memory.amygdala import Amygdala
from python.modules.hexagon_core.temporal_graph import TemporalGraph, TemporalNode

@pytest.fixture
def clean_memory():
    base_dir = Path.home() / ".ghostgpt" / "memory_test_reproductive"
    if base_dir.exists():
        shutil.rmtree(base_dir)
    yield str(base_dir)
    if base_dir.exists():
        shutil.rmtree(base_dir)

def test_fork_creates_valid_child(clean_memory):
    parent = Amygdala(user_id="parent", memory_dir=clean_memory, persist_state=True)
    parent.state = 0.6
    parent.endocrine.hormones["dopamine"] = 0.8
    parent._persist_state()

    child = parent.fork_self("child_1", mutation_factor=0.0)

    assert child.user_id == "parent_fork_child_1"
    assert child.state == parent.state
    assert child.endocrine.hormones["dopamine"] == parent.endocrine.hormones["dopamine"]
    assert "parent_fork_child_1" in parent.offspring_ids

def test_mutation_changes_hormones(clean_memory):
    parent = Amygdala(user_id="parent", memory_dir=clean_memory, persist_state=True)

    # Large mutation factor to guarantee change
    child = parent.fork_self("child_mutant", mutation_factor=1.0)

    # Check if at least one hormone changed
    changed = False
    for h in parent.endocrine.hormones:
        if child.endocrine.hormones[h] != parent.endocrine.hormones[h]:
            changed = True
            break
    assert changed
    # State should also likely change
    assert child.state != parent.state or changed

def test_best_offspring_selected_by_merit():
    tg = TemporalGraph()
    offspring = ["child_A", "child_B", "child_C"]

    tg.nodes["child_A"] = TemporalNode(id="child_A", resonance=0.5, harmony_bonus=0.1)  # score 0.55
    tg.nodes["child_B"] = TemporalNode(id="child_B", resonance=0.8, harmony_bonus=0.0)  # score 0.8
    tg.nodes["child_C"] = TemporalNode(id="child_C", resonance=0.6, harmony_bonus=0.5)  # score 0.9

    best = tg.select_best_offspring(offspring)
    assert best == "child_C"

def test_child_persists_independently(clean_memory):
    parent = Amygdala(user_id="parent", memory_dir=clean_memory, persist_state=True)
    child = parent.fork_self("independent", mutation_factor=0.0)

    child.state = 0.1
    child.endocrine.hormones["serotonin"] = 0.9
    child._persist_state()

    # Reload child
    child_reloaded = Amygdala(user_id=child.user_id, memory_dir=clean_memory, persist_state=True)
    assert child_reloaded.state == 0.1
    assert child_reloaded.endocrine.hormones["serotonin"] == 0.9

    # Parent should be unchanged
    parent_reloaded = Amygdala(user_id="parent", memory_dir=clean_memory, persist_state=True)
    assert parent_reloaded.state != 0.1
