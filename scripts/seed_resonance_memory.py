# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


ROOT = Path(__file__).resolve().parents[1]
PYTHON_DIR = ROOT / "python"
MODULES_DIR = PYTHON_DIR / "modules"
for candidate in (str(ROOT), str(PYTHON_DIR), str(MODULES_DIR)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

from agent.resonance_agent import ResonanceAgent  # noqa: E402
from graph.memory_store import MemoryGraphStore  # noqa: E402
from llm.backends.router import build_llm_backend  # noqa: E402


DEFAULT_THREAD_CONTEXT = (
    "Мы обсуждаем выбор стека, архитектурные компромиссы, стоимость поддержки, "
    "скорость разработки и устойчивость решений. Отвечать без выдуманных цифр и "
    "без фиктивных кейсов."
)

DEFAULT_QUESTIONS = [
    "Почему вы выбрали этот стек для продукта, а не более простой набор технологий?",
    "Какие компромиссы вы приняли при выборе архитектуры и почему они были оправданы?",
    "Если бы команда была вдвое меньше, вы бы всё равно выбрали этот стек? Почему?",
    "Как вы объясните выбор этого стека с точки зрения скорости разработки, стоимости поддержки и риска ошибок?",
    "Какие были альтернативы, почему вы их не выбрали и в каких условиях решение могло бы измениться?",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed resonance memory with strong non-reuse reasoning prompts.")
    parser.add_argument(
        "--thread-context",
        default=DEFAULT_THREAD_CONTEXT,
        help="Shared thread context injected into each run.",
    )
    parser.add_argument(
        "--questions-file",
        default=None,
        help="Optional UTF-8 text file with one question per line.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured JSON instead of text output.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N questions.",
    )
    parser.add_argument(
        "--force-cooperative",
        action="store_true",
        help="Force the cooperative local>gonka>mimo route instead of relying on selector choice.",
    )
    return parser.parse_args()


def _load_questions(path: str | None) -> list[str]:
    if not path:
        return list(DEFAULT_QUESTIONS)
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"questions file not found: {file_path}")
    questions = [
        line.strip()
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return questions or list(DEFAULT_QUESTIONS)


def main() -> int:
    args = _parse_args()
    questions = _load_questions(args.questions_file)
    if args.limit is not None:
        questions = questions[: max(1, int(args.limit))]
    backend = build_llm_backend()
    agent = ResonanceAgent(
        llm_backend=backend,
        orientation=args.thread_context,
    )
    store = MemoryGraphStore()
    before_units = len(store.list_resonance_units())

    results: list[dict[str, object]] = []
    if not args.json:
        print(f"seeding.questions = {len(questions)}", flush=True)
        print(f"resonance.units.before = {before_units}", flush=True)
        print(f"force.cooperative = {args.force_cooperative}", flush=True)
        print("progress = starting", flush=True)
        print("", flush=True)

    forced_goal_vector = {
        "style": "structured",
        "strategy_bias": "cooperative_reasoning",
        "target_relevance": 0.8,
        "target_thread_alignment": 0.8,
        "target_hallucination_max": 0.2,
        "target_latency_ms": 20000.0,
    }
    for index, question in enumerate(questions, start=1):
        if not args.json:
            print(f"[{index}/{len(questions)}] start = {question}", flush=True)
        item = {
            "type": "question",
            "text": question,
            "clean_text": question,
            "thread_context": args.thread_context,
            "confidence": 1.0,
            "source": "seed_resonance_memory",
        }
        if args.force_cooperative:
            item["_path_selection"] = {
                "route_key": "full_run>local>gonka>mimo",
                "selected_backend": "cooperative",
                "reason": "forced-cooperative-seed",
                "exploration_used": False,
                "pheromone_weight": 0.0,
            }
            item["_network_plan"] = {
                "mode": "full_run",
                "route_key": "full_run>local>gonka>mimo",
                "reason": "forced-cooperative-seed",
                "confidence": 1.0,
                "goal_vector": forced_goal_vector,
                "need_profile": {
                    "priority": "deep_reasoning",
                    "route_bias": "cooperative_only",
                    "compute_budget": 1.0,
                },
            }
            agent._control_center = None  # type: ignore[attr-defined]
        result = agent.process_item(item)
        entry = {
            "index": index,
            "question": question,
            "route_key": result.get("orientation_route_key") or result.get("route_key"),
            "was_reused": result.get("was_reused"),
            "provider": result.get("llm_provider"),
            "model": result.get("llm_model"),
            "goal_alignment_score": result.get("goal_alignment_score"),
            "resonance_score": result.get("resonance_score"),
            "output": result.get("final_output"),
        }
        results.append(entry)
        if not args.json:
            print(
                "[{idx}/{total}] done = route={route} reused={reused} provider={provider} goal_alignment={goal} resonance={resonance}".format(
                    idx=index,
                    total=len(questions),
                    route=entry["route_key"],
                    reused=entry["was_reused"],
                    provider=entry["provider"],
                    goal=entry["goal_alignment_score"],
                    resonance=entry["resonance_score"],
                ),
                flush=True,
            )
            print("", flush=True)

    after_units = len(store.list_resonance_units())
    payload = {
        "questions": len(questions),
        "resonance_units_before": before_units,
        "resonance_units_after": after_units,
        "resonance_units_added": max(0, after_units - before_units),
        "results": results,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"resonance.units.before = {before_units}")
    print(f"resonance.units.after = {after_units}")
    print(f"resonance.units.added = {payload['resonance_units_added']}")
    print("")
    for entry in results:
        print(f"[{entry['index']}] question = {entry['question']}")
        print(f"[{entry['index']}] route = {entry['route_key']}")
        print(f"[{entry['index']}] reused = {entry['was_reused']}")
        print(f"[{entry['index']}] provider = {entry['provider']}  model = {entry['model']}")
        print(f"[{entry['index']}] goal_alignment = {entry['goal_alignment_score']}  resonance = {entry['resonance_score']}")
        print(f"[{entry['index']}] output = {entry['output']}")
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
