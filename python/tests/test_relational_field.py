from __future__ import annotations

from graph.relational_field import RelationalFieldAnalyzer, compute_relational_coherence


def test_relational_analyzer_returns_snapshot_with_expected_fields() -> None:
    analyzer = RelationalFieldAnalyzer()

    snapshot = analyzer.analyze(
        text="Я понимаю твою точку зрения, давай вместе посмотрим варианты.",
        participants=["alice", "bob"],
    )

    payload = snapshot.to_dict()

    assert payload["field_id"]
    assert payload["timestamp"]
    assert payload["participants"] == ["alice", "bob"]
    assert payload["interaction_scope"] == "human-human"
    assert "tension_score" in payload
    assert "alignment_score" in payload
    assert "dominant_signal" in payload
    assert "background_pressure" in payload
    assert "foreground_expression" in payload
    assert "notes" in payload
    assert "metadata" in payload
    assert "relational_coherence" in payload["metadata"]
    assert 0.0 <= payload["metadata"]["relational_coherence"] <= 1.0


def test_relational_analyzer_high_conflict_raises_tension() -> None:
    analyzer = RelationalFieldAnalyzer()

    conflict = analyzer.analyze(
        text="Ты опять должен это сделать сейчас! Это невозможно, никогда так не работало!"
    )
    cooperative = analyzer.analyze(
        text="Давай вместе посмотрим, я слышу тебя и хочу понять, что важно нам обоим."
    )

    assert conflict.tension_score > cooperative.tension_score
    assert conflict.tension_score >= 0.4


def test_relational_analyzer_cooperative_text_raises_alignment() -> None:
    analyzer = RelationalFieldAnalyzer()

    cooperative = analyzer.analyze(
        text="Я понимаю и я слышу тебя. Давай вместе найдём решение, нам важно договориться."
    )
    neutral = analyzer.analyze(text="Передай статус по задаче.")

    assert cooperative.alignment_score > neutral.alignment_score
    assert cooperative.alignment_score > 0.35


def test_compute_relational_coherence_rewards_alignment_and_low_tension() -> None:
    stable = compute_relational_coherence(
        tension_score=0.15,
        alignment_score=0.78,
        foreground=["repair_attempt"],
        background=[],
    )
    strained = compute_relational_coherence(
        tension_score=0.82,
        alignment_score=0.18,
        foreground=["pressure", "attack"],
        background=["urgency", "overload"],
    )

    assert 0.0 <= stable <= 1.0
    assert 0.0 <= strained <= 1.0
    assert stable > strained
