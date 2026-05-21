from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from run_pr_role_market_demo import build_pr_role_market_payload, _load_role_outputs  # noqa: E402


def _run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result.stdout


def _commit_ranges(repo: Path, *, head: str, last: int) -> list[dict[str, str]]:
    commits = [line.strip() for line in _run_git(["rev-list", "--first-parent", f"--max-count={last}", head], repo).splitlines() if line.strip()]
    ranges: list[dict[str, str]] = []
    for commit in commits:
        parts = _run_git(["rev-list", "--parents", "-n", "1", commit], repo).split()
        if len(parts) < 2:
            continue
        subject = _run_git(["log", "-1", "--format=%s", commit], repo).strip()
        ranges.append(
            {
                "base": parts[1],
                "head": commit,
                "commit": commit,
                "short_commit": commit[:8],
                "subject": subject,
            }
        )
    return ranges


def _signal_codes(source: dict[str, Any]) -> list[str]:
    return [str(signal.get("code")) for signal in source.get("signals") or []]


def _row_from_payload(commit_range: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    source = payload["source_artifact"]
    best_role = payload["best_role_contributor"]
    best_actor = payload["best_actor_contributor"]
    return {
        "status": "ok",
        "commit": commit_range["commit"],
        "short_commit": commit_range["short_commit"],
        "subject": commit_range["subject"],
        "diff_source": source["diff_source"],
        "files_changed": len(source.get("files") or []),
        "decision": source["decision"],
        "signals": _signal_codes(source),
        "baseline_reward": payload["baseline"]["reward"],
        "cooperative_reward": payload["cooperative"]["reward"],
        "reward_lift": payload["synergy"]["reward_lift"],
        "quality_lift": payload["synergy"]["quality_lift"],
        "best_role": best_role["role"],
        "best_role_score": best_role["score"],
        "best_actor_id": best_actor["actor_id"],
        "best_actor_model": best_actor["model_name"],
        "attached_role_outputs": payload["attached_role_outputs"],
    }


def _error_row(commit_range: dict[str, str], error: Exception) -> dict[str, Any]:
    return {
        "status": "error",
        "commit": commit_range["commit"],
        "short_commit": commit_range["short_commit"],
        "subject": commit_range["subject"],
        "error": str(error),
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok_rows = [row for row in rows if row.get("status") == "ok"]
    role_counts = Counter(row["best_role"] for row in ok_rows)
    actor_counts = Counter(row["best_actor_id"] for row in ok_rows)

    def avg(key: str) -> float:
        if not ok_rows:
            return 0.0
        return round(sum(float(row[key]) for row in ok_rows) / len(ok_rows), 4)

    return {
        "requested": len(rows),
        "analyzed": len(ok_rows),
        "errors": len(rows) - len(ok_rows),
        "positive_reward_lift": sum(1 for row in ok_rows if float(row["reward_lift"]) > 0),
        "avg_baseline_reward": avg("baseline_reward"),
        "avg_cooperative_reward": avg("cooperative_reward"),
        "avg_reward_lift": avg("reward_lift"),
        "avg_quality_lift": avg("quality_lift"),
        "top_role": role_counts.most_common(1)[0][0] if role_counts else "n/a",
        "top_role_count": role_counts.most_common(1)[0][1] if role_counts else 0,
        "top_actor": actor_counts.most_common(1)[0][0] if actor_counts else "n/a",
        "top_actor_count": actor_counts.most_common(1)[0][1] if actor_counts else 0,
        "role_counts": dict(role_counts),
        "actor_counts": dict(actor_counts),
    }


def build_batch_payload(
    *,
    repo: Path,
    head: str,
    last: int,
    role_outputs: list[dict[str, Any]],
    max_diff_chars: int,
) -> dict[str, Any]:
    ranges = _commit_ranges(repo, head=head, last=last)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="ls-pr-role-market-batch-") as tmp:
        tmp_path = Path(tmp)
        for commit_range in ranges:
            try:
                payload = build_pr_role_market_payload(
                    repo=repo,
                    base=commit_range["base"],
                    head=commit_range["head"],
                    diff_file=None,
                    store_path=tmp_path / f"routes-{commit_range['short_commit']}.json",
                    max_diff_chars=max_diff_chars,
                    role_outputs=role_outputs,
                )
                rows.append(_row_from_payload(commit_range, payload))
            except Exception as exc:
                rows.append(_error_row(commit_range, exc))
    return {
        "artifact_type": "ls.pr_role_market_batch.v0.1",
        "repo": str(repo),
        "head": head,
        "last": last,
        "attached_role_outputs": bool(role_outputs),
        "summary": summarize_rows(rows),
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# LS PR Role Market Batch Report",
        "",
        f"- Repo: `{payload['repo']}`",
        f"- Head: `{payload['head']}`",
        f"- Requested commits: `{payload['last']}`",
        f"- Analyzed: `{summary['analyzed']}`",
        f"- Errors: `{summary['errors']}`",
        f"- Attached role outputs: `{str(payload['attached_role_outputs']).lower()}`",
        f"- Average baseline reward: `{summary['avg_baseline_reward']}`",
        f"- Average cooperative reward: `{summary['avg_cooperative_reward']}`",
        f"- Average reward lift: `+{summary['avg_reward_lift']}`",
        f"- Average quality lift: `+{summary['avg_quality_lift']}`",
        f"- Positive reward lift: `{summary['positive_reward_lift']}/{summary['analyzed']}`",
        f"- Top role: `{summary['top_role']}` ({summary['top_role_count']})",
        f"- Top actor: `{summary['top_actor']}` ({summary['top_actor_count']})",
        "",
        "## Runs",
        "",
        "| Commit | Decision | Signals | Baseline | Cooperative | Lift | Best role | Best actor/model |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        if row.get("status") != "ok":
            lines.append(
                f"| `{row['short_commit']}` | error | `{row.get('error', '')}` |  |  |  |  |  |"
            )
            continue
        signals = ", ".join(row["signals"]) or "none"
        lines.append(
            "| `{short_commit}` | `{decision}` | `{signals}` | {baseline_reward} | {cooperative_reward} | "
            "+{reward_lift} | `{best_role}` | `{best_actor_id}` / `{best_actor_model}` |".format(
                **{**row, "signals": signals}
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This is a contextual benchmark over repository diffs, not a global ranking of people or models.",
            "The useful signal is whether cooperative routes repeatedly improve reward and which role tends to add verified value.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Run LS PR Role Market over recent git history.")
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository path.")
    parser.add_argument("--head", default="HEAD", help="Head revision to walk from.")
    parser.add_argument("--last", type=int, default=10, help="Number of first-parent commits to analyze.")
    parser.add_argument("--role-outputs", type=Path, default=None, help="Attach JSON role outputs to each run.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON batch artifact.")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Write Markdown batch report.")
    parser.add_argument("--max-diff-chars", type=int, default=6000, help="Max diff excerpt used by each source artifact.")
    parser.add_argument("--json", action="store_true", help="Print full JSON payload.")
    args = parser.parse_args()

    repo = args.repo.resolve()
    role_outputs = _load_role_outputs(args.role_outputs)
    payload = build_batch_payload(
        repo=repo,
        head=args.head,
        last=args.last,
        role_outputs=role_outputs,
        max_diff_chars=args.max_diff_chars,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(payload), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        summary = payload["summary"]
        print("LS PR Role Market batch")
        print(f"Analyzed: {summary['analyzed']}/{payload['last']}")
        print(f"Errors: {summary['errors']}")
        print(f"Attached role outputs: {str(payload['attached_role_outputs']).lower()}")
        print(f"Average baseline reward: {summary['avg_baseline_reward']:.4f}")
        print(f"Average cooperative reward: {summary['avg_cooperative_reward']:.4f}")
        print(f"Average reward lift: +{summary['avg_reward_lift']:.4f}")
        print(f"Positive reward lift: {summary['positive_reward_lift']}/{summary['analyzed']}")
        print(f"Top role: {summary['top_role']} ({summary['top_role_count']})")
        print(f"Top actor: {summary['top_actor']} ({summary['top_actor_count']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
