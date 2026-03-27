import sys
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modules.agent.resonance_agent import ResonanceAgent
from modules.llm.backends.base import LLMResponse
from graph.runtime import GraphRuntimeDecision
from graph.route_stats import RouteStatsStore


class FakeBackend:
    def __init__(self, provider="gonka", model="gonka-test", text="backend answer"):
        self.provider = provider
        self.model = model
        self.text = text

    def generate(self, messages, system_prompt=None, temperature=None, max_tokens=None, timeout=None, metadata=None, *, stream=False, on_token=None):
        return LLMResponse(
            text=self.text,
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


class FakeGraphRuntimeFullRun:
    def process(self, item, thread_context=None):
        return GraphRuntimeDecision(
            mode="full_run",
            matched_case_id=None,
            similarity=0.0,
            prior_answer=None,
            prior_case=None,
            reason="no-similar-case",
        )

    def remember_success(self, item, *, answer_text, thread_context=None, answer_quality=None, contributors=None):
        return None


class FakeRouter:
    def __init__(self):
        self.primary = "local"
        self.fallback_chain = ["gonka", "mimo"]
        self.backends = {
            "local": FakeBackend(provider="local", model="local-test", text="draft answer"),
            "gonka": FakeBackend(provider="gonka", model="gonka-test", text="critique answer"),
            "mimo": FakeBackend(provider="mimo", model="mimo-test", text="compressed answer"),
        }

    def generate(self, *args, **kwargs):
        return self.backends[self.primary].generate(*args, **kwargs)


def test_resonance_agent_can_reuse_graph_answer_without_llm_call():
    agent = ResonanceAgent(anchor=[], llm_backend=FakeBackend(), graph_runtime=FakeGraphRuntime(), orientation="test")

    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["final_output"] == "cached answer"
    assert result["llm_provider"] == "graph_reuse"
    assert result["graph_mode"] == "reuse"
    assert result["was_reused"] is True


def test_resonance_agent_updates_trail_stats_after_answer(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        route_store = RouteStatsStore(Path(tmpdir) / "routes.json")
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", True)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_STORE_PATH", str(Path(tmpdir) / "routes.json"))
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_EXPLORATION_RATE", 0.0)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_DECAY", 0.95)

        agent = ResonanceAgent(anchor=[], llm_backend=FakeBackend(), graph_runtime=FakeGraphRuntimeFullRun(), orientation="test")
        result = agent.process_text("Почему вы выбрали этот стек?")

        stats = route_store.get_route("full_run>gonka")
        assert result["trail_updated"] is True
        assert result["route_key"] == "full_run>gonka"
        assert stats is not None
        assert stats.runs >= 1


def test_resonance_agent_uses_cooperative_route_metadata(monkeypatch):
    with tempfile.TemporaryDirectory():
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)

        class FixedSelector:
            def choose_route(self, **kwargs):
                from graph.path_selector import PathSelectionDecision
                return PathSelectionDecision(
                    route_key="full_run>local>gonka>mimo",
                    reason="fixed-test-route",
                    exploration_used=False,
                    pheromone_weight=0.0,
                    selected_backend="cooperative",
                )

        agent = ResonanceAgent(anchor=[], llm_backend=FakeRouter(), graph_runtime=FakeGraphRuntimeFullRun(), orientation="test")
        agent._path_selector = FixedSelector()
        result = agent.process_text("Почему вы выбрали этот стек?")

        assert result["cooperative_used"] is True
        assert result["cooperative_route_key"] == "full_run>local>gonka>mimo"
        assert isinstance(result["cooperative_participants"], list)


def test_resonance_agent_updates_coalition_registry(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_COALITION_ENABLED", True)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_COALITION_STORE_PATH", str(Path(tmpdir) / "coalitions.json"))

        class FixedSelector:
            def choose_route(self, **kwargs):
                from graph.path_selector import PathSelectionDecision
                return PathSelectionDecision(
                    route_key="full_run>local>gonka>mimo",
                    reason="fixed-test-route",
                    exploration_used=False,
                    pheromone_weight=0.0,
                    selected_backend="cooperative",
                )

        agent = ResonanceAgent(anchor=[], llm_backend=FakeRouter(), graph_runtime=FakeGraphRuntimeFullRun(), orientation="test")
        agent._path_selector = FixedSelector()
        result = agent.process_text("Почему вы выбрали этот стек?")

        assert result["coalition_used"] is True
        assert result["coalition_route_key"] == "full_run>local>gonka>mimo"
        assert result["coalition_trust_score"] is not None


def test_resonance_agent_uses_derived_module_when_available(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_COALITION_ENABLED", False)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_ENABLED", True)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_STORE_PATH", str(Path(tmpdir) / "derived.json"))
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_QUALITY", 0.7)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_TRUST", 0.6)

        from graph.derived_module_registry import DerivedModuleRegistry

        registry = DerivedModuleRegistry(Path(tmpdir) / "derived.json")
        registry.create_or_update_from_success(
            parent_coalition_id="coalition-local-gonka-mimo",
            source_route_key="full_run>local>gonka>mimo",
            domain="unknown",
            task_type="evaluate_reasoning",
            preferred_backend="local",
            policy_type="prompt_policy",
            policy_text="Use concise answers and do not invent facts.",
            quality_score=0.84,
        )

        agent = ResonanceAgent(anchor=[], llm_backend=FakeRouter(), graph_runtime=FakeGraphRuntimeFullRun(), orientation="test")
        result = agent.process_text("Почему вы выбрали этот стек?")

        assert result["derived_module_used"] is True
        assert result["llm_provider"] == "derived_module"
        assert result["derived_module_backend"] == "local"


def test_resonance_agent_creates_derived_module_from_successful_cooperative_run(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_COALITION_ENABLED", True)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_COALITION_STORE_PATH", str(Path(tmpdir) / "coalitions.json"))
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_ENABLED", True)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_STORE_PATH", str(Path(tmpdir) / "derived.json"))
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_QUALITY", 0.6)
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_TRUST", 0.5)

        class FixedSelector:
            def choose_route(self, **kwargs):
                from graph.path_selector import PathSelectionDecision
                return PathSelectionDecision(
                    route_key="full_run>local>gonka>mimo",
                    reason="fixed-test-route",
                    exploration_used=False,
                    pheromone_weight=0.0,
                    selected_backend="cooperative",
                )

        agent = ResonanceAgent(anchor=[], llm_backend=FakeRouter(), graph_runtime=FakeGraphRuntimeFullRun(), orientation="test")
        agent._path_selector = FixedSelector()
        result = agent.process_text("Почему вы выбрали этот стек?")

        assert result["derived_module_used"] is True
        assert result["derived_module_id"] is not None
