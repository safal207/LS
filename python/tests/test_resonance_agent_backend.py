import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modules.agent.resonance_agent import ResonanceAgent
from modules.llm.backends.base import LLMResponse


class FakeBackend:
    provider = "gonka"
    model = "gonka-test"

    def generate(self, messages, system_prompt=None, temperature=None, max_tokens=None, timeout=None, metadata=None, *, stream=False, on_token=None):
        return LLMResponse(
            text="backend answer",
            model=self.model,
            provider=self.provider,
            latency_ms=12.5,
        )


def test_resonance_agent_uses_backend_contract():
    agent = ResonanceAgent(anchor=[], llm_backend=FakeBackend(), orientation="test")

    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["final_output"] == "backend answer"
    assert result["llm_provider"] == "gonka"
    assert result["llm_model"] == "gonka-test"
    assert result["llm_latency_ms"] == 12.5
    assert result["llm_fallback_used"] is False
