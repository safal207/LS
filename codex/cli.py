from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from codex.benchmark import BenchmarkReport, BenchmarkRunner
from codex.registry import build_default_registry


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex", description="Codex CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    models_parser = subparsers.add_parser("models", help="Manage local models")
    models_sub = models_parser.add_subparsers(dest="models_command", required=True)

    models_sub.add_parser("list", help="List registered models")

    info_parser = models_sub.add_parser("info", help="Show model info")
    info_parser.add_argument("name")

    load_parser = models_sub.add_parser("load", help="Load a model")
    load_parser.add_argument("name")

    unload_parser = models_sub.add_parser("unload", help="Unload a model")
    unload_parser.add_argument("name")

    benchmark_parser = subparsers.add_parser("benchmark", help="Run model benchmarks")
    benchmark_sub = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)

    benchmark_run = benchmark_sub.add_parser("run", help="Benchmark a single model")
    benchmark_run.add_argument("name")

    benchmark_sub.add_parser("all", help="Benchmark all registered models")

    benchmark_report = benchmark_sub.add_parser("report", help="Show benchmark report")
    benchmark_report.add_argument("name")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    registry = build_default_registry()

    if args.command == "models":
        if args.models_command == "list":
            for line in registry.format_list():
                print(line)
            return 0
        if args.models_command == "info":
            info = registry.info(args.name)
            print(json.dumps(info, indent=2, sort_keys=True))
            return 0
        if args.models_command == "load":
            registry.load(args.name)
            print(f"Loaded {args.name}")
            return 0
        if args.models_command == "unload":
            registry.unload(args.name)
            print(f"Unloaded {args.name}")
            return 0
    if args.command == "benchmark":
        runner = BenchmarkRunner(registry)
        if args.benchmark_command == "run":
            result = runner.run(args.name)
            print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
            return 0
        if args.benchmark_command == "all":
            results = runner.run_all()
            print(json.dumps([result.to_dict() for result in results], indent=2, sort_keys=True))
            return 0
        if args.benchmark_command == "report":
            report = BenchmarkReport(runner.results_dir)
            print(json.dumps(report.model_report(args.name), indent=2, sort_keys=True))
            return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
