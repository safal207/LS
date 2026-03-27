import sys
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.path_selector import PathSelector
from graph.route_stats import RouteStats, RouteStatsStore
from graph.trail_updater import PathExecutionRecord, TrailUpdater


def test_trail_update_increases_pheromone_on_good_result(tmp_path):
    store = RouteStatsStore(tmp_path / "routes.json")
    updater = TrailUpdater(store, decay=0.95)
    record = PathExecutionRecord(
        route_key="full_run>local",
        question_text="Почему вы выбрали этот стек?",
        graph_mode="full_run",
        selected_backend="local",
        quality={"overall": 0.9, "relevance": 0.8, "thread_relevance": 0.8, "coherence": 0.9, "hallucination_risk": 0.1},
        latency_ms=5000,
    )

    route, reward = updater.update(record)

    assert reward > 0
    assert route.pheromone_weight > 0
    assert route.runs == 1


def test_trail_update_applies_decay(tmp_path):
    store = RouteStatsStore(tmp_path / "routes.json")
    store.save_route(RouteStats(route_key="full_run>local", pheromone_weight=1.0, runs=1, successes=1))
    updater = TrailUpdater(store, decay=0.5)
    record = PathExecutionRecord(
        route_key="full_run>local",
        question_text="Почему вы выбрали этот стек?",
        graph_mode="full_run",
        selected_backend="local",
        quality={"overall": 0.0, "relevance": 0.0, "thread_relevance": 0.0, "coherence": 0.0, "hallucination_risk": 1.0},
        latency_ms=30000,
    )

    route, _ = updater.update(record)

    assert route.pheromone_weight < 1.0


def test_path_selector_chooses_best_route_by_weight(tmp_path):
    store = RouteStatsStore(tmp_path / "routes.json")
    store.save_route(RouteStats(route_key="full_run>local", pheromone_weight=0.2, runs=3))
    store.save_route(RouteStats(route_key="full_run>gonka", pheromone_weight=0.8, runs=3))
    selector = PathSelector(store, exploration_rate=0.0)

    decision = selector.choose_route(
        graph_mode="full_run",
        available_backends=["local", "gonka"],
        default_backend="local",
    )

    assert decision.route_key == "full_run>gonka"
    assert decision.selected_backend == "gonka"


def test_path_selector_can_explore_alternative_route(tmp_path):
    store = RouteStatsStore(tmp_path / "routes.json")
    store.save_route(RouteStats(route_key="full_run>local", pheromone_weight=0.2, runs=3))
    store.save_route(RouteStats(route_key="full_run>gonka", pheromone_weight=0.8, runs=3))
    selector = PathSelector(store, exploration_rate=1.0, rng=random.Random(1))

    decision = selector.choose_route(
        graph_mode="full_run",
        available_backends=["local", "gonka"],
        default_backend="local",
    )

    assert decision.exploration_used is True
    assert decision.selected_backend in {"local", "gonka"}


def test_path_selector_prefers_default_cooperative_route_when_full_coalition_available(tmp_path):
    store = RouteStatsStore(tmp_path / "routes.json")
    selector = PathSelector(store, exploration_rate=0.0)

    decision = selector.choose_route(
        graph_mode="full_run",
        available_backends=["local", "gonka", "mimo"],
        default_backend="local",
    )

    assert decision.route_key == "full_run>local>gonka>mimo"
    assert decision.selected_backend == "cooperative"
