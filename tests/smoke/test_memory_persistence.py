from __future__ import annotations

import json
from pathlib import Path

from codex.causal_memory.amygdala import Amygdala
from codex.causal_memory.memory import MemoryService


def test_memory_load_default(tmp_path: Path) -> None:
    service = MemoryService(user_id="default", base_dir=str(tmp_path))

    assert service.load() == {}


def test_memory_save_and_reload(tmp_path: Path) -> None:
    service = MemoryService(user_id="default", base_dir=str(tmp_path))
    payload = {
        "user_id": "default",
        "personality_p": 0.78,
        "visceral": {
            "phantom_pain": 0.08,
            "resolution_strength": 0.72,
            "last_trigger_intensity": 0.12,
            "history": [
                {"ts": "2026-02-28T14:23:45Z", "event": "pain", "intensity": 0.35},
                {"ts": "2026-02-28T14:25:10Z", "event": "resolve", "strength": 0.25},
            ],
        },
    }

    service.save(payload)

    loaded = service.load()
    assert loaded == payload

    raw = json.loads((tmp_path / "user_default.json").read_text(encoding="utf-8"))
    assert raw["personality_p"] == 0.78


def test_visceral_persistence_across_init(tmp_path: Path) -> None:
    amygdala = Amygdala(user_id="default", memory_base_dir=str(tmp_path))
    amygdala.evaluate(
        new_resonance=0.2,
        axis_position=0.9,
        delta_axis=0.7,
        affect=-0.9,
    )
    amygdala.learn_from_outcome(stable_interaction=True, user_engaged=True)

    persisted_file = tmp_path / "user_default.json"
    assert persisted_file.exists()

    rehydrated = Amygdala(user_id="default", memory_base_dir=str(tmp_path))
    assert rehydrated.personality_p == amygdala.personality_p
    assert rehydrated.visceral.phantom_pain == amygdala.visceral.phantom_pain
    assert rehydrated.visceral.resolution_strength == amygdala.visceral.resolution_strength
    assert list(rehydrated.visceral.history) == list(amygdala.visceral.history)
