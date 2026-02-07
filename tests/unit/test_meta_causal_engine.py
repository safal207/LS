from __future__ import annotations

from codex.causal_memory.engine import AdaptiveEngine
from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.store import MemoryStore


def test_forecast_model_risks_and_outcomes(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    graph = CausalGraph()
    graph.add_edge("ram<8gb", "failure:model-a", weight=3.0)
    graph.add_edge("ram<8gb", "success:model-b", weight=1.5)
    engine = AdaptiveEngine(store, graph)

    risks = engine.forecast_model_risks(["model-a", "model-b"], context={"ram_gb": 4})
    assert risks["model-a"] == 0.6
    assert risks["model-b"] == 0.0

    outcomes = engine.forecast_outcomes({"ram_gb": 4}, top_k=2)
    assert outcomes[0][0] == "failure:model-a"
    assert outcomes[0][1] == 3.0
