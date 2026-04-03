# -*- coding: utf-8 -*-
"""CLI entry point for the runtime status snapshot.

Usage::

    python -m graph.status
    python -m graph.status --data-dir /path/to/data/graph_memory
    python -m graph.status --compact

Prints a JSON snapshot of graph memory, care cycle, and omni worker
to stdout.  Exit code 0 on success, 1 on error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_snapshot(data_dir: Path) -> dict:
    from graph.derived_module_registry import DerivedModuleRegistry
    from graph.memory_store import MemoryGraphStore
    from graph.runtime_snapshot import collect_runtime_status

    store = MemoryGraphStore(data_dir / "cases.jsonl")
    registry = DerivedModuleRegistry(data_dir / "derived_modules.json")
    snap = collect_runtime_status(graph_store=store, registry=registry)
    return snap.to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m graph.status",
        description="Print a machine-readable runtime status snapshot.",
    )
    parser.add_argument(
        "--data-dir",
        default=str(Path.cwd() / "data" / "graph_memory"),
        help="Path to the graph_memory data directory (default: ./data/graph_memory)",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Output compact JSON (no indentation).",
    )
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    try:
        snapshot = _build_snapshot(data_dir)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1

    indent = None if args.compact else 2
    print(json.dumps(snapshot, ensure_ascii=False, indent=indent))
    return 0


if __name__ == "__main__":
    sys.exit(main())
