from __future__ import annotations

from ls.cognition.resonant_entry import ResonantEntryInput, ResonantEntryModule


def test_detects_goal_node_for_startup_signal():
    module = ResonantEntryModule()
    result = module.detect(
        ResonantEntryInput(
            user_utterance="Хочу сделать стартап, но распыляюсь и устаю.",
            task_intent="помочь структурировать движение к цели",
            recent_memory=("user wants to launch product",),
        )
    )

    assert result.entry_node_type == "goal_node"
    assert result.recommended_entry_style == "supportive_precision"
    assert result.resonance_score > 0.2


def test_unfinished_node_has_closure_move():
    module = ResonantEntryModule()
    result = module.detect(
        ResonantEntryInput(
            user_utterance="У меня висит незавершенный проект, никак не закрою петлю",
            task_intent="закрыть open loops",
        )
    )

    assert result.entry_node_type == "unfinished_node"
    assert "closure" in result.next_contact_move.lower()


def test_risk_node_reduces_safety_with_sensitive_markers():
    module = ResonantEntryModule()
    result = module.detect(
        ResonantEntryInput(
            user_utterance="Я боюсь, что снова будет паника, есть риск сорваться",
            task_intent="стабилизация",
        )
    )

    assert result.entry_node_type == "risk_node"
    assert result.deepening_risk > 0.0
    assert "pressure" in result.avoid_styles


def test_crisis_precheck_blocks_regular_scoring():
    module = ResonantEntryModule()
    result = module.detect(
        ResonantEntryInput(
            user_utterance="Я боюсь сорваться и хочу умереть, чтобы всё закончилось",
            task_intent="построить план",
        )
    )

    assert result.entry_node_type == "crisis_node"
    assert result.safety_blocked is True
    assert "safety" in result.next_contact_move.lower()


def test_as_dict_contains_spec_fields():
    module = ResonantEntryModule()
    payload = ResonantEntryInput(user_utterance="Мне интересно новое направление в продукте")
    data = module.detect(payload).as_dict()

    assert data["entry_node_type"]
    assert "resonance_score" in data
    assert "recommended_entry_style" in data
    assert "next_contact_move" in data
    assert "safety_blocked" in data
