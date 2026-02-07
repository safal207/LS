from codex.lpi import PresenceMonitor, StateTransitionEngine, SystemState


def test_state_transition_engine_overload():
    engine = StateTransitionEngine()
    snapshot = engine.update(
        capu_features={"rtf_estimate": 1.2},
        metrics={},
        hardware={},
    )
    assert snapshot.state is SystemState.OVERLOAD


def test_presence_monitor_records_history():
    monitor = PresenceMonitor()
    snapshot = monitor.update(
        capu_features={"logits_confidence_margin": 0.05},
        metrics={},
        hardware={},
    )
    assert monitor.current_state is snapshot
    assert snapshot.state is SystemState.UNCERTAIN
    assert monitor.history[-1] is snapshot
