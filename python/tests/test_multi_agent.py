import json
import os
import threading
import time

from modules.llm.causal_memory import with_file_lock
from modules.llm.temporal_graph import merge_or_append_entry


def test_flock_prevents_race_condition(tmp_path):
    file_path = str(tmp_path / "memory.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"items": []}, f)

    def writer(index: int) -> None:
        def _critical() -> None:
            with open(file_path, "r", encoding="utf-8") as src:
                payload = json.load(src)
            payload["items"].append(index)
            with open(file_path, "w", encoding="utf-8") as dst:
                json.dump(payload, dst)

        with_file_lock(file_path, _critical, timeout=1.5)

    t1 = threading.Thread(target=writer, args=(1,))
    t2 = threading.Thread(target=writer, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    with open(file_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    assert sorted(payload["items"]) == [1, 2]


def test_consent_merges_similar_nodes():
    graph = {
        "nodes": {
            "thread-old:0": {
                "id": "thread-old:0",
                "cause": "database timeout while writing task",
                "solution": "retry write with backoff",
                "ts": "2026-01-01T00:00:00+00:00",
                "thread_id": "thread-old",
                "lri_core": {},
                "edges": [],
            }
        },
        "edges": [],
    }

    merge_or_append_entry(
        {
            "cause": "database timeout while writing user task",
            "solution": "retry write with exponential backoff",
            "ltp_trace": {"thread_id": "thread-new"},
            "ts": "2026-01-01T00:01:00+00:00",
        },
        graph,
    )

    assert len(graph["nodes"]) == 1
    merged = graph["nodes"]["thread-old:0"]
    assert "database timeout while writing task" in merged["cause"]
    assert "database timeout while writing user task" in merged["cause"]


def test_consent_creates_new_for_unique():
    graph = {"nodes": {}, "edges": []}

    merge_or_append_entry(
        {
            "cause": "first unique issue",
            "solution": "first unique fix",
            "ltp_trace": {"thread_id": "thread-a"},
            "ts": "2026-01-01T00:00:00+00:00",
        },
        graph,
    )
    merge_or_append_entry(
        {
            "cause": "completely different networking incident",
            "solution": "switch transport channel",
            "ltp_trace": {"thread_id": "thread-b"},
            "ts": "2026-01-01T00:02:00+00:00",
        },
        graph,
    )

    assert len(graph["nodes"]) == 2


def test_flock_recovers_from_stale_lock(tmp_path):
    file_path = str(tmp_path / "memory.yaml")
    lock_path = file_path + ".lock"

    # Создаём stale lock вручную (симуляция краша процесса)
    with open(lock_path, "w") as f:
        f.write("stale")

    start = time.monotonic()
    result = []
    with_file_lock(file_path, lambda: result.append(1), timeout=0.5)
    duration = time.monotonic() - start

    assert result == [1]
    assert not os.path.exists(lock_path)
    assert duration >= 0.01
    assert duration < 1.0
