from __future__ import annotations

from codex.causal_memory.engine import AdaptiveEngine
from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.store import MemoryStore


def test_summarize_context_reports_state_outcomes_and_risks(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory.jsonl")
    graph = CausalGraph()
    graph.add_edge("ram<8gb", "failure:model-a", weight=2.0)
    graph.add_edge("ram<8gb", "success:model-b", weight=1.0)
    engine = AdaptiveEngine(store, graph)

    summary = engine.summarize_context(["model-a", "model-b"], {"ram_gb": 4}, top_k=2)

    assert summary["predicted_state"] == "uncertain"
    assert summary["top_outcomes"][0][0] == "failure:model-a"
    assert summary["model_risks"]["model-a"] == 0.4
