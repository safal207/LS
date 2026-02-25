from modules.llm.temporal_graph import build_graph, find_related, visualize_ascii


def _sample_entries(count: int = 12):
    entries = []
    for idx in range(count):
        thread = f"thread-{idx % 3}"
        entries.append(
            {
                "ts": f"2026-02-25T10:00:{idx:02d}Z",
                "cause": f"cause {idx}",
                "solution": f"solution {idx}",
                "ltp_trace": {"thread_id": thread},
                "lri_core": {"resonance_map": {"focus": 0.7 + (idx % 2) * 0.1}},
            }
        )

    if count > 4:
        entries[4]["cause"] = "solution 1 appears later"
    if count > 7:
        entries[7]["cause"] = "solution 3 appears later"
    return entries


def test_build_graph_from_10_plus_entries():
    entries = _sample_entries(12)
    graph = build_graph(lambda: entries)

    assert len(graph["nodes"]) == 12
    assert any(edge["relation"] == "temporal" for edge in graph["edges"])
    assert any(edge["relation"] == "resonance" for edge in graph["edges"])


def test_find_related_depth_two_returns_neighbors():
    graph = build_graph(lambda: _sample_entries(12))
    related = find_related(graph, "thread-0", max_depth=2)

    assert related
    assert "thread-0" not in related


def test_visualize_ascii_is_readable():
    graph = build_graph(lambda: _sample_entries(6))
    view = visualize_ascii(graph)

    assert "Temporal Graph" in view
    assert "└─" in view
    assert "thread-" in view
