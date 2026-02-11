import importlib
import importlib.machinery
import importlib.util
import pathlib
import sys

import pytest

import rust_bridge


def _repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def _artifact_candidates() -> list[pathlib.Path]:
    release_dir = _repo_root() / "rust_core" / "target" / "release"
    names = []
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        names.append(f"ghostgpt_core{suffix}")
        names.append(f"libghostgpt_core{suffix}")
    return [release_dir / name for name in names]


def _load_ghostgpt_core():
    try:
        return importlib.import_module("ghostgpt_core")
    except ImportError:
        for artifact_path in _artifact_candidates():
            if not artifact_path.exists():
                continue

            spec = importlib.util.spec_from_file_location("ghostgpt_core", artifact_path)
            if spec is None or spec.loader is None:
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules["ghostgpt_core"] = module
            spec.loader.exec_module(module)
            return module

        raise


@pytest.fixture
def optimizer_pair(monkeypatch, tmp_path):
    try:
        core_module = _load_ghostgpt_core()
    except ImportError:
        pytest.skip("Rust core not available, cannot run API parity tests.")

    monkeypatch.setattr(rust_bridge, "ghostgpt_core", core_module)
    rust_optimizer = rust_bridge.RustOptimizer(db_path=str(tmp_path / "parity.db"))
    assert rust_optimizer.is_available() is True

    fallback_optimizer = rust_bridge.RustOptimizer(db_path=str(tmp_path / "fallback.db"))
    fallback_optimizer.available = False
    fallback_optimizer.transport = None

    return rust_optimizer, fallback_optimizer


def assert_same_type(rust_value, fallback_value):
    assert type(rust_value) is type(fallback_value), (
        f"Type mismatch: {type(rust_value)} vs {type(fallback_value)}"
    )


def test_find_similar_parity(optimizer_pair):
    rust_optimizer, fallback_optimizer = optimizer_pair

    rust_result = rust_optimizer.find_similar([1.0, 0.0], k=1)
    fallback_result = fallback_optimizer.find_similar([1.0, 0.0], k=1)

    assert_same_type(rust_result, fallback_result)
    assert isinstance(rust_result, list)
    assert isinstance(fallback_result, list)

    assert rust_result == []
    assert fallback_result == []


def test_list_sessions_parity(optimizer_pair):
    rust_optimizer, fallback_optimizer = optimizer_pair

    rust_result = rust_optimizer.list_sessions()
    fallback_result = fallback_optimizer.list_sessions()

    assert_same_type(rust_result, fallback_result)
    assert isinstance(rust_result, list)
    assert isinstance(fallback_result, list)

    assert rust_result == []
    assert fallback_result == []


def test_load_from_storage_parity(optimizer_pair):
    rust_optimizer, fallback_optimizer = optimizer_pair

    rust_result = rust_optimizer.load_from_storage("missing-key")
    fallback_result = fallback_optimizer.load_from_storage("missing-key")

    assert_same_type(rust_result, fallback_result)
    assert rust_result is None
    assert fallback_result is None


def test_open_channel_parity(optimizer_pair):
    rust_optimizer, fallback_optimizer = optimizer_pair

    rust_result = rust_optimizer.open_channel("missing-kind")
    fallback_result = fallback_optimizer.open_channel("missing-kind")

    assert_same_type(rust_result, fallback_result)
    assert rust_result is None
    assert fallback_result is None


def test_receive_parity(optimizer_pair):
    rust_optimizer, fallback_optimizer = optimizer_pair

    rust_result = rust_optimizer.receive(999999)
    fallback_result = fallback_optimizer.receive(999999)

    assert_same_type(rust_result, fallback_result)
    assert rust_result is None
    assert fallback_result is None
