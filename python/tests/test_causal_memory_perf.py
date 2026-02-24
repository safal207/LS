import time
import pytest
from modules.llm import causal_memory

class _DummyReg:
    def __init__(self):
        self.saved = None

    def save_causal_trace(self, *args):
        self.saved = args

def test_save_causal_trace_performance():
    reg = _DummyReg()
    lce = {"v": 1, "intent": {"type": "answer", "goal": "test"}, "memory": {"thread": "t1", "t": "now"}}
    ltp = {"thread_id": "t1", "drift": 0.05}
    lri = {"emotional_drift": 0.1, "resonance_map": {"focus": 0.9}, "invariants": ["non_reductive"]}

    # Warmup
    for _ in range(10):
        causal_memory.save_causal_trace(
            "cause", "solution", lce, ltp, lri,
            get_registry_manager=lambda: reg,
            save_to_codex=lambda _: None
        )

    start = time.perf_counter()
    iterations = 100
    for _ in range(iterations):
        causal_memory.save_causal_trace(
            "cause", "solution", lce, ltp, lri,
            get_registry_manager=lambda: reg,
            save_to_codex=lambda _: None
        )
    elapsed = (time.perf_counter() - start) / iterations

    print(f"Average save_causal_trace time (Python overhead): {elapsed*1000:.4f}ms")
    # Requirement: < 3ms (including Rust, but Python part should be very fast)
    assert elapsed < 0.003

if __name__ == "__main__":
    test_save_causal_trace_performance()
