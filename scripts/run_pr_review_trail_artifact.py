from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "python" / "modules"
if str(MODULES) not in sys.path:
    sys.path.insert(0, str(MODULES))

from graph.path_selector import PathSelector  # noqa: E402
from graph.route_stats import RouteStatsStore  # noqa: E402
from graph.trail_updater import PathExecutionRecord, TrailUpdater, compute_route_reward  # noqa: E402


@dataclass
class ReviewSignal:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _read_diff(*, repo: Path, base: str, head: str, diff_file: Path | None) -> tuple[str, str, list[str], str]:
    if diff_file is not None:
        diff_text = diff_file.read_text(encoding="utf-8")
        files = _files_from_diff(diff_text)
        return f"file:{diff_file}", "(diff-file)", files, diff_text

    revision_range = f"{base}..{head}"
    stat = _run_git(["diff", "--stat", revision_range], repo).strip()
    files = [line.strip() for line in _run_git(["diff", "--name-only", revision_range], repo).splitlines() if line.strip()]
    diff_text = _run_git(["diff", "--unified=80", revision_range], repo)
    return revision_range, stat, files, diff_text


def _files_from_diff(diff_text: str) -> list[str]:
    files: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            files.append(line.removeprefix("+++ b/"))
    return sorted(set(files))


def _classify_files(files: list[str]) -> dict[str, Any]:
    docs = [path for path in files if path.lower().endswith((".md", ".txt", ".rst"))]
    tests = [path for path in files if "test" in path.lower() or path.lower().endswith(("_test.py", ".test.ts", ".spec.ts"))]
    code = [path for path in files if path not in docs]
    scripts = [path for path in files if path.startswith("scripts/") or path.startswith("scripts\\")]
    return {
        "count": len(files),
        "docs": docs,
        "tests": tests,
        "code": code,
        "scripts": scripts,
    }


def _detect_signals(diff_text: str, files: list[str]) -> list[ReviewSignal]:
    lower = diff_text.lower()
    signals: list[ReviewSignal] = []
    if not diff_text.strip():
        signals.append(ReviewSignal("empty_diff", "hold", "No diff was found, so the route cannot review concrete evidence."))
        return signals

    risky_tokens = [
        ("force_push", "git push --force"),
        ("recursive_delete", "rm -rf"),
        ("python_eval", "eval("),
        ("python_exec", "exec("),
        ("shell_true", "shell=true"),
        ("secret_literal", "password="),
        ("token_literal", "api_key"),
    ]
    for code, token in risky_tokens:
        if token in lower:
            signals.append(ReviewSignal(code, "human_review", f"Diff contains `{token}`, which needs explicit review."))

    file_info = _classify_files(files)
    if file_info["code"] and not file_info["tests"]:
        signals.append(
            ReviewSignal(
                "missing_tests",
                "medium",
                "Code or script files changed without an obvious test file in the same diff.",
            )
        )
    if len(diff_text) > 20000:
        signals.append(ReviewSignal("large_diff", "medium", "Diff is large enough that review should be split into smaller passes."))
    if file_info["docs"] and not file_info["code"]:
        signals.append(ReviewSignal("docs_only", "low", "Diff appears docs-only; evidence burden is lower but wording should still be checked."))
    return signals


def _score_quality(signals: list[ReviewSignal], files: list[str], diff_text: str) -> dict[str, float]:
    high_or_hold = sum(1 for signal in signals if signal.severity in {"hold", "human_review"})
    medium = sum(1 for signal in signals if signal.severity == "medium")
    docs_only = any(signal.code == "docs_only" for signal in signals)
    has_diff = bool(diff_text.strip())
    has_files = bool(files)

    overall = 0.9
    overall -= 0.18 * high_or_hold
    overall -= 0.08 * medium
    if not has_diff or not has_files:
        overall = 0.35
    if docs_only:
        overall += 0.03
    overall = max(0.0, min(0.98, overall))

    hallucination_risk = 0.08 + (0.13 * high_or_hold) + (0.05 * medium)
    if not has_diff:
        hallucination_risk = 0.45
    hallucination_risk = max(0.0, min(0.8, hallucination_risk))

    return {
        "overall": round(overall, 4),
        "relevance": round(0.92 if has_diff else 0.4, 4),
        "thread_relevance": round(0.9 if has_files else 0.4, 4),
        "coherence": round(max(0.4, overall - 0.02), 4),
        "goal_alignment_score": round(max(0.35, overall - 0.04), 4),
        "hallucination_risk": round(hallucination_risk, 4),
    }


def _decision_from_signals(signals: list[ReviewSignal]) -> str:
    severities = {signal.severity for signal in signals}
    if "hold" in severities:
        return "hold_until_diff"
    if "human_review" in severities:
        return "human_review"
    if "medium" in severities:
        return "review_with_conditions"
    return "approve_route"


def build_pr_review_artifact(
    *,
    repo: Path,
    base: str,
    head: str,
    diff_file: Path | None,
    store_path: Path,
    max_diff_chars: int,
) -> dict[str, Any]:
    source, stat, files, diff_text = _read_diff(repo=repo, base=base, head=head, diff_file=diff_file)
    signals = _detect_signals(diff_text, files)
    quality = _score_quality(signals, files, diff_text)

    store = RouteStatsStore(store_path)
    selector = PathSelector(store, exploration_rate=0.0)
    route_decision = selector.choose_route(
        graph_mode="pr_review",
        available_backends=["local", "gonka", "mimo"],
        default_backend="local",
        strategy_bias="cooperative_reasoning",
    )
    latency_ms = min(30000.0, 2500.0 + (len(diff_text) / 12.0))
    record = PathExecutionRecord(
        route_key=route_decision.route_key,
        question_text=f"Review git diff {source} for risky changes, missing tests, and evidence quality.",
        graph_mode="pr_review",
        selected_backend=route_decision.selected_backend or "cooperative",
        quality=quality,
        latency_ms=latency_ms,
    )
    route_stats, reward = TrailUpdater(store).update(record)

    file_info = _classify_files(files)
    final_decision = _decision_from_signals(signals)
    return {
        "artifact_type": "ls.pr_review_trail.v0.1",
        "created_at": _utc_now(),
        "repo": str(repo),
        "diff_source": source,
        "stat": stat,
        "files": files,
        "file_summary": file_info,
        "selected_route": route_decision.to_dict(),
        "review_flow": [
            {"role": "draft_reviewer", "task": "Summarize the diff surface and likely intent."},
            {"role": "risk_critic", "task": "Search for risky state changes, missing tests, and unsafe operations."},
            {"role": "evidence_verifier", "task": "Check whether the finding is grounded in diff evidence."},
            {"role": "final_reviewer", "task": "Emit a concise human-facing review decision."},
        ],
        "signals": [signal.to_dict() for signal in signals],
        "quality": quality,
        "route_reward": compute_route_reward(quality, latency_ms),
        "updated_route": route_stats.to_dict(),
        "decision": final_decision,
        "human_summary": _human_summary(final_decision, signals, files),
        "diff_excerpt": diff_text[:max_diff_chars],
        "diff_truncated": len(diff_text) > max_diff_chars,
    }


def _human_summary(decision: str, signals: list[ReviewSignal], files: list[str]) -> str:
    if decision == "hold_until_diff":
        return "LS did not find a concrete diff to review. Provide a PR range or diff file before continuing."
    if decision == "human_review":
        return "LS found a high-risk signal. Human review is required before treating this route as reusable."
    if decision == "review_with_conditions":
        messages = "; ".join(signal.message for signal in signals if signal.severity == "medium")
        return f"LS can continue, but the review should address: {messages}"
    return f"LS found a reviewable diff across {len(files)} file(s) and marked the cooperative route as reusable."


def render_markdown(artifact: dict[str, Any]) -> str:
    signals = artifact["signals"] or [{"code": "none", "severity": "low", "message": "No review signals."}]
    lines = [
        "# LS PR Review Trail Artifact",
        "",
        f"- Diff source: `{artifact['diff_source']}`",
        f"- Decision: `{artifact['decision']}`",
        f"- Selected route: `{artifact['selected_route']['route_key']}`",
        f"- Route reward: `{artifact['route_reward']}`",
        f"- Files changed: `{len(artifact['files'])}`",
        "",
        "## Human Summary",
        "",
        artifact["human_summary"],
        "",
        "## Signals",
        "",
    ]
    for signal in signals:
        lines.append(f"- `{signal['severity']}` `{signal['code']}`: {signal['message']}")
    lines.extend(
        [
            "",
            "## Review Flow",
            "",
        ]
    )
    for step in artifact["review_flow"]:
        lines.append(f"- `{step['role']}`: {step['task']}")
    if artifact["stat"]:
        lines.extend(["", "## Git Stat", "", "```text", artifact["stat"], "```"])
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build an LS PR-review trail artifact from a real git diff.")
    parser.add_argument("--repo", type=Path, default=ROOT, help="Repository path.")
    parser.add_argument("--base", default="HEAD~1", help="Base revision. Default reviews the latest commit.")
    parser.add_argument("--head", default="HEAD", help="Head revision.")
    parser.add_argument("--diff-file", type=Path, default=None, help="Read a saved diff instead of running git diff.")
    parser.add_argument("--store-path", type=Path, default=None, help="Route stats JSON path.")
    parser.add_argument("--output", type=Path, default=None, help="Write JSON artifact.")
    parser.add_argument("--markdown-output", type=Path, default=None, help="Write Markdown artifact.")
    parser.add_argument("--max-diff-chars", type=int, default=12000, help="Max diff excerpt embedded in JSON.")
    parser.add_argument("--json", action="store_true", help="Print full JSON artifact.")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if args.store_path is None:
        with tempfile.TemporaryDirectory(prefix="ls-pr-review-artifact-") as tmp:
            artifact = build_pr_review_artifact(
                repo=repo,
                base=args.base,
                head=args.head,
                diff_file=args.diff_file,
                store_path=Path(tmp) / "routes.json",
                max_diff_chars=args.max_diff_chars,
            )
    else:
        artifact = build_pr_review_artifact(
            repo=repo,
            base=args.base,
            head=args.head,
            diff_file=args.diff_file,
            store_path=args.store_path,
            max_diff_chars=args.max_diff_chars,
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(render_markdown(artifact), encoding="utf-8")

    if args.json:
        print(json.dumps(artifact, ensure_ascii=False, indent=2))
    else:
        print("LS PR Review Trail artifact")
        print(f"Diff source: {artifact['diff_source']}")
        print(f"Decision: {artifact['decision']}")
        print(f"Selected route: {artifact['selected_route']['route_key']}")
        print(f"Route reward: {artifact['route_reward']:.4f}")
        print(f"Files changed: {len(artifact['files'])}")
        print(f"Summary: {artifact['human_summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
