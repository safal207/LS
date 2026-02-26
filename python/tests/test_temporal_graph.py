from modules.llm.temporal_graph import (
    build_graph,
    find_related,
    find_vector_related,
    get_context_for_question,
    visualize_ascii,
)


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


def _semantic_entries():
    return [
        {
            "ts": "2026-02-25T10:00:01Z",
            "cause": "database outage from connection pool exhaustion",
            "solution": "increase DB pool and restart service",
            "ltp_trace": {"thread_id": "thread-db"},
        },
        {
            "ts": "2026-02-25T10:00:02Z",
            "cause": "android crash due to null pointer",
            "solution": "guard null values in renderer",
            "ltp_trace": {"thread_id": "thread-android"},
        },
        {
            "ts": "2026-02-25T10:00:03Z",
            "cause": "database latency spikes on postgres",
            "solution": "tune query plan and increase DB pool",
            "ltp_trace": {"thread_id": "thread-postgres"},
        },
    ]


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


def test_vector_related_finds_semantic_matches():
    graph = build_graph(_semantic_entries)

    related = find_vector_related(
        graph,
        thread_id="thread-db",
        query_text="postgres database pool exhausted",
        top_k=5,
        min_similarity=0.2,
    )

    assert any(node_id.startswith("thread-postgres:") for node_id in related)


def test_context_includes_vector_matches():
    context = get_context_for_question(
        "database pool exhausted on postgres",
        "thread-db",
        replay_loader=_semantic_entries,
        max_depth=1,
        max_entries=2,
    )

    assert "[Из памяти системы — похожие ситуации]" in context
    assert "tune query plan" in context
