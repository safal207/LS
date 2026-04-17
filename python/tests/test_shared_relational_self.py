# ruff: noqa: E402
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from modules.graph.memory_store import MemoryGraphStore
from modules.graph.models import RelationalSelf
from ls.agent_shell.cognitive_state import CognitiveStateBridge
from ls.agent_shell.mcp_resources import MCPResourceRegistry
from ls.agent_shell.mcp_tools import MCPToolRegistry


def _store(tmp_path: Path) -> MemoryGraphStore:
    path = tmp_path / "graph_memory" / "cases.jsonl"
    os.environ["GRAPH_MEMORY_STORE_PATH"] = str(path)
    store = MemoryGraphStore(path)
    store._atomic_write_json(
        path.with_name("relational_self.json"),
        RelationalSelf(
            core_nodes=[
                {
                    "unit_id": "raw-unit-1",
                    "intent": "support",
                    "resonance_score": 0.81,
                    "alignment_score": 0.73,
                }
            ],
            emotional_summary={"dominant_tone": "calm", "bond_strength": 0.64, "notes": "private"},
        ).to_dict(),
    )
    return store


def _bridge(tmp_path: Path) -> CognitiveStateBridge:
    _store(tmp_path)
    manager = MagicMock()
    manager.get_resonance_snapshot = MagicMock(return_value=[])
    manager.get_alignment_current = MagicMock(return_value={"alignment_state": "ok"})
    return CognitiveStateBridge(task_manager=manager)


def test_share_self_anonymizes_nodes_and_updates_registry(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = store.share_self(partial=True, recipients=["fellow-1", "council"], consent_mode="allow")

    assert result["shared"] is True
    snapshot = result["snapshot"]
    assert snapshot["recipients"] == ["fellow-1", "council"]
    assert snapshot["core_nodes"][0]["node_id"].startswith("anon:")
    assert "unit_id" not in snapshot["core_nodes"][0]
    assert "notes" not in snapshot["emotional_summary"]
    assert "fellow-1" in store.get_fellowship_registry()["trusted"]


def test_share_self_consent_deny_is_blocked_and_audited(tmp_path: Path) -> None:
    store = _store(tmp_path)

    result = store.share_self(partial=True, recipients=["fellow-2"], consent_mode="deny")

    assert result["shared"] is False
    audit = store.get_sharing_audit(limit=5)
    assert any(row.get("event") == "share_self_denied" for row in audit)


def test_accept_shared_self_selective_merge_updates_relational_self(tmp_path: Path) -> None:
    store = _store(tmp_path)

    accepted = store.accept_shared_self(
        shared_payload={
            "shared_id": "incoming-1",
            "emotional_summary": {
                "dominant_tone": "supportive",
                "bond_strength": 0.77,
                "private_notes": "should be dropped",
            },
        },
        selective_merge=True,
    )

    assert accepted["accepted"] is True
    refreshed = store.get_relational_self()
    assert refreshed.emotional_summary.get("dominant_tone") in {"calm", "supportive"}
    assert "shared:private_notes" not in refreshed.emotional_summary


def test_mcp_shared_self_resource_exists_and_is_readable(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    registry = MCPResourceRegistry(task_manager=MagicMock(), cognitive_state=bridge)

    uris = [r.uri for r in registry.list_resources()]
    assert "shared-self/current" in uris
    payload = registry.read_resource("shared-self/current")
    assert payload["resource"] == "shared-self/current"
    assert "snapshot" in payload


def test_mcp_tools_expose_phase3_shared_self_ops(tmp_path: Path) -> None:
    bridge = _bridge(tmp_path)
    tools = MCPToolRegistry(task_manager=MagicMock(), cognitive_state=bridge)

    names = [row["name"] for row in tools.list_tools()]
    assert "propose_shared_insight" in names
    assert "accept_shared_self" in names

    proposal = tools.call_tool(
        "propose_shared_insight",
        {
            "recipient": "fellow-1",
            "source_node_id": "a",
            "target_node_id": "b",
            "relation_type": "reinforces",
            "strength": 0.6,
            "rationale": "shared arc alignment",
        },
    )
    assert proposal["resource"] == "shared-self/proposal"
    assert proposal["proposal"]["status"] == "proposed"

    accepted = tools.call_tool(
        "accept_shared_self",
        {
            "shared_payload": {
                "shared_id": "peer-1",
                "emotional_summary": {"dominant_tone": "reflective", "bond_strength": 0.71},
            },
            "selective_merge": True,
        },
    )
    assert accepted["resource"] == "shared-self/accept"
    assert accepted["accepted"] is True
