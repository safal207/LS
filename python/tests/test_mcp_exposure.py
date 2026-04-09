# ruff: noqa: E402
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from ls.agent_shell.mcp_resources import MCPResourceRegistry
from ls.agent_shell.mcp_tools import MCPToolRegistry
from ls.agent_shell.testing.runtime_fixture import FixtureRuntime


class CognitiveFixtureRuntime(FixtureRuntime):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resonance_calls = 0

    def get_alignment_current(self) -> dict:
        return {
            "alignment_state": "stable",
            "outcomes": [
                {"cycle_id": "c-1", "guidance_effective": True},
                {"cycle_id": "c-2", "guidance_effective": False},
            ],
            "softening_detected": False,
        }

    def get_omni_last_insight(self) -> dict:
        return {
            "source_question": "monitor current screen",
            "resonance_score": 0.61,
            "metadata": {"provider": "fallback"},
        }

    def get_resonance_snapshot(
        self,
        *,
        top_k: int = 10,
        min_resonance_score: float = 0.3,
    ) -> list[dict]:
        self.resonance_calls += 1
        rows = [
            {
                "unit_id": "runtime-u1",
                "source_question": "runtime",
                "timestamp": "2026-04-09T10:00:00+00:00",
                "resonance_score": 0.88,
                "alignment_score": 0.72,
            }
        ]
        return [r for r in rows if r["resonance_score"] > min_resonance_score][:top_k]


def _new_runtime(tmp_path: Path) -> CognitiveFixtureRuntime:
    return CognitiveFixtureRuntime(
        state_path=tmp_path / "state.json",
        artifact_root=tmp_path / "artifacts",
    )


def _write_resonance_units(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "unit_id": "u1",
            "source_question": "q1",
            "timestamp": "2026-04-08T12:00:00+00:00",
            "resonance_score": 0.87,
            "alignment_score": 0.75,
        },
        {
            "unit_id": "u2",
            "source_question": "q2",
            "timestamp": "2026-04-09T08:00:00+00:00",
            "resonance_score": 0.91,
            "alignment_score": 0.79,
        },
        {
            "unit_id": "u3",
            "source_question": "q3",
            "timestamp": "2026-04-09T09:00:00+00:00",
            "resonance_score": 0.21,
            "alignment_score": 0.50,
        },
    ]
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_mcp_resonance_exposure(tmp_path, monkeypatch):
    runtime = _new_runtime(tmp_path)
    cases_path = tmp_path / "graph_memory" / "cases.jsonl"
    _write_resonance_units(cases_path.with_name("resonance_units.jsonl"))
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(cases_path))

    resources = MCPResourceRegistry(runtime)
    payload = resources.read_resource("resonance/snapshot", {"top_k": 2})

    assert payload["resource"] == "resonance/snapshot"
    assert len(payload["items"]) == 1
    assert payload["items"][0]["unit_id"] == "runtime-u1"
    assert runtime.resonance_calls == 1


def test_mcp_resonance_file_fallback_handles_malformed_json(tmp_path, monkeypatch):
    runtime = FixtureRuntime(
        state_path=tmp_path / "state.json",
        artifact_root=tmp_path / "artifacts",
    )
    cases_path = tmp_path / "graph_memory" / "cases.jsonl"
    resonance_path = cases_path.with_name("resonance_units.jsonl")
    resonance_path.parent.mkdir(parents=True, exist_ok=True)
    resonance_path.write_text(
        '{"unit_id":"ok-1","timestamp":"2026-04-09T10:00:00+00:00","resonance_score":0.9}\n'
        '{malformed_json}\n'
        '{"unit_id":"ok-2","timestamp":"2026-04-09T11:00:00+00:00","resonance_score":0.95}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(cases_path))

    resources = MCPResourceRegistry(runtime)
    payload = resources.read_resource("resonance/snapshot", {"top_k": 5})

    assert [row["unit_id"] for row in payload["items"]] == ["ok-2", "ok-1"]


def test_mcp_alignment_exposure(tmp_path):
    runtime = _new_runtime(tmp_path)
    resources = MCPResourceRegistry(runtime)

    payload = resources.read_resource("alignment/current")

    assert payload["resource"] == "alignment/current"
    assert payload["alignment_state"] == "stable"
    assert payload["softening_detected"] is False
    assert len(payload["outcomes"]) == 2


def test_mcp_omni_exposure(tmp_path, monkeypatch):
    runtime = _new_runtime(tmp_path)
    monkeypatch.setenv("QWEN_OMNI_ENABLED", "1")
    resources = MCPResourceRegistry(runtime)

    payload = resources.read_resource("omni/last-insight")

    assert payload["resource"] == "omni/last-insight"
    assert payload["enabled"] is True
    assert payload["insight"]["resonance_score"] == 0.61


def test_mcp_cognitive_state_summary(tmp_path, monkeypatch):
    runtime = _new_runtime(tmp_path)
    cases_path = tmp_path / "graph_memory" / "cases.jsonl"
    _write_resonance_units(cases_path.with_name("resonance_units.jsonl"))
    monkeypatch.setenv("GRAPH_MEMORY_STORE_PATH", str(cases_path))
    monkeypatch.setenv("QWEN_OMNI_ENABLED", "1")

    tools = MCPToolRegistry(task_manager=runtime)
    payload = tools.call_tool("get_cognitive_state", {"top_k": 1})

    assert payload["resonance"]["resource"] == "resonance/snapshot"
    assert len(payload["resonance"]["items"]) == 1
    assert payload["alignment"]["resource"] == "alignment/current"
    assert payload["omni"]["resource"] == "omni/last-insight"
