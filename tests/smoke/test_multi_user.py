import json
import sys

import pytest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from GhostGPT.modules.gui import GhostWindow
except Exception:  # pragma: no cover - optional GUI deps
    GhostWindow = None
from codex.causal_memory.amygdala import Amygdala


def test_different_users_have_different_p(tmp_path):
    amygdala_alex = Amygdala(user_id="alex", memory_dir=tmp_path, persist_state=True)
    amygdala_bob = Amygdala(user_id="bob", memory_dir=tmp_path, persist_state=True)

    amygdala_alex.learn_from_outcome(stable_interaction=True, user_engaged=True)
    amygdala_alex.learn_from_outcome(stable_interaction=True, user_engaged=True)

    amygdala_bob.learn_from_outcome(stable_interaction=False, user_engaged=False)

    assert amygdala_alex.personality_p > amygdala_bob.personality_p


def test_memory_isolated_per_user(tmp_path):
    alex = Amygdala(user_id="alex", memory_dir=tmp_path, persist_state=True)
    bob = Amygdala(user_id="bob", memory_dir=tmp_path, persist_state=True)

    alex.learn_from_outcome(stable_interaction=True, user_engaged=True)
    bob.evaluate(new_resonance=0.2, axis_position=0.9, delta_axis=0.6, affect=-0.9)

    alex_file = tmp_path / "user_alex.json"
    bob_file = tmp_path / "user_bob.json"

    assert alex_file.exists()
    assert bob_file.exists()

    alex_payload = json.loads(alex_file.read_text(encoding="utf-8"))
    bob_payload = json.loads(bob_file.read_text(encoding="utf-8"))

    assert alex_payload["user_id"] == "alex"
    assert bob_payload["user_id"] == "bob"
    assert alex_payload["personality_p"] != bob_payload["personality_p"]


@pytest.mark.skipif(GhostWindow is None, reason="PyQt6 is unavailable")
def test_switch_user_updates_visualization(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    updates: list[dict] = []
    dummy_window = SimpleNamespace()
    dummy_window.agent_loop = SimpleNamespace(
        causal_transitions=SimpleNamespace(
            amygdala=Amygdala(user_id="default", memory_dir=tmp_path / ".ghostgpt" / "memory", persist_state=True)
        )
    )
    dummy_window.update_amygdala_visual = updates.append
    dummy_window.lbl_status = SimpleNamespace(setText=lambda _: None)
    dummy_window.current_user_id = "default"

    GhostWindow.switch_user(dummy_window, "bob")

    assert dummy_window.current_user_id == "bob"
    assert dummy_window.agent_loop.causal_transitions.amygdala.user_id == "bob"
    assert updates
    assert "personality_p" in updates[-1]
