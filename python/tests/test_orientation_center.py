# ruff: noqa: E402
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.path_selector import PathSelector
from graph.route_stats import RouteStatsStore
from graph.derived_module_registry import DerivedModuleRegistry
from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit
from network.orientation_center import OrientationCenter


class FakeGraphDecision:
    def __init__(
        self,
        mode="full_run",
        matched_case_id=None,
        similarity=0.0,
        prior_answer=None,
        prior_case=None,
        reason="no-match",
    ):
        self.mode = mode
        self.matched_case_id = matched_case_id
        self.similarity = similarity
        self.prior_answer = prior_answer
        self.prior_case = prior_case
        self.reason = reason

    def to_dict(self):
        return {
            "mode": self.mode,
            "matched_case_id": self.matched_case_id,
            "similarity": self.similarity,
            "prior_answer": self.prior_answer,
            "prior_case": self.prior_case,
            "reason": self.reason,
        }


class FakeGraphRuntime:
    def __init__(self, decision):
        self.decision = decision

    def process(self, item, thread_context=None):
        return self.decision


class FakeRouter:
    def __init__(self):
        self.primary = "local"
        self.backends = {"local": object(), "gonka": object(), "mimo": object()}


class FakeAdequacyCore:
    def __init__(self, status="stable", risks=None):
        self.status = status
        self.risks = risks or []

    def evaluate(self):
        return type(
            "Adequacy",
            (),
            {
                "to_dict": lambda self_: {
                    "status": self.status,
                    "risks": self.risks,
                    "recommendations": [],
                }
            },
        )()


class FakeObserverCore:
    def evaluate(self):
        return type(
            "Observer",
            (),
            {
                "to_dict": lambda self_: {
                    "status": "watch",
                    "summary": {"trend": "degrading", "stale_modules": 1},
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


def test_orientation_center_prefers_reuse():
    center = OrientationCenter(
        graph_runtime=FakeGraphRuntime(
            FakeGraphDecision(
                mode="reuse",
                matched_case_id="case-1",
                similarity=0.98,
                prior_answer="cached",
                reason="high-similarity",
            )
        ),
        llm_backend=FakeRouter(),
    )

    plan = center.decide(
        {"text": "Почему вы выбрали этот стек?"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert plan.mode == "reuse"
    assert plan.route_key == "reuse"
    assert plan.memory_case_id == "case-1"


def test_orientation_center_prefers_derived_module_when_available(tmp_path):
    derived = DerivedModuleRegistry(tmp_path / "derived.json")
    derived.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="technical_reasoning",
        task_type="evaluate_reasoning",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Use concise interview answers.",
        quality_score=0.84,
    )
    center = OrientationCenter(
        graph_runtime=FakeGraphRuntime(
            FakeGraphDecision(mode="full_run", reason="no-match")
        ),
        path_selector=PathSelector(
            RouteStatsStore(tmp_path / "routes.json"), exploration_rate=0.0
        ),
        derived_module_registry=derived,
        llm_backend=FakeRouter(),
        derived_min_quality=0.7,
        derived_min_trust=0.6,
    )

    plan = center.decide(
        {"text": "Почему вы выбрали этот стек?"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert plan.derived_module_id is not None
    assert plan.reason == "derived-module"
    assert plan.selected_backend == "local"


def test_orientation_center_blocks_derived_module_when_adequacy_intervenes(tmp_path):
    derived = DerivedModuleRegistry(tmp_path / "derived.json")
    derived.create_or_update_from_success(
        parent_coalition_id="coalition-local-gonka-mimo",
        source_route_key="full_run>local>gonka>mimo",
        domain="technical_reasoning",
        task_type="evaluate_reasoning",
        preferred_backend="local",
        policy_type="prompt_policy",
        policy_text="Use concise interview answers.",
        quality_score=0.84,
    )
    center = OrientationCenter(
        graph_runtime=FakeGraphRuntime(
            FakeGraphDecision(mode="full_run", reason="no-match")
        ),
        path_selector=PathSelector(
            RouteStatsStore(tmp_path / "routes.json"), exploration_rate=0.0
        ),
        derived_module_registry=derived,
        llm_backend=FakeRouter(),
        adequacy_core=FakeAdequacyCore(
            status="intervene", risks=["derived module drift"]
        ),
        derived_min_quality=0.7,
        derived_min_trust=0.6,
    )

    plan = center.decide(
        {"text": "Почему вы выбрали этот стек?"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert plan.derived_module_id is None
    assert plan.adequacy_report is not None
    assert plan.adequacy_report["status"] == "intervene"
    assert plan.route_key in {
        "full_run>local>gonka>mimo",
        "full_run>local",
        "full_run>gonka",
        "full_run>mimo",
    }


def test_orientation_center_surfaces_observer_report(tmp_path):
    center = OrientationCenter(
        graph_runtime=FakeGraphRuntime(
            FakeGraphDecision(mode="full_run", reason="no-match")
        ),
        path_selector=PathSelector(
            RouteStatsStore(tmp_path / "routes.json"), exploration_rate=0.0
        ),
        llm_backend=FakeRouter(),
        observer_core=FakeObserverCore(),
    )

    plan = center.decide(
        {"text": "Почему вы выбрали этот стек?"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
    )

    assert plan.observer_report is not None
    assert plan.observer_report["status"] == "watch"
    assert plan.adequacy_report["status"] == "watch"


def test_orientation_center_uses_goal_vector_for_route_choice(tmp_path):
    center = OrientationCenter(
        graph_runtime=FakeGraphRuntime(
            FakeGraphDecision(mode="full_run", reason="no-match")
        ),
        path_selector=PathSelector(
            RouteStatsStore(tmp_path / "routes.json"), exploration_rate=0.0
        ),
        llm_backend=FakeRouter(),
    )

    plan = center.decide(
        {"text": "Почему вы выбрали этот стек?"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
        goal_vector={"style": "structured", "strategy_bias": "cooperative_reasoning"},
    )

    assert plan.goal_vector is not None
    assert plan.route_key == "full_run>local>gonka>mimo"


def test_orientation_center_uses_resonance_memory_as_weak_signal(tmp_path):
    store = MemoryGraphStore(tmp_path / "cases.jsonl")
    store.store_resonance_unit(
        ResonanceKnowledgeUnit(
            source_question="Почему вы выбрали этот стек?",
            clean_question="Почему вы выбрали этот стек?",
            intent="technical_reasoning",
            why="evaluate_reasoning",
            resonance_score=0.9,
            alignment_score=0.8,
            metadata={"route_key": "full_run>local>gonka>mimo"},
        )
    )
    center = OrientationCenter(
        graph_runtime=FakeGraphRuntime(
            FakeGraphDecision(mode="full_run", reason="no-match")
        ),
        path_selector=PathSelector(
            RouteStatsStore(tmp_path / "routes.json"), exploration_rate=0.0
        ),
        llm_backend=FakeRouter(),
        memory_store=store,
    )

    plan = center.decide(
        {"text": "Почему вы выбрали этот стек?"},
        intent="technical_reasoning",
        why_tag="evaluate_reasoning",
        goal_vector={"style": "structured", "strategy_bias": "cooperative_reasoning"},
    )

    assert plan.route_key == "full_run>local>gonka>mimo"
    assert plan.reason.endswith("+resonance-memory")
    assert plan.resonance_signal is not None
    assert plan.resonance_signal["count"] == 1
    assert plan.confidence > 0.0
