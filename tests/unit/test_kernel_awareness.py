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


def test_scheduler_assigns_affinity_and_numa() -> None:
    scheduler = ThreadScheduler()
    thread = CognitiveThread(thread_id="t1", priority=0.8, attention_weight=1.0)
    scheduler.register_thread(thread)
    frame = GlobalFrame(
        thread_id="t1",
        task_type="chat",
        system_state="stable",
        self_model={},
        affective={},
        identity={},
        capu_features={},
        decision={},
        memory_refs={},
        merit_scores={},
        timestamp="2025-01-01T00:00:00+00:00",
        hardware={
            "topology": {"per_cpu_percent": [10.0, 20.0, 5.0, 40.0]},
            "numa": {"nodes": {"0": {"cpus": [0, 1], "mem_total_gb": 16.0, "mem_free_gb": 8.0}}},
        },
    )
    scheduler.update_attention(frame)
    assert thread.cpu_affinity
    assert thread.numa_node == 0


def test_graph_conditions_for_topology_and_numa() -> None:
    graph = CausalGraph()
    record = MemoryRecord.build(
        model="model-b",
        model_type="llm",
        inputs={},
        outputs={},
        hardware={
            "topology": {"per_cpu_percent": [90.0, 20.0], "logical_cpus": 4, "physical_cores": 2},
            "numa": {"nodes": {"0": {"mem_total_gb": 16.0, "mem_free_gb": 1.0}}},
            "cpu_temp": 85.0,
        },
        metrics={},
        success=True,
    )
    graph.observe(record)
    assert graph.get_downstream("cpu_hotspot")
    assert graph.get_downstream("numa_pressure")


def test_lri_conditions_and_scheduler_integration(tmp_path) -> None:
    engine = AdaptiveEngine(MemoryStore(tmp_path / "memory.jsonl"), CausalGraph())
    assert engine.recommend_strategy(["model-a"], context={"lri": {"value": 0.9}}) == "ultra_conservative"

    scheduler = ThreadScheduler()
    thread = CognitiveThread(thread_id="t1", priority=0.5, attention_weight=1.0)
    scheduler.register_thread(thread)
    frame = GlobalFrame(
        thread_id="t1",
        task_type="chat",
        system_state="stable",
        self_model={},
        affective={},
        identity={},
        capu_features={},
        decision={},
        memory_refs={},
        merit_scores={},
        timestamp="2025-01-01T00:00:00+00:00",
        hardware={"lri": {"value": 0.85, "state": "overload", "tags": ["cpu_bound"]}},
    )
    scheduler.update_attention(frame)
    assert thread.active is False

    graph = CausalGraph()
    record = MemoryRecord.build(
        model="model-c",
        model_type="llm",
        inputs={},
        outputs={},
        hardware={"lri": {"value": 0.9, "state": "overload", "tags": []}},
        metrics={},
        success=False,
    )
    graph.observe(record)
    assert graph.get_downstream("lri_overload")
