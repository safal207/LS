import pytest

from codex.causal_memory import Amygdala, AmygdalaBlockError, BlockReason, CausalMemoryTransitions


def test_amygdala_blocks_overload():
    transitions = CausalMemoryTransitions(amygdala=Amygdala())

    with pytest.raises(AmygdalaBlockError) as exc:
        transitions.transition_down(
            current_layer="Consumer",
            target_layer="Execution",
            text="нужно сделать сразу",
            resonance=0.8,
            axis_position=0.9,
            delta_axis=0.4,
        )

    assert exc.value.reason == BlockReason.OVERLOAD


def test_amygdala_blocks_low_resonance_chain():
    amygdala = Amygdala(window_size=5)
    transitions = CausalMemoryTransitions(amygdala=amygdala)

    for _ in range(4):
        transitions.transition_down(
            current_layer="Consumer",
            target_layer="Execution",
            text="нейтрально",
            resonance=0.45,
            axis_position=0.2,
            delta_axis=0.1,
        )

    with pytest.raises(AmygdalaBlockError) as exc:
        transitions.transition_down(
            current_layer="Consumer",
            target_layer="Execution",
            text="падает резонанс без маркеров",
            resonance=0.1,
            axis_position=0.2,
            delta_axis=0.1,
        )

    assert exc.value.reason == BlockReason.LOW_RESONANCE


def test_affect_modifies_resonance():
    transitions = CausalMemoryTransitions(amygdala=Amygdala())

    positive = transitions.transition_down(
        current_layer="Consumer",
        target_layer="Execution",
        text="радость и нужно",
        resonance=0.5,
        axis_position=0.3,
        delta_axis=0.1,
    )

    neutral = transitions.transition_down(
        current_layer="Consumer",
        target_layer="Execution",
        text="просто запрос",
        resonance=0.5,
        axis_position=0.3,
        delta_axis=0.1,
    )

    assert positive.affect > neutral.affect
    assert positive.resonance > neutral.resonance


def test_amygdala_blocks_threat_affect():
    transitions = CausalMemoryTransitions()

    with pytest.raises(AmygdalaBlockError) as exc:
        transitions.transition_down(
            current_layer="Consumer",
            target_layer="Execution",
            text="страх и угроза перегрузки",
            resonance=0.8,
            axis_position=0.5,
            delta_axis=0.1,
        )

    assert exc.value.reason == BlockReason.THREAT


def test_amygdala_blocks_sharp_resonance_drop():
    amygdala = Amygdala(window_size=3)
    transitions = CausalMemoryTransitions(amygdala=amygdala)

    transitions.transition_down(
        current_layer="Consumer",
        target_layer="Execution",
        text="нейтрально",
        resonance=0.7,
        axis_position=0.3,
        delta_axis=0.1,
    )
    transitions.transition_down(
        current_layer="Consumer",
        target_layer="Execution",
        text="нейтрально",
        resonance=0.65,
        axis_position=0.4,
        delta_axis=0.1,
    )

    with pytest.raises(AmygdalaBlockError) as exc:
        transitions.transition_down(
            current_layer="Consumer",
            target_layer="Execution",
            text="падает резонанс",
            resonance=0.15,
            axis_position=0.5,
            delta_axis=0.1,
        )

    assert exc.value.reason == BlockReason.LOW_RESONANCE
