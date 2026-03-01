import pytest
import os
import json
import zipfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from codex.causal_memory.amygdala import Amygdala
from codex.causal_memory.memory import MemoryService

def test_amygdala_reflection_trigger(tmp_path):
    memory_dir = tmp_path / "memory"
    # Ensure datetime.now() - last_reflection > 1 hour
    amy = Amygdala(user_id="test_reflect", memory_dir=memory_dir, persist_state=True)
    amy.last_reflection = datetime.now() - timedelta(hours=2)

    # Simulate 48 interactions (increments by 2 each call)
    for i in range(24):
        amy.evaluate(new_resonance=0.8, axis_position=0.1, delta_axis=0.0, affect=0.0)

    assert amy.interaction_count == 48
    # The 49th call (bringing count to 50) will trigger it inside evaluate
    amy.evaluate(new_resonance=0.8, axis_position=0.1, delta_axis=0.0, affect=0.0)
    assert amy.interaction_count == 50
    # should_reflect is now False because evaluate() updated last_reflection (cooldown)
    assert amy.should_reflect() is False
    assert (datetime.now() - amy.last_reflection).total_seconds() < 10

def test_amygdala_pain_reflection_trigger(tmp_path):
    memory_dir = tmp_path / "memory"
    amy = Amygdala(user_id="test_pain", memory_dir=memory_dir, persist_state=True)
    amy.last_reflection = datetime.now() - timedelta(hours=2)

    # Simulate 3 pain episodes
    for i in range(20): # Ensure history
        amy.evaluate(new_resonance=0.8, axis_position=0.1, delta_axis=0.0, affect=0.0)

    for i in range(2):
        # We need to trigger phantom_pain > 0.3
        amy.visceral.record_pain(0.4)
        amy.evaluate(new_resonance=0.4, axis_position=0.8, delta_axis=0.3, affect=-0.6)

    # 3rd one triggers it
    amy.visceral.record_pain(0.4)
    amy.evaluate(new_resonance=0.4, axis_position=0.8, delta_axis=0.3, affect=-0.6)

    assert amy.pain_episodes >= 3
    # should_reflect is now False because evaluate() updated last_reflection (cooldown)
    assert amy.should_reflect() is False
    assert (datetime.now() - amy.last_reflection).total_seconds() < 10

def test_reflection_cooldown(tmp_path):
    memory_dir = tmp_path / "memory"
    amy = Amygdala(user_id="test_cooldown", memory_dir=memory_dir, persist_state=True)
    amy.last_reflection = datetime.now() - timedelta(minutes=30)

    # Simulate 50 interactions
    for i in range(25):
        amy.evaluate(new_resonance=0.8, axis_position=0.1, delta_axis=0.0, affect=0.0)

    assert amy.interaction_count == 50
    assert amy.should_reflect() is False  # Should be blocked by cooldown

def test_soul_export_import_logic(tmp_path):
    memory_dir = tmp_path / "memory"
    user_id = "soul_user"
    amy = Amygdala(user_id=user_id, memory_dir=memory_dir, persist_state=True)

    # Set some state
    amy.visceral.record_pain(0.5)
    amy.interaction_count = 121
    amy.evaluate(new_resonance=0.7, axis_position=0.2, delta_axis=0.0, affect=0.0)

    # Manually simulate export logic (what GhostWindow does)
    memory_file = memory_dir / f"user_{user_id}.json"
    assert memory_file.exists()
    memory_data = json.loads(memory_file.read_text())

    zip_path = tmp_path / "soul.zip"
    manifest = {
        "user_id": user_id,
        "interaction_count": amy.interaction_count,
        "last_reflection": amy.last_reflection.isoformat(),
        "current_phantom_pain": amy.visceral.phantom_pain
    }

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("memory.json", json.dumps(memory_data))
        zf.writestr("manifest.json", json.dumps(manifest))

    # Import into a fresh instance
    new_memory_dir = tmp_path / "new_memory"
    new_amy = Amygdala(user_id="new_user", memory_dir=new_memory_dir, persist_state=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        imported_memory = json.loads(zf.read("memory.json"))

    new_amy.restore_state(imported_memory)

    assert new_amy.interaction_count == 123
    assert new_amy.visceral.phantom_pain > 0.4  # should be preserved

    # Check visceral history
    pain_events = [h for h in new_amy.visceral.history if h.get("event") == "pain"]
    assert len(pain_events) > 0
