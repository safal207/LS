from __future__ import annotations

from codex.causal_memory.engine import AdaptiveEngine
from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.store import MemoryStore


def test_explain_model_outcome_returns_ranked_causes(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    graph = CausalGraph()
    graph.add_edge("ram<8gb", "failure:model-a", weight=2.5)
    graph.add_edge("vram<4gb", "failure:model-a", weight=1.0)
    engine = AdaptiveEngine(store, graph)

    causes = engine.explain_model_outcome("model-a", "failure", {"ram_gb": 4, "vram_gb": 2})

    assert causes[0][0] == "ram<8gb"
    assert causes[0][1] == 2.5
