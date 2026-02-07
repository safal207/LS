from codex.causal_memory import CausalGraph, MemoryRecord
from codex.dmp import DecisionMemoryProtocol
from codex.lpi import PresenceMonitor, SystemState
from codex.lpi.integration import enrich_decision_context
from codex.selector.model_selector import AdaptiveModelSelector
from codex.registry.model_config import ModelConfig


def test_causal_graph_conditions_include_system_state():
    graph = CausalGraph()
    record = MemoryRecord.build(
        model="qwen",
        model_type="llm",
        inputs={"metadata": {"system_state": "overload"}},
        outputs={},
        parameters={},
        hardware={},
        metrics={},
        success=True,
    )
    graph.observe(record)
    effects = {edge.effect for edge in graph.get_downstream("state_overload")}
    assert "success:qwen" in effects


def test_selector_penalizes_heavy_models_on_overload():
    monitor = PresenceMonitor()
    monitor.update(capu_features={"rtf_estimate": 1.2}, metrics={}, hardware={})
    assert monitor.current_state.state is SystemState.OVERLOAD

    selector = AdaptiveModelSelector.__new__(AdaptiveModelSelector)
    selector.presence_monitor = monitor

    light = ModelConfig.from_dict(
        "light-model",
        {"type": "llm", "path": "models/light", "ram_required": "1GB"},
    )
    heavy = ModelConfig.from_dict(
        "heavy-model",
        {"type": "llm", "path": "models/heavy", "ram_required": "8GB"},
    )
    ranked = AdaptiveModelSelector._score_models(
        selector,
        [light, heavy],
        benchmarks={},
        priority="latency",
    )
    assert ranked[0].name == "light-model"


def test_decision_protocol_records_system_state():
    monitor = PresenceMonitor()
    monitor.update(capu_features={"avg_attention_entropy": 6.0}, metrics={}, hardware={})
    protocol = DecisionMemoryProtocol()
    context = enrich_decision_context({"action": "choose_model"}, monitor)
    record = protocol.record_decision(decision="select", context=context)
    assert record.context["system_state"] == SystemState.DIFFUSE_FOCUS.value
