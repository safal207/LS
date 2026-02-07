from codex.causal_memory import AdaptiveEngine, CausalGraph, MemoryRecord, MemoryStore


def test_memory_store_roundtrip(tmp_path):
    store = MemoryStore(tmp_path / "memory.jsonl")
    record = MemoryRecord.build(
        model="qwen",
        model_type="llm",
        inputs={"prompt": "hello"},
        outputs={"completion": "hi"},
        parameters={"quant": "q4"},
        hardware={"ram_gb": 16},
        metrics={"tokenspersecond": 12.5},
        success=True,
    )
    store.add(record)
    loaded = store.load_all()
    assert len(loaded) == 1
    assert loaded[0].model == "qwen"
    assert loaded[0].metrics["tokenspersecond"] == 12.5


def test_causal_graph_observe_failure_conditions():
    graph = CausalGraph()
    record = MemoryRecord.build(
        model="whisper-medium",
        model_type="stt",
        inputs={"benchmark": "stt"},
        outputs={},
        parameters={},
        hardware={"ram_gb": 4, "vram_gb": 2},
        metrics={"realtimefactor": 1.4, "tokenspersecond": 2.0},
        success=False,
        error="oom",
    )
    graph.observe(record)
    effects = {edge.effect for edge in graph.get_downstream("ram<8gb")}
    assert "failure:whisper-medium" in effects
    error_effects = {edge.effect for edge in graph.get_downstream("error:oom")}
    assert "failure:whisper-medium" in error_effects


def test_adaptive_engine_ranking_penalizes_failure(tmp_path):
    store = MemoryStore(tmp_path / "memory.jsonl")
    graph = CausalGraph()
    engine = AdaptiveEngine(store, graph)

    success = MemoryRecord.build(
        model="stable-model",
        model_type="llm",
        inputs={},
        outputs={},
        parameters={},
        hardware={"ram_gb": 16},
        metrics={"tokenspersecond": 15.0},
        success=True,
    )
    failure = MemoryRecord.build(
        model="fragile-model",
        model_type="llm",
        inputs={},
        outputs={},
        parameters={},
        hardware={"ram_gb": 4},
        metrics={"tokenspersecond": 2.0},
        success=False,
    )
    store.add(success)
    store.add(failure)
    graph.observe(success)
    graph.observe(failure)

    ranked = engine.rank_models(["stable-model", "fragile-model"], context={"ram_gb": 4})
    assert ranked[0].model == "stable-model"
