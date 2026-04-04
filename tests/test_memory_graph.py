from __future__ import annotations

from ls.memory.edge import MemoryEdge
from ls.memory.memory_graph import MemoryGraph
from ls.memory.node import MemoryNode


def test_memory_graph_node_edge_and_neighbors():
    graph = MemoryGraph()
    a = graph.add_node(MemoryNode("n1", "event", {"text": "input"}, 1.0))
    b = graph.add_node(MemoryNode("n2", "decision", {"text": "choose"}, 2.0))

    graph.add_edge(MemoryEdge(a.node_id, b.node_id, "leads_to", 1.0))

    neighbors = graph.get_neighbors("n1")
    assert [n.node_id for n in neighbors] == ["n2"]


def test_memory_graph_find_path_and_extract_context():
    graph = MemoryGraph()
    n1 = graph.add_node(node_type="event", content={"text": "event"})
    n2 = graph.add_node(node_type="action", content={"text": "action"})
    n3 = graph.add_node(node_type="reflection", content={"text": "reflection"})

    graph.add_edge(MemoryEdge(n1.node_id, n2.node_id, "leads_to", 1.0))
    graph.add_edge(MemoryEdge(n2.node_id, n3.node_id, "derived_from", 0.8))

    path = graph.find_path(n1.node_id, n3.node_id)
    assert path == [n1.node_id, n2.node_id, n3.node_id]

    ctx = graph.extract_context(n1.node_id, depth=2)
    assert ctx["summaries"]["node_count"] == 3
    assert len(ctx["edges"]) == 2


def test_memory_graph_semantic_search():
    graph = MemoryGraph()
    graph.add_node(node_type="fact", content={"text": "agent learned graph planning"})
    graph.add_node(node_type="fact", content={"text": "audio queue utilization high"})

    hits = graph.semantic_search("graph planning", limit=1)
    assert len(hits) == 1
    assert "graph" in str(hits[0].content).lower()


def test_memory_graph_find_nodes_with_indexed_filters():
    graph = MemoryGraph()
    graph.add_node(MemoryNode("n1", "fact", {"capability_id": "cap-a", "text": "first"}, 1.0))
    graph.add_node(MemoryNode("n2", "fact", {"capability_id": "cap-b", "text": "second"}, 2.0))
    graph.add_node(MemoryNode("n3", "event", {"capability_id": "cap-a", "text": "third"}, 3.0))

    hits = graph.find_nodes(node_type="fact", content_key="capability_id", content_value="cap-a")
    assert [node.node_id for node in hits] == ["n1"]


def test_memory_graph_reindex_on_node_overwrite():
    graph = MemoryGraph()
    graph.add_node(MemoryNode("n1", "fact", {"text": "old planning term"}, 1.0))
    graph.add_node(MemoryNode("n1", "fact", {"text": "new routing term"}, 2.0))

    old_hits = graph.semantic_search("planning", limit=5)
    new_hits = graph.semantic_search("routing", limit=5)

    assert all(node.node_id != "n1" for node in old_hits)
    assert any(node.node_id == "n1" for node in new_hits)
