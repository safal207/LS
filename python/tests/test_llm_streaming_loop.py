import pytest
pytest.importorskip("requests")

import queue

from modules.llm.llm_module import LanguageModel, _chunk_ready_for_tts, _compress_messages_for_hint


def test_compress_messages_for_hint_keeps_system_and_recent():
    messages = [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "older"},
        {"role": "user", "content": "new"},
    ]
    out = _compress_messages_for_hint(messages, max_messages=2)
    assert out[0]["role"] == "system"
    assert out[-2:] == messages[-2:]


def test_chunk_ready_for_tts_detects_sentence_boundaries():
    assert _chunk_ready_for_tts("hello.") is True
    assert _chunk_ready_for_tts("hello?") is True
    assert _chunk_ready_for_tts("hello") is False


def test_run_emits_token_tts_and_final_events(monkeypatch):
    in_q: queue.Queue = queue.Queue()
    out_q: queue.Queue = queue.Queue()
    model = LanguageModel(in_q, out_q)

    def _fake_generate(question, cancel_event=None, messages=None, *, stream=False, on_token=None):
        assert stream is True
        if on_token:
            on_token("Hello")
            on_token(".")
        return "Hello."

    monkeypatch.setattr(model, "test_ollama_connection", lambda: True)
    monkeypatch.setattr(model, "generate_response", _fake_generate)

    in_q.put({"type": "question", "text": "q", "timestamp": 0})
    model.running = True

    # run one iteration by forcing stop after first task_done
    original_task_done = in_q.task_done

    def _task_done_and_stop():
        original_task_done()
        model.running = False

    monkeypatch.setattr(in_q, "task_done", _task_done_and_stop)
    model.run()

    events = []
    while not out_q.empty():
        events.append(out_q.get_nowait())

    assert any(e.get("type") == "token" for e in events)
    assert any(e.get("type") == "tts_chunk" for e in events)
    assert any(e.get("type") == "final" for e in events)
