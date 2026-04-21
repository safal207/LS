#!/usr/bin/env python3
"""Quick project health-check for the current LS repository."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON_ROOT = ROOT / "python"
MODULES_ROOT = PYTHON_ROOT / "modules"


def bootstrap_paths() -> None:
    for path in (ROOT, PYTHON_ROOT, MODULES_ROOT):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def safe_text(value: object) -> str:
    text = str(value)
    return text.encode("ascii", errors="replace").decode("ascii")


def check_files() -> list[tuple[str, bool, str]]:
    expected = [
        "README.md",
        "pyproject.toml",
        "requirements.txt",
        "apps/console/main.py",
        "python/modules/agent/resonance_agent.py",
        "python/modules/agent/loop.py",
        "python/modules/graph/memory_store.py",
        "python/tests/test_coordination_output_contract.py",
    ]
    results: list[tuple[str, bool, str]] = []
    for rel_path in expected:
        path = ROOT / rel_path
        results.append((rel_path, path.exists(), "present" if path.exists() else "missing"))
    return results


def check_imports() -> list[tuple[str, bool, str]]:
    targets = [
        ("modules.config", "core config"),
        ("modules.agent.resonance_agent", "resonance agent"),
        ("modules.agent.loop", "agent loop"),
        ("modules.graph.memory_store", "memory store"),
        ("modules.agent.coordination_advisory_summary", "coordination summary"),
    ]
    results: list[tuple[str, bool, str]] = []
    for module_name, label in targets:
        try:
            importlib.import_module(module_name)
            results.append((label, True, module_name))
        except Exception as exc:  # pragma: no cover - diagnostic script
            results.append((label, False, f"{module_name}: {exc.__class__.__name__}: {exc}"))
    return results


def check_config() -> list[tuple[str, bool, str]]:
    try:
        from modules import config
    except Exception as exc:  # pragma: no cover - diagnostic script
        return [("config", False, f"import failed: {exc.__class__.__name__}: {exc}")]

    values = [
        ("AGENT_ENABLED", getattr(config, "AGENT_ENABLED", None)),
        ("TEMPORAL_ENABLED", getattr(config, "TEMPORAL_ENABLED", None)),
        ("GRAPH_TRAIL_ENABLED", getattr(config, "GRAPH_TRAIL_ENABLED", None)),
        ("GRAPH_COALITION_ENABLED", getattr(config, "GRAPH_COALITION_ENABLED", None)),
        ("GRAPH_CARE_CYCLES_ENABLED", getattr(config, "GRAPH_CARE_CYCLES_ENABLED", None)),
    ]
    return [(name, True, json.dumps(value)) for name, value in values]


def check_runtime_probe() -> list[tuple[str, bool, str]]:
    try:
        from modules.agent.resonance_agent import ResonanceAgent

        agent = ResonanceAgent(anchor=[], llm_fn=None)
        result = agent._build_output(
            {
                "text": "status probe",
                "_why_strategy": {},
                "_copilot_output": {},
                "_intent": {},
                "_why": {},
                "_llm_backend": {},
                "_path_selection": {"route_key": "r1", "reason": "status-probe"},
                "_graph_runtime": {"mode": "reuse"},
                "_trail_route": {},
                "_coalition": {},
                "_derived_module": {},
                "_care_cycle": {},
                "_network_plan": {},
                "_adequacy_report": {},
                "_observer_report": {},
                "_alignment_report": {},
                "_alignment_outcome": {},
                "_resonance_score": 0.5,
            },
            final_output="ok",
            generation_time=0.01,
            cycle_id="status-probe",
        )
        required = [
            "collective_coordination_snapshot",
            "bridge_stabilization_order",
            "bridge_playbook_advisory",
            "coordination_advisory_summary",
            "relational_edge_update_preview",
        ]
        missing = [key for key in required if key not in result]
        if missing:
            return [("build_output", False, f"missing keys: {', '.join(missing)}")]
        return [("build_output", True, "core output contract present")]
    except Exception as exc:  # pragma: no cover - diagnostic script
        return [("build_output", False, f"probe failed: {exc.__class__.__name__}: {exc}")]


def check_ollama() -> list[tuple[str, bool, str]]:
    try:
        requests = importlib.import_module("requests")
    except Exception:
        return [("ollama", False, "requests not installed")]

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code != 200:
            return [("ollama", False, f"http {response.status_code}")]
        payload = response.json()
        models = payload.get("models") or []
        return [("ollama", True, f"reachable, models={len(models)}")]
    except Exception as exc:  # pragma: no cover - diagnostic script
        return [("ollama", False, f"unreachable: {exc.__class__.__name__}: {exc}")]


def render_section(title: str, rows: list[tuple[str, bool, str]]) -> int:
    print(safe_text(title))
    failures = 0
    for name, ok, detail in rows:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {safe_text(name)}: {safe_text(detail)}")
        if not ok:
            failures += 1
    print()
    return failures


def main() -> int:
    bootstrap_paths()
    print("LS Project Status")
    print("=" * 48)
    print(f"Root: {safe_text(ROOT)}")
    print()

    failures = 0
    failures += render_section("Files", check_files())
    failures += render_section("Imports", check_imports())
    failures += render_section("Config", check_config())
    failures += render_section("Runtime Probe", check_runtime_probe())
    failures += render_section("Optional Services", check_ollama())

    if failures == 0:
        print("Summary: healthy")
        return 0

    print(f"Summary: issues detected ({failures})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
