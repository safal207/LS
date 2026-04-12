# -*- coding: utf-8 -*-
"""Tests for Phase 2.4 — emotional layer in ask_self, MCP resources, tools.

Covers:
  T-4  ask_self tests (emotional questions, causal_trace emotional nodes)
  T-5  MCP tests (new resources readable, old resources unbroken, new tool works)
  T-7  Safety / boundary: constitution stays primary
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock


from modules.graph.memory_store import MemoryGraphStore


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _make_bridge(tmp_path: Path):
    """Create a CognitiveStateBridge pointing at a temp store."""
    from ls.agent_shell.cognitive_state import CognitiveStateBridge

    store_path = tmp_path / "cases.jsonl"
    os.environ["GRAPH_MEMORY_STORE_PATH"] = str(store_path)
    manager = MagicMock()
    manager.get_resonance_snapshot = MagicMock(return_value=[])
    manager.get_alignment_current = MagicMock(return_value={"alignment_state": "ok"})
    return CognitiveStateBridge(task_manager=manager), MemoryGraphStore(store_path)


def _seed_emotional_data(store: MemoryGraphStore, n: int = 3) -> None:
    for i in range(n):
        store.update_emotional_memory_from_cycle(
            cycle_id=f"seed_{i}",
            source="care_cycle",
            resonance_score=0.6 + i * 0.05,
            alignment_score=0.65 + i * 0.04,
        )


# ──────────────────────────────────────────────────────────────
# T-4  ask_self — emotional layer
# ──────────────────────────────────────────────────────────────


class TestAskSelfEmotionalLayer:
    def test_ask_self_returns_emotional_layer_key(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        result = bridge.ask_self("How do you feel about our recent interactions?")
        assert "emotional_layer" in result
        assert isinstance(result["emotional_layer"], dict)

    def test_ask_self_causal_trace_contains_emotional_event(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        result = bridge.ask_self("Do you feel we have a warm connection?")
        types = [node["type"] for node in result.get("causal_trace", [])]
        assert "emotional_event" in types

    def test_ask_self_causal_trace_contains_bond_shift(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=4)
        result = bridge.ask_self("Has our bond grown stronger?")
        types = [node["type"] for node in result.get("causal_trace", [])]
        assert "bond_shift" in types

    def test_ask_self_causal_trace_contains_emotional_summary_state(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        result = bridge.ask_self("What is our relationship like?")
        types = [node["type"] for node in result.get("causal_trace", [])]
        assert "emotional_summary_state" in types

    def test_ask_self_emotional_question_includes_tone_in_answer(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        result = bridge.ask_self("How warm is our connection?")
        answer = result.get("answer", "")
        # The answer should reference emotional signals
        assert any(kw in answer.lower() for kw in ("tone", "bond", "inferred", "signal"))

    def test_ask_self_non_emotional_question_still_works(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        result = bridge.ask_self("How coherent am I?")
        assert "answer" in result
        assert "coherence_now" in result
        assert "causal_trace" in result

    def test_ask_self_causal_trace_nodes_have_linked_from(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        result = bridge.ask_self("Feel close?")
        trace = result.get("causal_trace", [])
        # All nodes except the first should have linked_from
        for node in trace[1:]:
            assert "linked_from" in node

    def test_ask_self_partial_rollback_reflected(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        # Simulate a rollback scenario
        store.update_emotional_memory_from_cycle(
            cycle_id="rollback_test",
            source="council",
            rollback_present=True,
            coherence_score=0.55,
        )
        result = bridge.ask_self("How are things after the rollback?")
        assert "answer" in result
        assert "emotional_layer" in result


# ──────────────────────────────────────────────────────────────
# T-5  MCP resources
# ──────────────────────────────────────────────────────────────


class TestMCPResourcesEmotionalMemory:
    def test_emotional_memory_resource_readable(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        result = bridge.get_emotional_memory(limit=10)
        assert result["resource"] == "self/emotional-memory"
        assert "entries" in result
        assert "emotional_summary" in result
        assert "last_updated" in result

    def test_emotional_arc_resource_readable(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store)
        result = bridge.get_emotional_arc(limit=50)
        assert result["resource"] == "self/emotional-arc"
        assert "arc" in result
        assert "bond_trend" in result
        assert "last_updated" in result

    def test_emotional_memory_limit_respected(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=20)
        result = bridge.get_emotional_memory(limit=5)
        assert len(result["entries"]) <= 5

    def test_emotional_arc_limit_respected(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=20)
        result = bridge.get_emotional_arc(limit=3)
        assert len(result["arc"]) <= 3


class TestMCPResourceRegistryEmotional:
    def _make_registry(self, tmp_path: Path):
        from ls.agent_shell.mcp_resources import MCPResourceRegistry
        from ls.agent_shell.cognitive_state import CognitiveStateBridge

        store_path = tmp_path / "cases.jsonl"
        os.environ["GRAPH_MEMORY_STORE_PATH"] = str(store_path)
        manager = MagicMock()
        manager.get_resonance_snapshot = MagicMock(return_value=[])
        manager.get_alignment_current = MagicMock(return_value={"alignment_state": "ok"})
        cognitive = CognitiveStateBridge(task_manager=manager)
        return MCPResourceRegistry(task_manager=manager, cognitive_state=cognitive)

    def test_emotional_memory_in_resource_list(self, tmp_path):
        registry = self._make_registry(tmp_path)
        uris = [r.uri for r in registry.list_resources()]
        assert "self/emotional-memory" in uris

    def test_emotional_arc_in_resource_list(self, tmp_path):
        registry = self._make_registry(tmp_path)
        uris = [r.uri for r in registry.list_resources()]
        assert "self/emotional-arc" in uris

    def test_read_emotional_memory_resource(self, tmp_path):
        registry = self._make_registry(tmp_path)
        result = registry.read_resource("self/emotional-memory", {"limit": 10})
        assert result["resource"] == "self/emotional-memory"

    def test_read_emotional_arc_resource(self, tmp_path):
        registry = self._make_registry(tmp_path)
        result = registry.read_resource("self/emotional-arc", {"limit": 20})
        assert result["resource"] == "self/emotional-arc"

    def test_existing_relational_self_resource_still_works(self, tmp_path):
        registry = self._make_registry(tmp_path)
        result = registry.read_resource("self/relational-self")
        assert result["resource"] == "self/relational-self"
        assert "snapshot" in result

    def test_existing_coherence_history_resource_still_works(self, tmp_path):
        registry = self._make_registry(tmp_path)
        result = registry.read_resource("self/coherence-history", {"limit": 10})
        assert result["resource"] == "self/coherence-history"

    def test_existing_action_history_resource_still_works(self, tmp_path):
        registry = self._make_registry(tmp_path)
        result = registry.read_resource("self/action-history", {"limit": 10})
        assert result["resource"] == "self/action-history"


class TestMCPToolGetEmotionalInsight:
    def _make_tool_registry(self, tmp_path: Path):
        from ls.agent_shell.mcp_tools import MCPToolRegistry
        from ls.agent_shell.cognitive_state import CognitiveStateBridge

        store_path = tmp_path / "cases.jsonl"
        os.environ["GRAPH_MEMORY_STORE_PATH"] = str(store_path)
        manager = MagicMock()
        manager.get_resonance_snapshot = MagicMock(return_value=[])
        manager.get_alignment_current = MagicMock(return_value={"alignment_state": "ok"})
        cognitive = CognitiveStateBridge(task_manager=manager)
        return MCPToolRegistry(task_manager=manager, cognitive_state=cognitive)

    def test_get_emotional_insight_in_tool_list(self, tmp_path):
        registry = self._make_tool_registry(tmp_path)
        names = [t["name"] for t in registry.list_tools()]
        assert "get_emotional_insight" in names

    def test_get_emotional_insight_returns_expected_keys(self, tmp_path):
        registry = self._make_tool_registry(tmp_path)
        result = registry.call_tool(
            "get_emotional_insight",
            {"question": "How do we relate?", "limit": 5},
        )
        assert result["resource"] == "self/emotional-insight"
        assert "answer" in result
        assert "dominant_tone" in result
        assert "bond_strength" in result
        assert "bond_trend" in result
        assert "causal_trace" in result
        assert "supporting_entries" in result

    def test_get_emotional_insight_causal_trace_has_emotional_summary_state(self, tmp_path):
        store_path = tmp_path / "cases.jsonl"
        store = MemoryGraphStore(store_path)
        _seed_emotional_data(store, n=3)
        registry = self._make_tool_registry(tmp_path)
        result = registry.call_tool(
            "get_emotional_insight",
            {"question": "Are we bonding well?"},
        )
        types = [n["type"] for n in result["causal_trace"]]
        assert "emotional_summary_state" in types

    def test_existing_ask_self_tool_unbroken(self, tmp_path):
        registry = self._make_tool_registry(tmp_path)
        result = registry.call_tool("ask_self", {"question": "How coherent am I?"})
        assert "answer" in result
        assert "causal_trace" in result

    def test_existing_get_cognitive_state_tool_unbroken(self, tmp_path):
        registry = self._make_tool_registry(tmp_path)
        result = registry.call_tool("get_cognitive_state", {})
        assert "resource" in result


# ──────────────────────────────────────────────────────────────
# T-5  get_emotional_insight via CognitiveStateBridge
# ──────────────────────────────────────────────────────────────


class TestGetEmotionalInsight:
    def test_returns_correct_resource_key(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        result = bridge.get_emotional_insight("How is our bond?")
        assert result["resource"] == "self/emotional-insight"

    def test_answer_is_non_empty(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        result = bridge.get_emotional_insight("Are we connected?")
        assert len(result["answer"]) > 0

    def test_answer_does_not_claim_real_feelings(self, tmp_path):
        """No first-person subjective feeling claims — only inferred signals."""
        bridge, store = _make_bridge(tmp_path)
        result = bridge.get_emotional_insight("What do you feel?")
        answer = result["answer"].lower()
        # Should reference inferred/observed signals, not real feelings
        assert any(kw in answer for kw in ("inferred", "signal", "bond", "tone"))
        # Must NOT contain unqualified "I feel" claims
        assert "i feel happy" not in answer
        assert "i am happy" not in answer

    def test_supporting_entries_count_respects_limit(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=20)
        result = bridge.get_emotional_insight("Bond status?", limit=3)
        assert len(result["supporting_entries"]) <= 3

    def test_seeded_data_visible_in_result(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=5)
        result = bridge.get_emotional_insight("How are things?")
        assert result["bond_strength"] >= 0.0
        assert result["dominant_tone"] != ""


# ──────────────────────────────────────────────────────────────
# Emotional intent detection: topic routing vs. sentiment polarity
# ──────────────────────────────────────────────────────────────


class TestEmotionalIntentDetection:
    """Unit-level tests for _is_emotional_question().

    Topic routing must be negation-agnostic and hesitation-robust.
    Negation only belongs in _feedback_matches() (sentiment polarity).
    """

    def setup_method(self):
        from ls.agent_shell.cognitive_state import _is_emotional_question
        self._detect = _is_emotional_question

    # ── Direct keywords (EN) ────────────────────────────────
    def test_en_direct_bond(self):
        assert self._detect("How is our bond?")

    def test_en_direct_feel(self):
        assert self._detect("Do you feel connected to me?")

    def test_en_direct_trust(self):
        assert self._detect("Do you trust our relationship?")

    # ── Negation does NOT suppress topic routing ─────────────
    def test_en_negated_connection_still_relational(self):
        assert self._detect("Why is there no connection between us?")

    def test_ru_negated_closeness_still_relational(self):
        assert self._detect("Почему между нами нет близости?")

    def test_ru_negated_feel_still_relational(self):
        assert self._detect("Ты не чувствуешь связь?")

    def test_ru_negated_trust_still_relational(self):
        assert self._detect("Почему нет доверия?")

    # ── Hesitation markers / interjections ───────────────────
    def test_ru_hm_stripped(self):
        assert self._detect("Хм, наша связь стала теплее?")

    def test_ru_em_stripped(self):
        assert self._detect("Эм... ты чувствуешь, что мы стали ближе?")

    def test_ru_nu_softener(self):
        assert self._detect("Ну, между нами как будто больше доверия?")

    def test_ru_kazbudo_softener(self):
        assert self._detect("Ну, как будто связь стала теплее?")

    def test_ru_mne_kazhetsya(self):
        assert self._detect("Хм, мне кажется, мы стали ближе?")

    # ── Relational speech patterns ────────────────────────────
    def test_ru_mezhdu_nami_pattern(self):
        assert self._detect("Что-то между нами изменилось?")

    def test_ru_nasha_svyaz_pattern(self):
        assert self._detect("Наша связь стала холоднее?")

    def test_en_between_us_pattern(self):
        assert self._detect("Something has changed between us.")

    def test_en_our_bond_pattern(self):
        assert self._detect("Has our bond grown stronger?")

    # ── Specific spec examples ────────────────────────────────
    def test_spec_example_1(self):
        assert self._detect("Какие наши моменты были самыми важными?")

    def test_spec_example_2(self):
        assert self._detect("Как ты себя чувствуешь ко мне?")

    def test_spec_example_3(self):
        assert self._detect("Наша связь стала теплее?")

    # ── Distance / coldness also relational ──────────────────
    def test_ru_distance_is_relational(self):
        assert self._detect("Ты чувствуешь дистанцию между нами?")

    def test_ru_coldness_is_relational(self):
        assert self._detect("Почему стало холоднее между нами?")

    # ── Non-relational questions must NOT trigger ─────────────
    def test_pure_cognitive_question_en(self):
        assert not self._detect("How coherent am I?")

    def test_pure_cognitive_question_ru(self):
        assert not self._detect("Насколько я когерентен?")

    def test_technical_question(self):
        assert not self._detect("What is the current resonance score?")

    def test_task_question(self):
        assert not self._detect("Run the self-consistency check.")


# ──────────────────────────────────────────────────────────────
# Bilingual emotional path: ask_self end-to-end with colloquial speech
# ──────────────────────────────────────────────────────────────


class TestBilingualEmotionalPath:
    def test_russian_warmth_query_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Наша связь стала теплее?")
        # Emotional path was triggered: emotional_layer must be present and populated
        assert "emotional_layer" in result
        # Answer must be in Russian (contains Cyrillic) — bilingual parity
        import re
        assert re.search(r"[а-яёА-ЯЁ]", result["answer"]), (
            f"Russian prompt must yield Russian answer, got: {result['answer']}"
        )

    def test_russian_hesitation_query_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Хм, мне кажется, мы стали ближе?")
        assert "emotional_layer" in result

    def test_russian_negated_topic_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        # "Ты не чувствуешь связь?" — negation in topic, still relational
        result = bridge.ask_self("Ты не чувствуешь связь?")
        assert "emotional_layer" in result

    def test_russian_netu_blizosti_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Почему между нами нет близости?")
        assert "emotional_layer" in result

    def test_russian_moments_query_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Какие моменты между нами были важными?")
        assert "emotional_layer" in result

    def test_colloquial_nu_kazbudo_triggers(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Ну, между нами как будто больше доверия?")
        assert "emotional_layer" in result

    def test_pure_cognitive_question_does_not_pollute_answer(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        result = bridge.ask_self("How coherent am I over the last 3 days?")
        assert "coherence" in result["answer"].lower()

    def test_bond_shift_node_has_confidence(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=4)
        result = bridge.ask_self("Как наша связь?")
        bond_shifts = [n for n in result.get("causal_trace", []) if n.get("type") == "bond_shift"]
        for node in bond_shifts:
            assert "confidence" in node, f"bond_shift node missing confidence: {node}"

    # ── Bilingual answer language tests ───────────────────────
    def test_russian_prompt_gives_russian_answer(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Наша связь стала теплее?")
        # Russian answer must contain Cyrillic characters
        import re
        assert re.search(r"[а-яёА-ЯЁ]", result["answer"]), (
            f"Russian prompt should yield Russian answer, got: {result['answer']}"
        )

    def test_english_prompt_gives_english_answer(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("How is our bond doing?")
        # English answer must NOT be entirely Cyrillic
        import re
        assert re.search(r"[a-zA-Z]", result["answer"]), (
            f"English prompt should yield English answer, got: {result['answer']}"
        )

    def test_get_emotional_insight_russian_answer(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.get_emotional_insight("Как ты ощущаешь нашу связь?")
        import re
        assert re.search(r"[а-яёА-ЯЁ]", result["answer"]), (
            f"Russian insight question should yield Russian answer, got: {result['answer']}"
        )

    def test_get_emotional_insight_english_answer(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.get_emotional_insight("How warm is our bond?")
        import re
        assert re.search(r"[a-zA-Z]", result["answer"]), (
            f"English insight question should yield English answer, got: {result['answer']}"
        )


# ──────────────────────────────────────────────────────────────
# Language detection unit tests
# ──────────────────────────────────────────────────────────────


class TestDetectLanguage:
    def setup_method(self):
        from ls.agent_shell.cognitive_state import _detect_language
        self._detect = _detect_language

    def test_cyrillic_gives_ru(self):
        assert self._detect("Наша связь стала теплее?") == "ru"

    def test_latin_gives_en(self):
        assert self._detect("How is our bond?") == "en"

    def test_empty_gives_en(self):
        assert self._detect("") == "en"

    def test_mixed_cyrillic_latin_gives_ru(self):
        # Any Cyrillic → ru
        assert self._detect("спасибо, very helpful") == "ru"

    def test_digits_only_gives_en(self):
        assert self._detect("12345") == "en"


# ──────────────────────────────────────────────────────────────
# Discourse marker normalisation unit tests
# ──────────────────────────────────────────────────────────────


class TestNormaliseForTopic:
    def setup_method(self):
        from ls.agent_shell.cognitive_state import _normalise_for_topic
        self._norm = _normalise_for_topic

    def test_single_word_marker_stripped(self):
        result = self._norm("Хм, наша связь стала теплее?")
        assert "хм" not in result.split()

    def test_multi_word_marker_stripped(self):
        result = self._norm("Ну, как будто связь стала теплее?")
        assert "будто" not in result
        assert "как будто" not in result

    def test_mne_kazhetsya_stripped(self):
        result = self._norm("Мне кажется, мы стали ближе?")
        assert "мне" not in result.split() or "кажется" not in result.split()

    def test_keywords_survive_stripping(self):
        # After stripping 'хм' and 'ну', 'связь' must remain
        result = self._norm("Хм, ну, наша связь стала теплее?")
        assert "связь" in result

    def test_en_um_stripped(self):
        result = self._norm("Um, how is our bond today?")
        assert "um" not in result.split()

    def test_punctuation_removed(self):
        result = self._norm("Ты не чувствуешь связь?")
        assert "?" not in result
