from modules.memory.causal import CausalMemory


def test_causal_memory_exposes_backend_and_diagnostics() -> None:
    memory = CausalMemory()
    assert memory.backend_name in {"rust", "python_fallback"}

    diagnostics = memory.diagnostics()
    assert diagnostics["backend"] == memory.backend_name


def test_causal_memory_basic_flow_works_for_any_backend() -> None:
    memory = CausalMemory()
    customer = memory.add_intent("draft architecture")
    execution = memory.transition_down(customer, "draft architecture implementation", "Execution")

    resonance = memory.check_resonance(execution)
    axis = memory.get_axis_position(execution)

    assert 0.0 <= resonance <= 1.0
    assert -1.0 <= axis <= 1.0
