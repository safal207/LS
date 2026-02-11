import importlib
import importlib.util
import pathlib
import sys

import pytest

import rust_bridge


EXPECTED_EXPORTS = ["MemoryManager", "PatternMatcher", "Storage", "Transport"]


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def _load_ghostgpt_core():
    """
    Import ghostgpt_core using the default import path, or from the Rust build
    artifact if only libghostgpt_core.so is present.
    """
    try:
        return importlib.import_module("ghostgpt_core")
    except ImportError:
        artifact_path = _repo_root() / "rust_core" / "target" / "release" / "libghostgpt_core.so"
        if not artifact_path.exists():
            raise

        spec = importlib.util.spec_from_file_location("ghostgpt_core", artifact_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not create import spec for {artifact_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules["ghostgpt_core"] = module
        spec.loader.exec_module(module)
        return module


@pytest.fixture(scope="module")
def ghostgpt_core_module():
    try:
        return _load_ghostgpt_core()
    except ImportError as exc:
        pytest.fail(f"Rust module 'ghostgpt_core' not found. Build might have failed: {exc}")


def test_ghostgpt_core_import(ghostgpt_core_module):
    """Проверяем, что модуль ghostgpt_core может быть импортирован."""
    assert ghostgpt_core_module is not None


def test_exported_classes_available(ghostgpt_core_module):
    """Проверяем доступность обязательных Rust-экспортов."""
    module_exports = set(dir(ghostgpt_core_module))

    # В Rust-модуле транспорт экспортирован как пара TransportConfig/TransportHandle.
    if "Transport" not in module_exports:
        module_exports.add("Transport")
        assert {"TransportConfig", "TransportHandle"}.issubset(set(dir(ghostgpt_core_module)))

    missing = [name for name in EXPECTED_EXPORTS if name not in module_exports]
    assert not missing, f"Missing exports in ghostgpt_core: {missing}"


def test_basic_instantiation(ghostgpt_core_module, tmp_path):
    """Проверяем, что можно создать ключевые Rust-объекты."""
    storage = ghostgpt_core_module.Storage(str(tmp_path / "bridge.db"))
    matcher = ghostgpt_core_module.PatternMatcher()
    manager = ghostgpt_core_module.MemoryManager(100)

    assert storage is not None
    assert matcher is not None
    assert manager is not None


def test_fallback_mechanism(monkeypatch):
    """Если Rust не загружен, RustOptimizer работает в fallback-режиме."""
    monkeypatch.setattr(rust_bridge, "ghostgpt_core", None)

    optimizer = rust_bridge.RustOptimizer()

    assert optimizer.is_available() is False
    assert optimizer.cache_pattern("k", [0.1, 0.2]) is False
    assert optimizer.find_similar([0.1, 0.2], k=1) == []
    assert optimizer.save_to_storage("k", b"v") is False
    assert optimizer.load_from_storage("k") is None
    assert optimizer.optimize_memory() == 0
    assert optimizer.transport_available() is False
    assert optimizer.open_channel("test") is None
