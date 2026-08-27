from __future__ import annotations

import argparse
from pathlib import Path

from review_benchmark_v0_2_common import load_json, write_json
from review_benchmark_v0_2_scoring import score
from review_benchmark_v0_2_seal import seal_report


def main() -> int:
    parser = argparse.ArgumentParser(description="LS review benchmark v0.2 provenance-aware tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    seal = sub.add_parser("seal")
    seal.add_argument("--case", type=Path, required=True)
    seal.add_argument("--binding", type=Path, required=True)
    seal.add_argument("--report", type=Path, required=True)
    seal.add_argument("--repo-root", type=Path, default=Path.cwd())
    seal.add_argument("--out", type=Path, required=True)

    scoring = sub.add_parser("score")
    scoring.add_argument("--case", type=Path, required=True)
    scoring.add_argument("--frontier-binding", type=Path, required=True)
    scoring.add_argument("--frontier-report", type=Path, required=True)
    scoring.add_argument("--frontier-seal", type=Path, required=True)
    scoring.add_argument("--ls-binding", type=Path, required=True)
    scoring.add_argument("--ls-report", type=Path, required=True)
    scoring.add_argument("--ls-seal", type=Path, required=True)
    scoring.add_argument("--adjudication", type=Path, required=True)
    scoring.add_argument("--repo-root", type=Path, default=Path.cwd())
    scoring.add_argument("--out", type=Path, required=True)

    args = parser.parse_args()
    case = load_json(args.case)
    if args.command == "seal":
        write_json(
            args.out,
            seal_report(case, load_json(args.binding), load_json(args.report), args.repo_root),
        )
        return 0

    bindings = {"FRONTIER_MODEL": load_json(args.frontier_binding), "LS": load_json(args.ls_binding)}
    reports = {"FRONTIER_MODEL": load_json(args.frontier_report), "LS": load_json(args.ls_report)}
    seals = {"FRONTIER_MODEL": load_json(args.frontier_seal), "LS": load_json(args.ls_seal)}
    write_json(
        args.out,
        score(case, bindings, reports, seals, load_json(args.adjudication), args.repo_root),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
