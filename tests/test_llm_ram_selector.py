import queue
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

sys.modules.setdefault("requests", MagicMock())

from python.modules.llm import llm_module
from python.modules.llm.ram_model_selector import select_model


def test_select_heavy_when_enough_ram():
    primary, fallback = select_model(available_ram_gb=8.0)
    assert primary == "qwen2.5:7b-instruct-q5_k_m"
    assert fallback == "phi4:mini-q5_k_m"


def test_select_light_when_low_ram():
    primary, fallback = select_model(available_ram_gb=4.0)
    assert primary == "phi4:mini-q5_k_m"
    assert fallback == "phi4:mini-q5_k_m"


def test_fallback_on_primary_failure():
    model = llm_module.LanguageModel(queue.Queue(), queue.Queue(), use_breaker=False)
    model.primary_model = "heavy"
    model.fallback_model = "light"
    model.qwen_handler.model_name = "heavy"

    def fake_generate_response(_prompt: str):
        if model.qwen_handler.model_name == "heavy":
            raise RuntimeError("heavy unavailable")
        return "ok-from-light"

    model.qwen_handler.generate_response = fake_generate_response

    response = model.generate_response_local("ping")
    assert response == "ok-from-light"
    assert model.qwen_handler.model_name == "heavy"


def test_e2e_in_ghostgpt(caplog, monkeypatch):
    monkeypatch.setattr(llm_module, "LLM_RAM_AWARE", True)

    monkeypatch.setattr(llm_module, "get_available_ram_gb", lambda: 8.0)
    with caplog.at_level("INFO"):
        high_ram_model = llm_module.LanguageModel(queue.Queue(), queue.Queue(), use_breaker=False)
    assert high_ram_model.primary_model == "qwen2.5:7b-instruct-q5_k_m"
    assert high_ram_model.fallback_model == "phi4:mini-q5_k_m"

    monkeypatch.setattr(llm_module, "get_available_ram_gb", lambda: 4.0)
    low_ram_model = llm_module.LanguageModel(queue.Queue(), queue.Queue(), use_breaker=False)
    assert low_ram_model.primary_model == "phi4:mini-q5_k_m"
    assert low_ram_model.fallback_model == "phi4:mini-q5_k_m"
    assert "RAM-aware model selection" in caplog.text
