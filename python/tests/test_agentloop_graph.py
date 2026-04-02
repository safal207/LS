# -*- coding: utf-8 -*-
def test_get_context_returns_related_solutions():
    entries = [
        {
            "ts": "2026-02-25T10:00:00Z",
            "cause": "auth error on login",
            "solution": "patch jwt token",
            "ltp_trace": {"thread_id": "thread-1"},
            "lri_core": {"resonance_map": {"focus": 0.85}},
        },
        {
            "ts": "2026-02-25T10:00:05Z",
            "cause": "need to patch jwt token in prod",
            "solution": "deployed fix",
            "ltp_trace": {"thread_id": "thread-2"},
            "lri_core": {"resonance_map": {"focus": 0.85}},
        },
    ]
    from modules.llm.temporal_graph import get_context_for_question

    context = get_context_for_question(
        "jwt issue",
        "thread-1",
        replay_loader=lambda: entries,
        max_depth=2,
        max_entries=3,
    )
    assert "[Из памяти системы" in context
    assert "patch jwt token" in context


def test_get_context_returns_empty_for_unknown_thread():
    from modules.llm.temporal_graph import get_context_for_question

    context = get_context_for_question(
        "something",
        "thread-unknown",
        replay_loader=lambda: [],
    )
    assert context == ""
