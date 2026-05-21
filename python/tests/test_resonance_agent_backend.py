# -*- coding: utf-8 -*-
# ruff: noqa: E402
import sys
from pathlib import Path
import tempfile
import json

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from modules.agent.resonance_agent import ResonanceAgent
from modules.agent.alignment_guidance import (
    get_alignment_guidance_metrics,
    reset_alignment_guidance_metrics,
)
from modules.llm.backends.base import LLMResponse
from modules.network.models import NetworkExecutionPlan
from graph.runtime import GraphRuntimeDecision
from graph.route_stats import RouteStatsStore


class FakeBackend:
    def __init__(self, provider="gonka", model="gonka-test", text="backend answer"):
        self.provider = provider
        self.model = model
        self.text = text

    def generate(
        self,
        messages,
        system_prompt=None,
        temperature=None,
        max_tokens=None,
        timeout=None,
        metadata=None,
        *,
        stream=False,
        on_token=None,
    ):
        return LLMResponse(
            text=self.text,
            model=self.model,
            provider=self.provider,
            latency_ms=12.5,
        )


class CapturingBackend(FakeBackend):
    def __init__(self, provider="local", model="local-test", text="backend answer"):
        super().__init__(provider=provider, model=model, text=text)
        self.last_system_prompt = ""

    def generate(self, *args, **kwargs):
        self.last_system_prompt = str(kwargs.get("system_prompt") or "")
        return super().generate(*args, **kwargs)


def _make_control_center_class(plan: NetworkExecutionPlan):
    class FakeControlCenter:
        def __init__(self, *args, **kwargs):
            pass

        def create_plan(self, item, *, thread_context=None, intent=None, why_tag=None):
            return plan

    return FakeControlCenter


def test_resonance_agent_uses_backend_contract():
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(),
        graph_runtime=FakeGraphRuntimeFullRun(),
        orientation="test",
    )

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

    def remember_success(
        self,
        item,
        *,
        answer_text,
        thread_context=None,
        answer_quality=None,
        contributors=None,
    ):
        return None

    def inject_resonance_hints(self, item, *, thread_context=None, top_k=3):
        raise AssertionError("inject_resonance_hints should not be called in reuse mode")


class FakeGraphRuntimeFullRun:
    def __init__(self):
        self.inject_thread_context = None
        self.remember_thread_context = None

    def process(self, item, thread_context=None):
        return GraphRuntimeDecision(
            mode="full_run",
            matched_case_id=None,
            similarity=0.0,
            prior_answer=None,
            prior_case=None,
            reason="no-similar-case",
        )

    def remember_success(
        self,
        item,
        *,
        answer_text,
        thread_context=None,
        answer_quality=None,
        contributors=None,
    ):
        self.remember_thread_context = thread_context
        return None

    def inject_resonance_hints(self, item, *, thread_context=None, top_k=3):
        self.inject_thread_context = thread_context
        item["_resonance_hints"] = [
            {
                "intent": "architecture",
                "why": "compare trade-offs",
                "route_key": "full_run>local",
                "causal_path": "intent_detected:architecture→intent_attached",
                "answer_pattern": "Сначала сравни варианты, потом выбери компромисс.",
                "resonance_score": 0.82,
                "alignment_score": 0.79,
            }
        ]
        return item["_resonance_hints"]


class FakeRelationalStore:
    def __init__(self):
        self.snapshots = []

    def store_relational_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        return snapshot


class FakeGraphRuntimeWithRelational(FakeGraphRuntimeFullRun):
    def __init__(self):
        super().__init__()
        self.store = FakeRelationalStore()

    def remember_relational_snapshot(self, snapshot):
        return self.store.store_relational_snapshot(snapshot)


class FakeGraphRuntimeFacadeOnly(FakeGraphRuntimeFullRun):
    def __init__(self):
        super().__init__()
        self.snapshots = []

    def remember_relational_snapshot(self, snapshot):
        self.snapshots.append(snapshot)
        return snapshot


class CapturingControlCenter:
    def __init__(self, plan: NetworkExecutionPlan):
        self.plan = plan
        self.thread_context = None

    def create_plan(self, item, *, thread_context=None, intent=None, why_tag=None):
        self.thread_context = thread_context
        return self.plan


def _full_run_plan() -> NetworkExecutionPlan:
    return NetworkExecutionPlan(
        mode="full_run",
        route_key="full_run>local",
        coalition_id=None,
        derived_module_id=None,
        memory_case_id=None,
        reason="test-full-run",
        confidence=0.9,
        graph_decision={"mode": "full_run"},
        available_backends=["local"],
    )


class FakeRouter:
    def __init__(self):
        self.primary = "local"
        self.fallback_chain = ["gonka", "mimo"]
        self.backends = {
            "local": FakeBackend(
                provider="local", model="local-test", text="draft answer"
            ),
            "gonka": FakeBackend(
                provider="gonka", model="gonka-test", text="critique answer"
            ),
            "mimo": FakeBackend(
                provider="mimo", model="mimo-test", text="compressed answer"
            ),
        }

    def generate(self, *args, **kwargs):
        return self.backends[self.primary].generate(*args, **kwargs)


def test_resonance_agent_can_reuse_graph_answer_without_llm_call():
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(),
        graph_runtime=FakeGraphRuntime(),
        orientation="test",
    )

    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["final_output"] == "cached answer"
    assert result["llm_provider"] == "graph_reuse"
    assert result["graph_mode"] == "reuse"
    assert result["was_reused"] is True


def test_resonance_agent_process_text_full_run_injects_hints_into_prompt():
    backend = CapturingBackend(provider="local", model="local-test", text="ok")
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=backend,
        graph_runtime=FakeGraphRuntimeFullRun(),
        orientation="test",
    )

    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["graph_mode"] == "full_run"
    assert "Слабые подсказки из resonance-memory" in backend.last_system_prompt
    assert "intent=architecture" in backend.last_system_prompt


def test_resonance_agent_does_not_fallback_to_orientation_for_thread_context():
    backend = CapturingBackend(provider="local", model="local-test", text="ok")
    graph_runtime = FakeGraphRuntimeFullRun()
    plan = _full_run_plan()
    control_center = CapturingControlCenter(plan)
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=backend,
        graph_runtime=graph_runtime,
        orientation="session-orientation",
    )
    agent._control_center = control_center

    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["graph_mode"] == "full_run"
    assert control_center.thread_context is None
    assert graph_runtime.inject_thread_context is None
    assert graph_runtime.remember_thread_context is None


def test_resonance_agent_passes_explicit_thread_context_to_runtime_components():
    backend = CapturingBackend(provider="local", model="local-test", text="ok")
    graph_runtime = FakeGraphRuntimeFullRun()
    plan = _full_run_plan()
    control_center = CapturingControlCenter(plan)
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=backend,
        graph_runtime=graph_runtime,
        orientation="session-orientation",
    )
    agent._control_center = control_center

    result = agent.process_item(
        {
            "text": "Почему вы выбрали этот стек?",
            "thread_context": "candidate-42/thread-a",
        }
    )

    assert result["graph_mode"] == "full_run"
    assert control_center.thread_context == "candidate-42/thread-a"
    assert graph_runtime.inject_thread_context == "candidate-42/thread-a"
    assert graph_runtime.remember_thread_context == "candidate-42/thread-a"


def test_resonance_agent_updates_trail_stats_after_answer(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        route_store = RouteStatsStore(Path(tmpdir) / "routes.json")
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", True)
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_TRAIL_STORE_PATH",
            str(Path(tmpdir) / "routes.json"),
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_TRAIL_EXPLORATION_RATE", 0.0
        )
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_DECAY", 0.95)

        agent = ResonanceAgent(
            anchor=[],
            llm_backend=FakeBackend(),
            graph_runtime=FakeGraphRuntimeFullRun(),
            orientation="test",
        )
        result = agent.process_text("Почему вы выбрали этот стек?")

        stats = route_store.get_route("full_run")
        assert result["trail_updated"] is True
        assert result["route_key"] == "full_run"
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

        agent = ResonanceAgent(
            anchor=[],
            llm_backend=FakeRouter(),
            graph_runtime=FakeGraphRuntimeFullRun(),
            orientation="test",
        )
        agent._path_selector = FixedSelector()
        result = agent.process_text("Почему вы выбрали этот стек?")

        assert result["cooperative_used"] is True
        assert result["cooperative_route_key"] == "full_run>local>gonka>mimo"
        assert isinstance(result["cooperative_participants"], list)


def test_resonance_agent_reroutes_from_relation_memory(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
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

        class FakeRelationalSnapshot:
            def to_dict(self):
                return {
                    "field_id": "field-001",
                    "timestamp": "2026-04-10T10:00:00Z",
                    "tension_score": 0.82,
                    "alignment_score": 0.22,
                    "dominant_signal": "tension",
                }

        class FakeRelationalAnalyzer:
            def analyze(self, **kwargs):
                return FakeRelationalSnapshot()

        class FakeScorer:
            def process(self, item):
                item["_resonance_score"] = 0.2
                return item

        relation_memory_dir = Path(tmpdir) / "relation-memory"
        relation_memory_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(2):
            (relation_memory_dir / f"seed-{idx}.json").write_text(
                json.dumps(
                    {
                        "cycle_id": f"seed-{idx}",
                        "pattern_key": "repair:tension:low",
                        "incident_published": True,
                        "review_decision": "rejected",
                    }
                ),
                encoding="utf-8",
            )

        agent = ResonanceAgent(
            anchor=[],
            llm_backend=FakeRouter(),
            graph_runtime=FakeGraphRuntimeFullRun(),
            orientation="test",
        )
        agent._path_selector = FixedSelector()
        agent._relational_analyzer = FakeRelationalAnalyzer()
        agent._scorer = FakeScorer()
        agent._relation_memory_dir = relation_memory_dir

        result = agent.process_text("Handle the operator request carefully.")

        assert result["route_key"] == "full_run>local"
        assert result["route_strategy"] == "freeze_and_escalate"
        assert result["route_memory_adjusted"] is True
        assert result["route_memory_match_count"] == 2
        assert "relation-memory-evidence-first" in str(result["route_reason"])
        assert result["llm_provider"] == "local"


def test_resonance_agent_updates_coalition_registry(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_COALITION_ENABLED", True
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_COALITION_STORE_PATH",
            str(Path(tmpdir) / "coalitions.json"),
        )

        plan = NetworkExecutionPlan(
            mode="full_run",
            route_key="full_run>local>gonka>mimo",
            coalition_id="full_run-local-gonka-mimo",
            derived_module_id=None,
            memory_case_id=None,
            reason="fixed-test-route",
            confidence=0.7,
            selected_backend="cooperative",
            graph_decision=FakeGraphRuntimeFullRun().process({}).to_dict(),
            path_decision={
                "route_key": "full_run>local>gonka>mimo",
                "reason": "fixed-test-route",
                "exploration_used": False,
                "pheromone_weight": 0.0,
                "selected_backend": "cooperative",
            },
            available_backends=["local", "gonka", "mimo"],
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent._NetworkControlCenter",
            _make_control_center_class(plan),
        )
        agent = ResonanceAgent(
            anchor=[],
            llm_backend=FakeRouter(),
            graph_runtime=FakeGraphRuntimeFullRun(),
            orientation="test",
        )
        result = agent.process_text(
            "??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ?????????? ???? ??????? ?????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ??????? ??????? ?????? ??????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????"
        )

        assert result["coalition_used"] is True
        assert result["coalition_route_key"] == "full_run>local>gonka>mimo"
        assert result["coalition_trust_score"] is not None


def test_resonance_agent_uses_derived_module_when_available(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_COALITION_ENABLED", False
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_ENABLED", True
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_STORE_PATH",
            str(Path(tmpdir) / "derived.json"),
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_QUALITY", 0.7
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_TRUST", 0.6
        )

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
        module = registry.get_module("derived-unknown-evaluate-reasoning-local")
        assert module is not None

        plan = NetworkExecutionPlan(
            mode="full_run",
            route_key=f"derived>{module.module_id}",
            coalition_id=module.parent_coalition_id,
            derived_module_id=module.module_id,
            memory_case_id=None,
            reason="derived-module",
            confidence=module.trust_score,
            selected_backend=module.preferred_backend,
            graph_decision=FakeGraphRuntimeFullRun().process({}).to_dict(),
            derived_module=module.to_dict(),
            available_backends=["local", "gonka", "mimo"],
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent._NetworkControlCenter",
            _make_control_center_class(plan),
        )
        agent = ResonanceAgent(
            anchor=[],
            llm_backend=FakeRouter(),
            graph_runtime=FakeGraphRuntimeFullRun(),
            orientation="test",
        )
        result = agent.process_text(
            "??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ?????????? ???? ??????? ?????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ??????? ??????? ?????? ??????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????"
        )

        assert result["derived_module_used"] is True
        assert result["llm_provider"] == "derived_module"
        assert result["derived_module_backend"] == "local"


def test_resonance_agent_creates_derived_module_from_successful_cooperative_run(
    monkeypatch,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_COALITION_ENABLED", True
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_COALITION_STORE_PATH",
            str(Path(tmpdir) / "coalitions.json"),
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_ENABLED", True
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_STORE_PATH",
            str(Path(tmpdir) / "derived.json"),
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_QUALITY", 0.6
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_TRUST", 0.5
        )

        plan = NetworkExecutionPlan(
            mode="full_run",
            route_key="full_run>local>gonka>mimo",
            coalition_id="full_run-local-gonka-mimo",
            derived_module_id=None,
            memory_case_id=None,
            reason="fixed-test-route",
            confidence=0.7,
            selected_backend="cooperative",
            graph_decision=FakeGraphRuntimeFullRun().process({}).to_dict(),
            path_decision={
                "route_key": "full_run>local>gonka>mimo",
                "reason": "fixed-test-route",
                "exploration_used": False,
                "pheromone_weight": 0.0,
                "selected_backend": "cooperative",
            },
            available_backends=["local", "gonka", "mimo"],
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent._NetworkControlCenter",
            _make_control_center_class(plan),
        )
        agent = ResonanceAgent(
            anchor=[],
            llm_backend=FakeRouter(),
            graph_runtime=FakeGraphRuntimeFullRun(),
            orientation="test",
        )
        result = agent.process_text(
            "??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ?????????? ???? ??????? ?????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ??????? ??????? ?????? ??????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????"
        )

        assert result["derived_module_used"] is True
        assert result["derived_module_id"] is not None


def test_resonance_agent_runs_care_cycle_for_derived_module(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr("modules.agent.resonance_agent.GRAPH_TRAIL_ENABLED", False)
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_COALITION_ENABLED", False
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_ENABLED", True
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_STORE_PATH",
            str(Path(tmpdir) / "derived.json"),
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_QUALITY", 0.7
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_DERIVED_MODULE_MIN_TRUST", 0.6
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_CARE_CYCLES_ENABLED", True
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_CARE_CYCLES_MIN_QUALITY", 0.68
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_CARE_CYCLES_MIN_TRUST", 0.58
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent.GRAPH_CARE_CYCLES_RETIRE_TRUST", 0.35
        )

        from graph.derived_module_registry import DerivedModuleRegistry

        registry = DerivedModuleRegistry(Path(tmpdir) / "derived.json")
        registry.create_or_update_from_success(
            parent_coalition_id="coalition-local-gonka-mimo",
            source_route_key="full_run>local>gonka>mimo",
            domain="generic",
            task_type="generic",
            preferred_backend="local",
            policy_type="prompt_policy",
            policy_text="Use concise answers and do not invent facts.",
            quality_score=0.84,
        )
        module = registry.get_module("derived-generic-generic-local")
        assert module is not None

        plan = NetworkExecutionPlan(
            mode="full_run",
            route_key=f"derived>{module.module_id}",
            coalition_id=module.parent_coalition_id,
            derived_module_id=module.module_id,
            memory_case_id=None,
            reason="derived-module",
            confidence=module.trust_score,
            selected_backend=module.preferred_backend,
            graph_decision=FakeGraphRuntimeFullRun().process({}).to_dict(),
            derived_module=module.to_dict(),
            available_backends=["local", "gonka", "mimo"],
        )
        monkeypatch.setattr(
            "modules.agent.resonance_agent._NetworkControlCenter",
            _make_control_center_class(plan),
        )
        agent = ResonanceAgent(
            anchor=[],
            llm_backend=FakeRouter(),
            graph_runtime=FakeGraphRuntimeFullRun(),
            orientation="test",
        )
        result = agent.process_text(
            "??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ?????????? ???? ??????? ?????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ??????? ??????? ?????? ??????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????"
        )

        assert result["care_cycle_used"] is True
        assert result["care_cycle_action"] in {"promote", "keep", "demote", "retire"}
        assert result["care_cycle_state"] in {"active", "review", "retired"}


def test_resonance_agent_exposes_adequacy_metadata(monkeypatch):
    class FakeObserver:
        def evaluate(self):
            return type(
                "Observer",
                (),
                {
                    "to_dict": lambda self_: {
                        "status": "watch",
                        "summary": {"trend": "watch"},
                        "adequacy": {
                            "status": "watch",
                            "risks": ["route dominance risk"],
                            "recommendations": ["increase exploration"],
                        },
                        "retrospective": {},
                        "trajectory": {},
                    }
                },
            )()

    monkeypatch.setattr("modules.agent.resonance_agent._NetworkObserver", FakeObserver)
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(),
        graph_runtime=FakeGraphRuntimeFullRun(),
        orientation="test",
    )
    result = agent.process_text("??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ?????????? ???? ??????? ?????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ??????? ??????? ?????? ??????? ?????? ??????? ?????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????????? ???????????? ???????????? ??????????? ??????? ???????")

    assert result["adequacy_status"] == "watch"
    assert "route dominance risk" in (result["adequacy_risks"] or [])


def test_resonance_agent_exposes_observer_metadata(monkeypatch):
    class FakeObserver:
        def evaluate(self):
            return type(
                "Observer",
                (),
                {
                    "to_dict": lambda self_: {
                        "status": "watch",
                        "summary": {"trend": "degrading", "stale_modules": 2},
                        "adequacy": {
                            "status": "watch",
                            "risks": ["route dominance risk"],
                            "recommendations": ["increase exploration"],
                        },
                        "retrospective": {"weak_routes": ["full_run>cloud"]},
                        "trajectory": {"record": {"trend": "degrading"}},
                    }
                },
            )()

    monkeypatch.setattr("modules.agent.resonance_agent._NetworkObserver", FakeObserver)
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(),
        graph_runtime=FakeGraphRuntimeFullRun(),
        orientation="test",
    )
    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["observer_status"] == "watch"
    assert result["observer_summary"]["trend"] == "degrading"


def test_resonance_agent_uses_network_control_center(monkeypatch):
    class FakeControlCenter:
        def __init__(self, *args, **kwargs):
            pass

        def create_plan(self, item, *, thread_context=None, intent=None, why_tag=None):
            return type(
                "Plan",
                (),
                {
                    "to_dict": lambda self_: {
                        "mode": "full_run",
                        "route_key": "full_run>local",
                        "reason": "control-center-test",
                        "confidence": 0.7,
                        "need_profile": {
                            "priority": "balanced",
                            "route_bias": "adaptive",
                        },
                        "goal_vector": {
                            "style": "structured",
                            "strategy_bias": "cooperative_reasoning",
                        },
                    },
                    "graph_decision": None,
                    "derived_module": None,
                    "path_decision": None,
                    "need_profile": {"priority": "balanced", "route_bias": "adaptive"},
                    "goal_vector": {
                        "style": "structured",
                        "strategy_bias": "cooperative_reasoning",
                    },
                    "adequacy_report": {
                        "status": "stable",
                        "risks": [],
                        "recommendations": [],
                    },
                    "observer_report": {
                        "status": "stable",
                        "summary": {"trend": "stable"},
                    },
                    "available_backends": ["local"],
                },
            )()

    monkeypatch.setattr(
        "modules.agent.resonance_agent._NetworkControlCenter", FakeControlCenter
    )
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        graph_runtime=FakeGraphRuntimeFullRun(),
        orientation="test",
    )
    result = agent.process_text("Почему вы выбрали этот стек?")

    assert result["orientation_reason"] == "control-center-test"
    assert result["observer_status"] == "stable"
    assert result["need_priority"] == "balanced"
    assert result["goal_style"] == "structured"


def test_resonance_agent_system_prompt_uses_goal_vector_guidance() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "text": "Почему вы выбрали этот стек?",
        "_network_plan": {
            "need_profile": {
                "priority": "safe_correction",
                "route_bias": "explore_and_verify",
                "compute_budget": 0.9,
            },
            "goal_vector": {
                "style": "careful",
                "strategy_bias": "verify_first",
                "target_relevance": 0.8,
                "target_thread_alignment": 0.8,
                "target_hallucination_max": 0.15,
                "target_latency_ms": 12000.0,
            },
        },
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
    }

    system_prompt = agent._build_system_prompt(item)

    assert "Профиль потребности сети" in system_prompt
    assert "Целевой профиль ответа" in system_prompt
    assert "Отвечай осторожно" in system_prompt
    assert "точность и проверяемость важнее скорости" in system_prompt


def test_resonance_agent_system_prompt_includes_resonance_hints_when_present() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "text": "Почему вы выбрали этот стек?",
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_resonance_hints": [
            {
                "intent": "architecture",
                "why": "compare trade-offs",
                "route_key": "full_run>local",
                "causal_path": "intent_detected:architecture→intent_attached",
                "answer_pattern": "Сначала сравни варианты, потом выбери компромисс.",
                "resonance_score": 0.82,
                "alignment_score": 0.79,
            }
        ],
    }

    system_prompt = agent._build_system_prompt(item)

    assert "Слабые подсказки из resonance-memory" in system_prompt
    assert "intent=architecture" in system_prompt
    assert "route=full_run>local" in system_prompt


def test_resonance_agent_system_prompt_includes_relational_soft_guidance() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "text": "Почему вы выбрали этот стек?",
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_relational_field": {
            "tension_score": 0.81,
            "alignment_score": 0.22,
        },
    }

    system_prompt = agent._build_system_prompt(item)

    assert "В поле есть напряжение" in system_prompt
    assert "Не дави на решение сразу" in system_prompt


def test_resonance_agent_system_prompt_skips_alignment_guidance_when_safe() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "text": "Почему вы выбрали этот стек?",
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_alignment_report": {
            "alignment_score": 0.81,
            "tension_score": 0.18,
            "mismatch_reasons": [],
            "pairwise_hotspots": [],
            "requires_softening": False,
            "requires_clarification": False,
            "requires_grounding": False,
        },
    }

    system_prompt = agent._build_system_prompt(item)
    assert "Alignment guidance (soft behavioral steering)" not in system_prompt


def test_resonance_agent_system_prompt_adds_alignment_guidance_from_hotspot() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "text": "Почему вы выбрали этот стек?",
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_alignment_report": {
            "pairwise_hotspots": [{"participants": ["a", "b"], "tension": 0.81}],
            "mismatch_reasons": [],
            "requires_softening": True,
        },
    }

    system_prompt = agent._build_system_prompt(item)
    assert "Alignment guidance (soft behavioral steering)" in system_prompt
    assert "Сначала признай напряжение" in system_prompt


def test_resonance_agent_system_prompt_adds_soft_alignment_guidance_from_mismatch() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "text": "Почему вы выбрали этот стек?",
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_alignment_report": {
            "pairwise_hotspots": [],
            "mismatch_reasons": ["why_mismatch"],
            "requires_clarification": True,
        },
    }

    system_prompt = agent._build_system_prompt(item)
    assert "Alignment guidance (soft behavioral steering)" in system_prompt
    assert "mismatch контекста/целей" in system_prompt
    assert "Сначала синхронизируй позиции участников" in system_prompt


def test_resonance_agent_alignment_guidance_preserves_existing_prompt_hints() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "text": "Почему вы выбрали этот стек?",
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {"route_key": "full_run>local"},
        "_resonance_score": 0.5,
        "_resonance_hints": [
            {
                "intent": "architecture",
                "why": "compare trade-offs",
                "route_key": "full_run>local",
                "causal_path": "intent_detected:architecture→intent_attached",
                "answer_pattern": "Сначала сравни варианты, потом выбери компромисс.",
                "resonance_score": 0.82,
                "alignment_score": 0.79,
            }
        ],
        "_network_plan": {
            "goal_vector": {
                "style": "structured",
                "strategy_bias": "cooperative_reasoning",
                "target_relevance": 0.8,
                "target_thread_alignment": 0.8,
                "target_hallucination_max": 0.15,
                "target_latency_ms": 12000.0,
            }
        },
        "_alignment_report": {
            "pairwise_hotspots": [{"participants": ["a", "b"], "tension": 0.81}],
            "mismatch_reasons": ["why_mismatch"],
            "requires_softening": True,
            "requires_clarification": True,
        },
    }

    system_prompt = agent._build_system_prompt(item)
    assert "Слабые подсказки из resonance-memory" in system_prompt
    assert "Целевой профиль ответа" in system_prompt
    assert "Маршрут решения выбран по истории успешных путей" in system_prompt
    assert "Alignment guidance (soft behavioral steering)" in system_prompt


def test_resonance_agent_alignment_guidance_is_advisory_for_graph_mode_and_route_key() -> None:
    backend = FakeBackend(provider="local", model="local-test", text="ok")
    runtime = FakeGraphRuntimeFullRun()
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=backend,
        graph_runtime=runtime,
        orientation="test",
    )

    result = agent.process_item(
        {
            "text": "Почему вы выбрали этот стек?",
            "participants": [
                {"participant_id": "candidate", "intent": "defend", "why": "explain"},
                {"participant_id": "counterparty", "intent": "challenge", "why": "verify"},
            ],
        }
    )

    assert result["graph_mode"] == "full_run"
    assert result["route_key"] == "full_run>local"
    assert result["was_reused"] is False


def test_resonance_agent_alignment_guidance_metrics_tracking() -> None:
    reset_alignment_guidance_metrics()
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )

    safe_item = {
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_alignment_report": {
            "pairwise_hotspots": [],
            "mismatch_reasons": [],
            "requires_softening": False,
            "requires_clarification": False,
            "requires_grounding": False,
        },
    }
    hotspot_item = {
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_alignment_report": {
            "pairwise_hotspots": [{"participants": ["a", "b"], "tension": 0.81}],
            "mismatch_reasons": [],
            "requires_softening": True,
        },
    }
    mismatch_item = {
        "_copilot_output": {},
        "_graph_runtime": {},
        "_path_selection": {},
        "_resonance_score": 0.5,
        "_alignment_report": {
            "pairwise_hotspots": [],
            "mismatch_reasons": ["why_mismatch"],
            "requires_clarification": True,
        },
    }

    agent._build_system_prompt(safe_item)
    agent._build_system_prompt(hotspot_item)
    agent._build_system_prompt(mismatch_item)

    metrics = get_alignment_guidance_metrics()
    assert metrics["calls_total"] == 3
    assert metrics["nonempty_total"] == 2
    assert metrics["average_lines"] > 0
    assert metrics["hotspot_guidance_total"] == 1
    assert metrics["mismatch_guidance_total"] == 1


def test_resonance_agent_records_relational_snapshot_as_observation() -> None:
    backend = CapturingBackend(provider="local", model="local-test", text="ok")
    graph_runtime = FakeGraphRuntimeWithRelational()
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=backend,
        graph_runtime=graph_runtime,
        orientation="test",
    )

    agent.process_text("Ты опять никогда не слушаешь, это невозможно!")

    assert graph_runtime.store.snapshots
    snapshot = graph_runtime.store.snapshots[0]
    assert snapshot.tension_score >= 0.3
    assert snapshot.interaction_scope == "human-human"


def test_resonance_agent_uses_runtime_relational_facade_without_store_attr() -> None:
    backend = CapturingBackend(provider="local", model="local-test", text="ok")
    graph_runtime = FakeGraphRuntimeFacadeOnly()
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=backend,
        graph_runtime=graph_runtime,
        orientation="test",
    )

    agent.process_text("Ты опять никогда не слушаешь, это невозможно!")

    assert graph_runtime.snapshots
    assert graph_runtime.snapshots[0].field_id


def test_resonance_agent_goal_alignment_score_rewards_matching_profile() -> None:
    agent = ResonanceAgent(
        anchor=[],
        llm_backend=FakeBackend(provider="local", model="local-test", text="ok"),
        orientation="test",
    )
    item = {
        "_network_plan": {
            "goal_vector": {
                "style": "careful",
                "strategy_bias": "verify_first",
                "target_relevance": 0.8,
                "target_thread_alignment": 0.8,
                "target_hallucination_max": 0.15,
                "target_latency_ms": 12000.0,
            }
        }
    }

    good = agent._goal_alignment_score(
        "Я выбрал этот стек, потому что он лучше подходил под задачу и команду, без лишних зависимостей.",
        item,
    )
    bad = agent._goal_alignment_score(
        "Мы ускорили всё на 300% и сэкономили 40% бюджета.", item
    )

    assert good > bad
    assert good <= 1.0
