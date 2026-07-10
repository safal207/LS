from codex.causal_memory.graph import CausalGraph

def test_get_upstream_basic():
    graph = CausalGraph()
    graph.add_edge("cause1", "effect1", weight=1.0)

    upstream = graph.get_upstream("effect1")
    assert len(upstream) == 1
    assert upstream[0].cause == "cause1"
    assert upstream[0].effect == "effect1"
    assert upstream[0].weight == 1.0
    assert upstream[0].count == 1

def test_get_upstream_multiple_causes():
    graph = CausalGraph()
    graph.add_edge("cause1", "effect1", weight=0.8)
    graph.add_edge("cause2", "effect1", weight=0.6)
    graph.add_edge("cause1", "effect2", weight=1.0)

    upstream = graph.get_upstream("effect1")
    assert len(upstream) == 2
    causes = {edge.cause for edge in upstream}
    assert causes == {"cause1", "cause2"}
    for edge in upstream:
        assert edge.effect == "effect1"

def test_get_upstream_nonexistent_effect():
    graph = CausalGraph()
    graph.add_edge("cause1", "effect1", weight=1.0)

    upstream = graph.get_upstream("effect_none")
    assert upstream == []

def test_get_upstream_data_integrity():
    graph = CausalGraph()
    # Adding edge twice to check count and average weight
    graph.add_edge("cause1", "effect1", weight=1.0)
    graph.add_edge("cause1", "effect1", weight=0.5)

    upstream = graph.get_upstream("effect1")
    assert len(upstream) == 1
    assert upstream[0].cause == "cause1"
    assert upstream[0].effect == "effect1"
    assert upstream[0].weight == 0.75  # (1.0 + 0.5) / 2
    assert upstream[0].count == 2
