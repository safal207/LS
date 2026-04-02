from __future__ import annotations

import json
from pathlib import Path

from python.modules.graph.derived_module_registry import DerivedModuleRegistry
from python.modules.graph.models import DerivedModule

def test_list_modules_file_not_found(tmp_path: Path):
    registry_path = tmp_path / "missing.json"
    registry = DerivedModuleRegistry(path=registry_path)
    assert registry.list_modules() == []

def test_list_modules_invalid_json(tmp_path: Path):
    registry_path = tmp_path / "invalid.json"
    registry_path.write_text("invalid json", encoding="utf-8")
    registry = DerivedModuleRegistry(path=registry_path)
    assert registry.list_modules() == []

def test_list_modules_not_a_list(tmp_path: Path):
    registry_path = tmp_path / "not_a_list.json"
    registry_path.write_text(json.dumps({"key": "value"}), encoding="utf-8")
    registry = DerivedModuleRegistry(path=registry_path)
    assert registry.list_modules() == []

def test_list_modules_valid_list(tmp_path: Path):
    registry_path = tmp_path / "valid.json"
    modules_data = [
        {
            "module_id": "m1",
            "parent_coalition_id": "c1",
            "domain": "test",
            "task_type": "unit-test",
            "policy_type": "simple",
            "policy_text": "allow all",
            "preferred_backend": "local",
            "source_route_key": "r1",
            "trust_score": 0.8,
            "quality_score": 0.9,
            "usage_count": 5,
            "runs": 10,
            "successes": 9,
            "state": "active",
            "care_cycles": 2,
            "last_used_at": "2023-01-01T00:00:00Z",
            "last_reviewed_at": None,
        }
    ]
    registry_path.write_text(json.dumps(modules_data), encoding="utf-8")
    registry = DerivedModuleRegistry(path=registry_path)

    modules = registry.list_modules()
    assert len(modules) == 1
    assert isinstance(modules[0], DerivedModule)
    assert modules[0].module_id == "m1"

def test_list_modules_skips_invalid_items(tmp_path: Path):
    registry_path = tmp_path / "mixed.json"
    modules_data = [
        {"module_id": "m1", "parent_coalition_id": "c1", "domain": "test", "task_type": "unit-test", "policy_type": "simple"},
        "not a dict",
        123
    ]
    registry_path.write_text(json.dumps(modules_data), encoding="utf-8")
    registry = DerivedModuleRegistry(path=registry_path)

    modules = registry.list_modules()
    assert len(modules) == 1
    assert modules[0].module_id == "m1"
