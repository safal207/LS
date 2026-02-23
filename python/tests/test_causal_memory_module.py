from modules.llm import causal_memory


class _DummyReg:
    def __init__(self):
        self.saved = None
        self.replay = []

    def save_causal_trace(self, *args):
        self.saved = args

    def replay_thread(self, thread_id):
        return self.replay


def test_save_causal_trace_uses_registry_and_codex_sink():
    reg = _DummyReg()
    captured = {}

    def _save_to_codex(payload):
        captured.update(payload)

    causal_memory.save_causal_trace(
        "cause",
        "solution",
        {"lce": 1},
        {"thread_id": "thread-1"},
        {"stabilizer": "active"},
        confidence=0.9,
        get_registry_manager=lambda: reg,
        save_to_codex=_save_to_codex,
    )

    assert reg.saved is not None
    assert captured["event_type"] == "causal_trace"
    assert captured["lri_core"]["stabilizer"] == "active"


def test_replay_thread_and_command_parser():
    reg = _DummyReg()
    reg.replay = [{"ts": "now"}]

    out = causal_memory.replay_thread("thread-1", get_registry_manager=lambda: reg)
    assert out == [{"ts": "now"}]

    assert causal_memory.extract_replay_thread_id("replay thread-123") == "thread-123"
    assert causal_memory.extract_replay_thread_id("переиграй test-xyz,") == "test-xyz"
    assert causal_memory.extract_replay_thread_id("replay please") is None


def test_build_default_trace_payloads():
    lce, ltp_trace, lri_core = causal_memory.build_default_trace_payloads("hello", "thread-7")

    assert lce["intent"]["goal"] == "hello"
    assert lce["memory"]["thread"] == "thread-7"
    assert ltp_trace["thread_id"] == "thread-7"
    assert lri_core["stabilizer"] == "active"
