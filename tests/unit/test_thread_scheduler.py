from __future__ import annotations

from datetime import datetime, timezone

from codex.cognitive.scheduler import ThreadScheduler
from codex.cognitive.thread import CognitiveThread
from codex.cognitive.workspace import GlobalFrame


def test_thread_scheduler_updates_attention_and_selects_active() -> None:
    scheduler = ThreadScheduler()
    thread = CognitiveThread(thread_id="t1", priority=2.0, attention_weight=0.5)
    scheduler.register_thread(thread)

    frame = GlobalFrame(
        thread_id="t1",
        task_type="chat",
        system_state="stable",
        self_model={},
        affective={},
        identity={},
        capu_features={},
        decision={},
        memory_refs={},
        narrative_refs={},
        merit_scores={"focus": 0.8},
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    distribution = scheduler.update_attention(frame)
    assert distribution["t1"] == 1.0
    assert scheduler.select_active_thread() == "t1"


def test_thread_scheduler_syncs_threads() -> None:
    scheduler = ThreadScheduler()
    thread = CognitiveThread(thread_id="t2", priority=1.0)

    scheduler.sync_threads([thread])

    assert scheduler.select_active_thread() == "t2"
