from __future__ import annotations

from codex.causal_memory.engine import AdaptiveEngine
from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.store import MemoryStore


def test_predict_system_state_prefers_uncertain_on_failure_bias(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    graph = CausalGraph()
    graph.add_edge("ram<8gb", "failure:model-a", weight=2.0)
    graph.add_edge("ram<8gb", "success:model-a", weight=1.0)
    engine = AdaptiveEngine(store, graph)

    state = engine.predict_system_state({"ram_gb": 4})

    assert state == "uncertain"
