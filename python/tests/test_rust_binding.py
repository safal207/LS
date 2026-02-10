from pathlib import Path

from python.rust_bridge import RustOptimizer


def _optimizer(tmp_path: Path) -> RustOptimizer:
    db_path = tmp_path / "patterns.db"
    return RustOptimizer(db_path=str(db_path))


def test_rust_binding_available(tmp_path: Path):
    opt = _optimizer(tmp_path)
    assert opt.is_available(), "Rust binding ghostgpt_core must be available"


def test_rust_binding_similarity(tmp_path: Path):
    opt = _optimizer(tmp_path)
    opt.add_patterns([[0.1, 0.2], [0.9, 0.8]])
    res = opt.find_similar([0.1, 0.2], k=1)
    assert isinstance(res, list)
    assert len(res) == 1
