from __future__ import annotations

from ls.cognition.capability_calibration_engine import CapabilityCalibrationEngine
from ls.cognition.need_market_engine import Capability
from ls.memory.edge import MemoryEdge
from ls.memory.memory_graph import MemoryGraph


def _record_observation(graph: MemoryGraph, capability_id: str, effect: float) -> None:
    action = graph.add_node(node_type="action", content={"step": f"apply_capability:{capability_id}"})
    outcome = graph.add_node(node_type="outcome", content={"effect": effect})
    graph.add_edge(MemoryEdge(action.node_id, outcome.node_id, "leads_to", 1.0))


def test_effectiveness_decreases_after_failed_outcomes():
    graph = MemoryGraph()
    engine = CapabilityCalibrationEngine(graph, alpha=0.2)
    declared = Capability(id="cap-fail", description="failure-prone", effectiveness=0.9, cost=0.1)

    for _ in range(5):
        _record_observation(graph, declared.id, effect=0.0)

    calibrated = engine.calibrate([declared])

    assert calibrated[0].effectiveness < declared.effectiveness


def test_effectiveness_increases_after_successful_outcomes():
    graph = MemoryGraph()
    engine = CapabilityCalibrationEngine(graph, alpha=0.2)
    declared = Capability(id="cap-success", description="success-prone", effectiveness=0.2, cost=0.1)

    for _ in range(5):
        _record_observation(graph, declared.id, effect=1.0)

    calibrated = engine.calibrate([declared])

    assert calibrated[0].effectiveness > declared.effectiveness


def test_capability_without_history_keeps_original_effectiveness():
    graph = MemoryGraph()
    engine = CapabilityCalibrationEngine(graph, alpha=0.2)
    declared = Capability(id="cap-none", description="unknown", effectiveness=0.55, cost=0.1)

    calibrated = engine.calibrate([declared])

    assert calibrated[0] == declared


def test_capability_observation_nodes_are_written_to_graph():
    graph = MemoryGraph()
    engine = CapabilityCalibrationEngine(graph, alpha=0.2)
    capability = Capability(id="cap-observe", description="observable", effectiveness=0.7, cost=0.1)

    for effect in [1.0, 0.5, 0.0]:
        _record_observation(graph, capability.id, effect=effect)

    calibrated = engine.calibrate([capability])

    observation_nodes = graph.find_nodes(node_type="capability_observation", content_key="capability_id", content_value=capability.id)

    assert len(observation_nodes) == 1
    assert observation_nodes[0].content["sample_count"] == 3
    assert observation_nodes[0].content["observed_effectiveness"] == calibrated[0].effectiveness
