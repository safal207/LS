from __future__ import annotations

from codex.causal_memory.engine import AdaptiveEngine
from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.store import MemoryStore


def test_recommend_strategy_conservative_when_risk_high(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    graph = CausalGraph()
    graph.add_edge("ram<8gb", "failure:model-a", weight=2.0)
    engine = AdaptiveEngine(store, graph)

    strategy = engine.recommend_strategy(["model-a"], {"ram_gb": 4})

    assert strategy == "conservative"
