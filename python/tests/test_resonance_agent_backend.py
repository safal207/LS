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
from graph.runtime import GraphRuntimeDecision


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


class FakeGraphRuntime:
    def process(self, item, thread_context=None):
        return GraphRuntimeDecision(
            mode="reuse",
            matched_case_id="case-1",
            similarity=1.0,
            prior_answer="cached answer",
            prior_case={"case_id": "case-1"},
            reason="high-similarity",
        )

    def remember_success(self, item, *, answer_text, thread_context=None, answer_quality=None, contributors=None):
        return None


def test_resonance_agent_can_reuse_graph_answer_without_llm_call():
    agent = ResonanceAgent(anchor=[], llm_backend=FakeBackend(), graph_runtime=FakeGraphRuntime(), orientation="test")

    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["final_output"] == "cached answer"
    assert result["llm_provider"] == "graph_reuse"
    assert result["graph_mode"] == "reuse"
    assert result["was_reused"] is True
