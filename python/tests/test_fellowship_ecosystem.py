from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from ls.agent_shell.cognitive_state import CognitiveStateBridge
from ls.agent_shell.mcp_resources import MCPResourceRegistry
from ls.agent_shell.mcp_tools import MCPToolRegistry
from modules.council.council_engine import RelationalCouncilEngine
from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import FellowshipProfile, RelationalSelf


def _store(tmp_path: Path) -> MemoryGraphStore:
    path = tmp_path / "graph_memory" / "cases.jsonl"
    os.environ["GRAPH_MEMORY_STORE_PATH"] = str(path)
    return MemoryGraphStore(path)


def _bridge(tmp_path: Path) -> CognitiveStateBridge:
    manager = MagicMock()
    manager.get_resonance_snapshot = MagicMock(return_value=[])
    manager.get_alignment_current = MagicMock(return_value={"alignment_state": "ok"})
    return CognitiveStateBridge(task_manager=manager)


def test_fellowship_registry_group_create_and_join(tmp_path: Path) -> None:
    store = _store(tmp_path)

    group = store.create_fellowship_group(name="Deep Thinkers", visibility="public")
    joined = store.join_fellowship_group(
        fellowship_id=group["fellowship_id"],
        participant_id="user-1",
    )

    assert joined["joined"] is True
    registry = store.get_fellowship_registry()
    assert registry["groups"][0]["name"] == "Deep Thinkers"
    assert "user-1" in registry["trusted"]


def test_collective_self_merge_and_reputation_update(tmp_path: Path) -> None:
    store = _store(tmp_path)

    merged = store.merge_collective_relational_self(
        fellowship_id="f-1",
        member_snapshots={
            "u1": RelationalSelf(
                self_coherence_score=0.9,
                core_nodes=[{"unit_id": "n1", "intent": "support"}],
                emotional_summary={"dominant_tone": "warm"},
                bond_strength=0.8,
            ).to_dict(),
            "u2": RelationalSelf(
                self_coherence_score=0.7,
                core_nodes=[{"unit_id": "n2", "intent": "reflect"}],
                emotional_summary={"dominant_tone": "calm"},
                bond_strength=0.6,
            ).to_dict(),
        },
    )
    assert merged.fellowship_id == "f-1"
    assert merged.collective_coherence_score > 0.0

    profile = store.update_fellowship_reputation(
        participant_id="u1",
        council_contribution_quality=0.9,
        shared_insight_quality=0.8,
        emotional_stability=0.85,
        repair_actions=2,
    )
    assert profile.trust_level in {"co-creator", "steward"}


def test_weighted_vote_prefers_high_reputation_yes() -> None:
    engine = RelationalCouncilEngine()

    outcome = engine.weighted_vote(
        proposal_id="p-1",
        votes=[
            {"participant_id": "a", "vote": "yes"},
            {"participant_id": "b", "vote": "no"},
        ],
        reputation_weights={"a": 1.8, "b": 0.6},
    )

    assert outcome["accepted"] is True
    assert outcome["weighted_yes"] > outcome["weighted_no"]


def test_mcp_fellowship_resources_and_tools(tmp_path: Path) -> None:
    store = _store(tmp_path)
    group = store.create_fellowship_group(name="Deep Thinkers")
    store.upsert_fellowship_profile(
        FellowshipProfile(participant_id="member-1", reputation_score=0.7, trust_level="co-creator")
    )

    bridge = _bridge(tmp_path)
    resources = MCPResourceRegistry(task_manager=MagicMock(), cognitive_state=bridge)
    tools = MCPToolRegistry(task_manager=MagicMock(), cognitive_state=bridge)

    uris = [r.uri for r in resources.list_resources()]
    assert "fellowship/current" in uris
    assert "fellowship/collective-self" in uris
    assert "fellowship/reputation" in uris

    joined = tools.call_tool(
        "join_fellowship",
        {"fellowship_id": group["fellowship_id"], "participant_id": "member-2"},
    )
    assert joined["joined"] is True

    vote = tools.call_tool(
        "vote_on_proposal",
        {
            "proposal_id": "proposal-1",
            "votes": [
                {"participant_id": "member-1", "vote": "yes"},
                {"participant_id": "member-2", "vote": "no"},
            ],
        },
    )
    assert vote["resource"] == "fellowship/vote"

    payload = resources.read_resource("fellowship/reputation")
    assert payload["resource"] == "fellowship/reputation"
    assert len(payload["profiles"]) == 1
