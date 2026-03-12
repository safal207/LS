import os
import sys
from pathlib import Path

from modules.shared.bootstrap import setup_runtime_paths, bootstrap_app


def test_setup_runtime_paths_adds_expected_paths(monkeypatch):
    monkeypatch.setattr(sys, "path", [])

    root = setup_runtime_paths(str(Path("/workspace/LS/apps/console/main.py")))

    assert root == Path("/workspace/LS")
    assert str(root / "python") in sys.path
    assert str(root / "python" / "modules") in sys.path
    assert str(root) in sys.path


def test_bootstrap_app_sets_ls_app_env(monkeypatch):
    monkeypatch.delenv("LS_APP", raising=False)

    cfg = bootstrap_app(str(Path("/workspace/LS/apps/console/main.py")), "console")

    assert os.environ["LS_APP"] == "console"
    assert isinstance(cfg, dict)
    assert "llm" in cfg
