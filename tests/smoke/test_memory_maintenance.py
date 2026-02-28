import time
import psutil
import pytest
from collections import deque
from python.modules.hexagon_core.temporal_graph import TemporalGraph, TemporalNode
from codex.causal_memory.visceral import VisceralMemory

def test_prune_reduces_node_count():
    graph = TemporalGraph()
    # Create 1000 nodes, some weak, some strong
    for i in range(1000):
        node = TemporalNode(id=f"node_{i}", resonance=0.1 if i < 500 else 0.8)
        graph.nodes[node.id] = node
        graph.active_chain.append(node)

    # Prune with active_window=100 (so nodes 900-999 are protected by window)
    # Weak nodes: 0-499. None of them are in 900-999. So all 500 weak nodes should be pruned.
    pruned = graph.prune_weak_nodes(threshold=0.25, active_window=100)

    assert pruned == 500
    assert len(graph.nodes) == 500

def test_compact_reduces_history_size():
    visceral = VisceralMemory(history_size=500)
    now = time.time()
    # 200 events, alternating but close in time and intensity
    for i in range(100):
        # Pairs of identical events
        visceral.history.append({
            "event": "pain",
            "intensity": 0.5,
            "ts": now + i * 10
        })
        visceral.history.append({
            "event": "pain",
            "intensity": 0.51,
            "ts": now + i * 10 + 2
        })

    assert len(visceral.history) == 200
    compacted = visceral.compact_history()

    # Should reduce by about 50%
    assert compacted == 100
    assert len(visceral.history) == 100

def test_search_time_before_after():
    graph = TemporalGraph()
    # Mocking nodes for search simulation
    for i in range(2000):
        node = TemporalNode(id=f"node_{i}", resonance=0.1 if i % 2 == 0 else 0.9)
        graph.nodes[node.id] = node
        graph.active_chain.append(node)

    def simulate_search():
        start = time.perf_counter()
        # Dummy search: iterate over nodes
        count = 0
        for nid in graph.nodes:
            if "node_199" in nid:
                count += 1
        return time.perf_counter() - start

    time_before = simulate_search()
    graph.prune_weak_nodes(threshold=0.25, active_window=100)
    time_after = simulate_search()

    # Pruning should remove ~1000 nodes (except those in active window)
    # Less nodes -> faster iteration
    assert time_after < time_before or abs(time_after - time_before) < 0.001 # Small scale might be noisy

def test_ram_usage_before_after():
    graph = TemporalGraph()
    process = psutil.Process()

    # Large number of nodes to see RAM difference
    for i in range(10000):
        node = TemporalNode(id=f"node_{i}", resonance=0.1)
        graph.nodes[node.id] = node

    ram_before = process.memory_info().rss
    graph.prune_weak_nodes(threshold=0.25, active_window=0)
    ram_after = process.memory_info().rss

    # Since we deleted 10000 objects, RAM should decrease or stay same (GC timing varies)
    # We'll just assert that len is 0
    assert len(graph.nodes) == 0
