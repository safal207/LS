# ruff: noqa: E402
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.memory_store import MemoryGraphStore
from graph.models import ResonanceKnowledgeUnit


def test_memory_store_two_instances_same_path_produce_valid_jsonl(tmp_path):
    cases_path = tmp_path / "cases.jsonl"
    store_a = MemoryGraphStore(cases_path)
    store_b = MemoryGraphStore(cases_path)

    def _writer(store: MemoryGraphStore, prefix: str) -> None:
        for idx in range(20):
            unit = ResonanceKnowledgeUnit(
                source_question=f"{prefix}-question-{idx}",
                resonance_score=0.7,
                metadata={"writer": prefix, "idx": idx},
            )
            store.store_resonance_unit(unit)

    t1 = threading.Thread(target=_writer, args=(store_a, "a"))
    t2 = threading.Thread(target=_writer, args=(store_b, "b"))
    t1.start()
    t2.start()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    units = store_a.list_resonance_units()
    assert len(units) == 40

    resonance_path = cases_path.with_name("resonance_units.jsonl")
    raw_lines = resonance_path.read_text(encoding="utf-8").splitlines()
    assert len(raw_lines) == 40
    for raw in raw_lines:
        parsed = json.loads(raw)
        assert "source_question" in parsed
        assert "unit_id" in parsed
