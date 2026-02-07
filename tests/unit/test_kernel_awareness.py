from __future__ import annotations

from codex.causal_memory.engine import AdaptiveEngine
from codex.causal_memory.graph import CausalGraph
from codex.causal_memory.store import MemoryRecord
from codex.causal_memory.store import MemoryStore
from codex.cognitive.scheduler import ThreadScheduler
from codex.cognitive.thread import CognitiveThread
from codex.cognitive.workspace.frame import GlobalFrame


def test_kernel_conditions_added(tmp_path) -> None:
    engine = AdaptiveEngine(MemoryStore(tmp_path / "memory.jsonl"), CausalGraph())
    conditions = list(
        engine._conditions_from_context(
            {
                "kernel": {
                    "signals": [
                        "cache_thrashing",
                        "syscall_flood",
                        "branch_mispredict_storm",
                        "context_switch_storm",
                        "iowait_spike",
                        "thermal_throttling",
                    ]
                }
            }
        )
    )
    assert "kernel:cache_thrashing" in conditions
    assert "kernel:syscall_flood" in conditions
    assert "kernel:branch_mispredict_storm" in conditions
    assert "kernel:context_switch_storm" in conditions
    assert "kernel:iowait_spike" in conditions
    assert "kernel:thermal_throttling" in conditions


def test_kernel_strategy_override(tmp_path) -> None:
    engine = AdaptiveEngine(MemoryStore(tmp_path / "memory.jsonl"), CausalGraph())
    assert engine.recommend_strategy(["model-a"], context={"kernel": {"state": "overload"}}) == "ultra_conservative"
    assert engine.recommend_strategy(["model-a"], context={"kernel": {"state": "stable"}}) == "balanced"
    assert (
        engine.recommend_strategy(["model-a"], context={"kernel": {"state": "high_throughput"}}) == "aggressive"
    )


def test_scheduler_kernel_signal_adjustments() -> None:
    scheduler = ThreadScheduler()
    io_thread = CognitiveThread(thread_id="io", priority=0.6, attention_weight=1.0, tags=["io-heavy"])
    cpu_thread = CognitiveThread(thread_id="cpu", priority=0.9, attention_weight=1.0)
    low_thread = CognitiveThread(thread_id="low", priority=0.3, attention_weight=1.0)
    scheduler.register_thread(io_thread)
    scheduler.register_thread(cpu_thread)
    scheduler.register_thread(low_thread)

    frame = GlobalFrame(
        thread_id="cpu",
        task_type="chat",
        system_state="stable",
        self_model={},
        affective={},
        identity={},
        capu_features={},
        decision={},
        memory_refs={},
        merit_scores={"focus": 0.5},
        timestamp="2025-01-01T00:00:00+00:00",
        hardware={"kernel": {"signals": ["cache_thrashing", "iowait_spike", "context_switch_storm"]}},
    )

    scheduler.update_attention(frame)

    assert io_thread.active is False
    assert low_thread.active is False
    assert cpu_thread.attention_weight > 1.0


def test_kernel_causal_edges_from_record() -> None:
    graph = CausalGraph()
    record = MemoryRecord.build(
        model="model-a",
        model_type="llm",
        inputs={},
        outputs={},
        hardware={"kernel": {"signals": ["cache_thrashing"], "state": "overload"}},
        metrics={},
        success=False,
    )
    graph.observe(record)
    downstream = graph.get_downstream("kernel:cache_thrashing")
    assert any(edge.effect.startswith("failure:model-a") for edge in downstream)
