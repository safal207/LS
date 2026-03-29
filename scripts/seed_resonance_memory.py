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
    backend = build_llm_backend()
    agent = ResonanceAgent(
        llm_backend=backend,
        orientation=args.thread_context,
    )
    store = MemoryGraphStore()
    before_units = len(store.list_resonance_units())

    results: list[dict[str, object]] = []
    for index, question in enumerate(questions, start=1):
        item = {
            "type": "question",
            "text": question,
            "clean_text": question,
            "thread_context": args.thread_context,
            "confidence": 1.0,
            "source": "seed_resonance_memory",
        }
        result = agent.process_item(item)
        results.append(
            {
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
        )

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
