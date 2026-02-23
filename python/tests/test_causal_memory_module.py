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

    # Verify coherence is within valid range and derived
    coherence = lce["qos"]["coherence"]
    assert 0.0 <= coherence <= 1.0
    # For default prev=0.95 and stub measured=0.90, result should be between them
    assert 0.90 < coherence < 0.95


def test_coherence_influence_and_prev_value():
    # Test that passing prev_coherence works
    lce1, _, _ = causal_memory.build_default_trace_payloads("q", "t", prev_coherence=0.95)
    lce2, _, _ = causal_memory.build_default_trace_payloads("q", "t", prev_coherence=0.60)

    coh1 = lce1["qos"]["coherence"]
    coh2 = lce2["qos"]["coherence"]

    assert coh1 > coh2
    assert coh1 > 0.90  # drifting towards 0.90 from 0.95
    assert coh2 > 0.60  # drifting towards 0.90 from 0.60


def test_smooth_coherence_fallback_logic():
    # Verify fallback logic if we can't import the real one
    # We can test the function directly from the module
    res = causal_memory.smooth_coherence(0.8, 0.9, drift=0.1, noise=0.0)
    assert 0.8 < res < 0.9

    res_high_drift = causal_memory.smooth_coherence(0.8, 0.9, drift=0.5, noise=0.0)
    # Higher drift should lead to higher gain, so closer to measured (0.9)
    assert res_high_drift > res
