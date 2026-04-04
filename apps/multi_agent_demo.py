#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple multi-agent demo powered by shared causal memory context."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable
import sys

ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from modules.llm.causal_memory import replay_thread
from modules.llm.temporal_graph import get_context_for_question


def get_registry_manager():
    """Placeholder registry manager used by replay_thread in local demo mode."""
    return None


def agent_task(
    agent_id: int,
    question: str,
    handler: Callable[[str], str],
    *,
    registry_manager_getter: Callable[[], object | None] = get_registry_manager,
    sleep_seconds: float = 2.0,
) -> None:
    """Single agent worker that enriches question with shared memory context."""
    thread_id = f"agent-{agent_id}"
    context = get_context_for_question(
        question,
        thread_id,
        replay_loader=lambda: replay_thread(
            thread_id,
            get_registry_manager=registry_manager_getter,
        ),
        max_depth=2,
        max_entries=3,
    )

    full_prompt = f"{context}\n\n{question}" if context else question
    response = handler(full_prompt)

    print(f"[Agent {agent_id}] Ответ: {response[:150]}...")
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)


def run_demo(
    handler: Callable[[str], str],
    *,
    questions: list[str] | None = None,
    registry_manager_getter: Callable[[], object | None] = get_registry_manager,
    sleep_seconds: float = 2.0,
) -> None:
    """Run three agent threads in parallel."""
    demo_questions = questions or [
        "Как оптимизировать базу данных при высокой нагрузке?",
        "Какие есть альтернативы SQL для больших данных?",
        "Как масштабировать API на 1M RPS?",
    ]

    threads: list[threading.Thread] = []
    for index, question in enumerate(demo_questions[:3], start=1):
        thread = threading.Thread(
            target=agent_task,
            args=(index, question, handler),
            kwargs={
                "registry_manager_getter": registry_manager_getter,
                "sleep_seconds": sleep_seconds,
            },
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()


if __name__ == "__main__":
    print("Запуск multi-agent demo...")

    def dummy_handler(prompt: str) -> str:
        return f"Пример ответа на: {prompt[:50]}..."

    run_demo(dummy_handler)
    print("Демо завершено. Проверьте .codex/temporal_graph/graph.json")
