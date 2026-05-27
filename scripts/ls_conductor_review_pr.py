from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MODULES = ROOT / "python" / "modules"
PYTHON_ROOT = ROOT / "python"
for candidate in (str(SCRIPTS), str(MODULES), str(PYTHON_ROOT)):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from run_pr_review_trail_artifact import build_pr_review_artifact  # noqa: E402
from run_pr_role_market_demo import build_pr_role_market_payload  # noqa: E402


CONDUCTOR_VERSION = "v0.1"
CLAIM_BOUNDARY = (
    "Conductor wrapper over LS PR-review route artifacts; "
    "not a formal proof of best answer or global model ranking."
)


def _build_evidence(signals: list[dict[str, Any]], files: list[str]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    seen: set[str] = set()
    for signal in signals:
        code = str(signal.get("code", ""))
        msg = str(signal.get("message", ""))
        if code and msg and code not in seen:
            seen.add(code)
            evidence.append({
                "claim": msg,
                "source": "diff",
                "status": "signal",
                "signal_code": code,
            })
    has_tests = any("test" in f.lower() for f in files)
    code_files = [f for f in files if f.endswith((".py", ".js", ".ts", ".rs", ".go", ".java"))]
    if code_files and not has_tests and "missing_tests" not in seen:
        evidence.append({
            "claim": "Code files changed without an obvious test file in the same diff.",
            "source": "diff",
            "status": "signal",
            "signal_code": "missing_tests",
        })
    return evidence


def build_conductor_payload(
    *,
    repo: Path = ROOT,
    base: str = "HEAD~1",
    head: str = "HEAD",
    diff_file: Path | None = None,
    policy: str = "cooperative_pr_review",
    store_path: Path | None = None,
    role_outputs: list[dict[str, Any]] | None = None,
    max_diff_chars: int = 12000,
) -> dict[str, Any]:
    store = store_path or Path(tempfile.mkdtemp()) / "routes.json"
    t_start = time.perf_counter()

    source_artifact = build_pr_review_artifact(
        repo=repo,
        base=base,
        head=head,
        diff_file=diff_file,
        store_path=store,
        max_diff_chars=max_diff_chars,
    )
    role_market = build_pr_role_market_payload(
        repo=repo,
        base=base,
        head=head,
        diff_file=diff_file,
        store_path=store,
        max_diff_chars=max_diff_chars,
        role_outputs=role_outputs,
    )
    latency_ms = round((time.perf_counter() - t_start) * 1000)

    baseline_quality = role_market.get("baseline", {}).get("quality", {})
    cooperative_quality = role_market.get("cooperative", {}).get("quality", {})

    final_answer = str(source_artifact.get("human_summary") or "")
    selected_route = source_artifact.get("selected_route", {})
    cooperative_route = role_market.get("cooperative", {}).get("route", "")
    route_id = str(cooperative_route or selected_route.get("route_key", ""))
    route_score = float(role_market.get("cooperative", {}).get("reward", 0.0))
    baseline_score = float(role_market.get("baseline", {}).get("reward", 0.0))

    files = source_artifact.get("files", [])
    signals = source_artifact.get("signals", [])
    evidence = _build_evidence(signals, files)

    return {
        "artifact_type": "ls.conductor.review_pr.v0.1",
        "conductor_version": CONDUCTOR_VERSION,
        "task_type": "pr_review",
        "policy": policy,
        "final_answer": final_answer,
        "route_id": route_id,
        "route_score": _round(route_score),
        "confidence": _round(float(cooperative_quality.get("overall", 0.0))),
        "route_won_vs_single": bool(route_score > baseline_score),
        "evidence": evidence,
        "disagreements": [],
        "signals": signals,
        "decision": str(source_artifact.get("decision", "")),
        "cost_usd": None,
        "latency_ms": latency_ms,
        "artifact_path": None,
        "source_artifact": _compact_artifact(source_artifact),
        "role_market": _compact_role_market(role_market),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _round(value: float) -> float:
    return round(float(value), 4)


def _compact_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": artifact.get("artifact_type"),
        "decision": artifact.get("decision"),
        "signals": artifact.get("signals"),
        "quality": artifact.get("quality"),
        "route_reward": artifact.get("route_reward"),
        "file_count": len(artifact.get("files", [])),
        "diff_truncated": artifact.get("diff_truncated"),
    }


def _compact_role_market(role_market: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": role_market.get("artifact_type"),
        "live_model_calls": role_market.get("live_model_calls"),
        "baseline_route": role_market.get("baseline", {}).get("route"),
        "cooperative_route": role_market.get("cooperative", {}).get("route"),
        "baseline_reward": role_market.get("baseline", {}).get("reward"),
        "cooperative_reward": role_market.get("cooperative", {}).get("reward"),
        "synergy_reward_lift": role_market.get("synergy", {}).get("reward_lift"),
        "best_actor": role_market.get("best_actor_contributor"),
    }


def _print_text(payload: dict[str, Any]) -> None:
    print("LS Conductor PR Review")
    print(f"Policy: {payload['policy']}")
    print(f"Decision: {payload['decision']}")
    print(f"Route: {payload['route_id']}")
    print(f"Route won vs single: {payload['route_won_vs_single']}")
    print(f"Confidence: {payload['confidence']:.4f}")
    print(f"Summary: {payload['final_answer'][:200]}")
    print(f"Claim boundary: {payload['claim_boundary']}")


def _resolve_diff_file(args: argparse.Namespace) -> Path | None:
    if args.diff_file:
        return Path(args.diff_file)
    return None


def _resolve_role_outputs(args: argparse.Namespace) -> list[dict[str, Any]] | None:
    if not args.role_outputs:
        return None
    ro_path = Path(args.role_outputs)
    if not ro_path.exists():
        return None
    raw = json.loads(ro_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and "role_outputs" in raw:
        return list(raw["role_outputs"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="LS Conductor PR Review CLI")
    parser.add_argument("--repo", default=str(ROOT), help="Repository path (default: repo root)")
    parser.add_argument("--base", default="HEAD~1", help="Base git revision")
    parser.add_argument("--head", default="HEAD", help="Head git revision")
    parser.add_argument("--diff-file", default=None, help="Optional saved diff file path")
    parser.add_argument("--policy", default="cooperative_pr_review", help="Route policy")
    parser.add_argument("--store-path", default=None, help="Optional route stats path")
    parser.add_argument("--role-outputs", default=None, help="Optional role outputs JSON path")
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    parser.add_argument("--max-diff-chars", type=int, default=12000, help="Max diff excerpt chars")
    parser.add_argument("--json", action="store_true", help="Print full Conductor JSON")
    args = parser.parse_args()

    payload = build_conductor_payload(
        repo=Path(args.repo),
        base=args.base,
        head=args.head,
        diff_file=_resolve_diff_file(args),
        policy=args.policy,
        store_path=Path(args.store_path) if args.store_path else None,
        role_outputs=_resolve_role_outputs(args),
        max_diff_chars=args.max_diff_chars,
    )
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        payload["artifact_path"] = str(out_path.resolve())
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        _print_text(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
