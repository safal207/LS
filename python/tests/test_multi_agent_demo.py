# -*- coding: utf-8 -*-
from apps.multi_agent_demo import run_demo


class FakeRegistryManager:
    def __init__(self, entries):
        self.entries = entries
        self.requested_threads = []

    def replay_thread(self, thread_id):
        self.requested_threads.append(thread_id)
        return self.entries


def test_multi_agent_no_crash():
    prompts = []

    def handler(prompt: str) -> str:
        prompts.append(prompt)
        return "ok"

    run_demo(handler, sleep_seconds=0)

    assert len(prompts) == 3
    assert all(prompt for prompt in prompts)


def test_shared_memory_used():
    prompts = []

    entries = [
        {
            "ts": "2026-02-25T10:00:01Z",
            "cause": "database pool exhausted on postgres",
            "solution": "increase pool and optimize query plan",
            "ltp_trace": {"thread_id": "agent-1"},
            "lri_core": {"resonance_map": {"focus": 0.85}},
        },
        {
            "ts": "2026-02-25T10:00:02Z",
            "cause": "postgres latency under high traffic",
            "solution": "shard reads and add pooling limits",
            "ltp_trace": {"thread_id": "agent-2"},
            "lri_core": {"resonance_map": {"focus": 0.81}},
        },
        {
            "ts": "2026-02-25T10:00:03Z",
            "cause": "api scaling bottleneck in request queue",
            "solution": "add horizontal workers and backpressure",
            "ltp_trace": {"thread_id": "agent-3"},
            "lri_core": {"resonance_map": {"focus": 0.79}},
        },
    ]
    fake_registry = FakeRegistryManager(entries)

    def handler(prompt: str) -> str:
        prompts.append(prompt)
        return "ok"

    run_demo(
        handler,
        registry_manager_getter=lambda: fake_registry,
        sleep_seconds=0,
        questions=[
            "Как оптимизировать базу данных при высокой нагрузке?",
            "Как уменьшить задержки postgres?",
            "Как масштабировать API?",
        ],
    )

    assert len(prompts) == 3
    assert fake_registry.requested_threads
    assert any("[Из памяти системы — похожие ситуации]" in prompt for prompt in prompts)
