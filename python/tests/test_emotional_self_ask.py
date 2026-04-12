# -*- coding: utf-8 -*-
"""Tests for Phase 2.4 — emotional layer in ask_self, MCP resources, tools.

Covers:
  T-4  ask_self tests (emotional questions, causal_trace emotional nodes)
  T-5  MCP tests (new resources readable, old resources unbroken, new tool works)
  T-7  Safety / boundary: constitution stays primary
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import EmotionalMemoryEntry


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
# Bilingual emotional intent detection
# ──────────────────────────────────────────────────────────────


class TestBilingualEmotionalIntent:
    def test_russian_warmth_query_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Наша связь стала теплее?")
        # Should enter emotional path → answer references tone/bond/inferred
        answer = result["answer"].lower()
        assert any(kw in answer for kw in ("tone", "bond", "inferred", "signal", "warm"))

    def test_russian_relationship_query_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Как ты относишься к нашим отношениям?")
        assert "emotional_layer" in result

    def test_russian_moments_query_triggers_emotional_path(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=3)
        result = bridge.ask_self("Какие моменты были важными?")
        assert "emotional_layer" in result

    def test_pure_cognitive_question_does_not_add_emotional_answer_text(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        result = bridge.ask_self("How coherent am I over the last 3 days?")
        # Without emotional data, the answer should be the base coherence text
        assert "coherence" in result["answer"].lower()

    def test_bond_shift_node_has_confidence(self, tmp_path):
        bridge, store = _make_bridge(tmp_path)
        _seed_emotional_data(store, n=4)
        result = bridge.ask_self("Как наша связь?")
        bond_shifts = [n for n in result.get("causal_trace", []) if n.get("type") == "bond_shift"]
        for node in bond_shifts:
            assert "confidence" in node, f"bond_shift node missing confidence: {node}"
