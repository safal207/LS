from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_opencode_config_exposes_ls_network_probe_mcp_server() -> None:
    payload = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    server = payload["mcp"]["ls-network-probes"]

    assert server["type"] == "local"
    assert server["command"] == ["python", "-m", "ls.agent_shell.mcp_server"]
    assert server["enabled"] is True
    assert server["environment"]["PYTHONPATH"] == "python;python/modules"
    assert "env" not in server


def test_opencode_config_uses_templates_for_contributor_commands() -> None:
    payload = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8"))
    commands = payload["command"]

    assert set(commands) == {
        "ls-contributor-pack",
        "ls-precision-report",
        "ls-probe-roster",
        "ls-probe-precision",
        "ls-probe-trajectory",
        "ls-probe-conductor-noise",
        "ls-live-pilot",
    }
    for command in commands.values():
        assert command["description"]
        assert command["template"]
        assert "prompt" not in command

    assert "prepare_contributor_pack.py" in commands["ls-contributor-pack"]["template"]
    assert "$ARGUMENTS" in commands["ls-contributor-pack"]["template"]
    assert "prepare_network_precision_contributor_report.py" in commands["ls-precision-report"]["template"]
    assert "$ARGUMENTS" in commands["ls-precision-report"]["template"]
    assert "run_conductor_noise_robustness_demo.py" in commands["ls-probe-conductor-noise"]["template"]
    assert "run_live_model_pilot.py" in commands["ls-live-pilot"]["template"]
    assert "--live" in commands["ls-live-pilot"]["template"]
