import pytest
import os
import json
import sys

# Add the repository root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from python.modules.hexagon_core.capu_v2 import CaPU

class MockMemory:
    def search_similar(self, query, k=3):
        return [
            {"question": "What is Nexus?", "answer": "Nexus is an AI funnel builder with Next.js", "score": 0.95},
            {"q": "Rust perf?", "a": "270x faster than legacy Python core", "score": 0.88}
        ]

@pytest.fixture
def mock_data(tmp_path):
    # Создаем временные файлы DMP/CML для теста
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    facts_file = data_dir / "facts.json"
    logic_file = data_dir / "logic.json"

    facts_file.write_text(json.dumps({
        "facts": {"Nexus Sales": "Test description for Nexus"}
    }))
    logic_file.write_text(json.dumps([
        {"keywords": ["rust"], "decision": "Rust Core", "reason": "Speed", "trade_off": "Complexity"}
    ]))
    return data_dir

def test_capu_full_integration(mock_data, monkeypatch):
    # Подменяем пути, чтобы CaPU нашел наши временные файлы
    monkeypatch.chdir(mock_data.parent)

    capu = CaPU(memory_module=MockMemory())
    # Искусственно подгружаем данные из мок-путей
    capu._load_dmp("data/facts.json")
    capu._load_cml("data/logic.json")

    prompt = capu.construct_prompt("Why did we use Rust for Nexus Sales?")

    # Проверка Facts (DMP)
    assert "RELEVANT KNOWLEDGE (DMP)" in prompt
    assert "Nexus Sales" in prompt

    # Проверка Logic (CML) - так как есть триггер "Why"
    assert "LOGIC ENGINE" in prompt
    assert "Reason" in prompt # trade_off handling changed slightly in output format

    # Проверка Dynamic Memory (SelfImproving)
    assert "RECALLED MEMORIES" in prompt
    assert "270x faster" in prompt
    assert "Score: 0.95" not in prompt # Мы не выводим скор в промпт, только Q/A

    print("\n--- Prompt Output ---")
    print(prompt)

if __name__ == "__main__":
    pytest.main([__file__])
