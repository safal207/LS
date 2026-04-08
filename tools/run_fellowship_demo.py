from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "council-ledger"
SUMMARY_DIR = ROOT / "artifacts" / "fellowship-demo"
SUMMARY_PATH = SUMMARY_DIR / "demo-summary.json"

for candidate in (ROOT / "python", ROOT / "python" / "modules", ROOT / "tools"):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from ls.agent_shell.cli import CouncilLLMMode, build_council_agent  # noqa: E402
from build_fellowship_dataset import OUTPUT_LEDGER_DIR, build_dataset  # noqa: E402
from export_council_scorecard import export_scorecard  # noqa: E402


def print_plain_safe(text: str) -> None:
    output = str(text or "")
    try:
        print(output)
    except UnicodeEncodeError:
        stream = getattr(sys.stdout, "buffer", None)
        safe_bytes = (output + "\n").encode("cp1252", errors="replace")
        if stream is not None:
            stream.write(safe_bytes)
            stream.flush()
        else:
            sys.stdout.write(safe_bytes.decode("cp1252", errors="replace"))


def build_demo_summary(
    *,
    prompt: str,
    llm_mode: str,
    result: dict,
    artifact_path: Path | None,
    dataset_manifest: dict | None,
    scorecard_payload: dict | None,
) -> dict:
    ledger = result.get("council_contribution_ledger") or {}
    outcome = ledger.get("outcome") or {}
    attribution = ledger.get("attribution") or {}
    final_decision = ledger.get("final_decision") or {}

    return {
        "prompt": prompt,
        "llm_mode": llm_mode,
        "cycle_id": result.get("cycle_id", "unknown"),
        "final_output": str(result.get("final_output", "") or ""),
        "ledger_artifact": str(artifact_path) if artifact_path else None,
        "selected_route": str(final_decision.get("selected_route", "unknown")),
        "best_contributor_model_id": str(attribution.get("best_contributor_model_id", "n/a")),
        "best_contributor_score": float(attribution.get("best_contributor_score", 0.0) or 0.0),
        "receiver_resonance_score": float(
            outcome.get("receiver_resonance_score", outcome.get("operator_feedback_score", 0.0)) or 0.0
        ),
        "network_improvement": float(outcome.get("network_improvement", 0.0) or 0.0),
        "success": bool(outcome.get("success")),
        "dataset_summary": dataset_manifest.get("summary") if dataset_manifest else None,
        "scorecard_summary": scorecard_payload.get("summary") if scorecard_payload else None,
        "scorecard_source": scorecard_payload.get("source") if scorecard_payload else None,
    }


def run_demo(
    *,
    prompt: str,
    llm_mode: CouncilLLMMode = CouncilLLMMode.AUTO,
    artifact_dir: Path = ARTIFACT_DIR,
    refresh_dataset: bool = True,
    refresh_scorecard: bool = True,
) -> dict:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    agent = build_council_agent(orientation="fellowship-demo", llm_mode=llm_mode)
    agent._council_ledger_dir = artifact_dir
    result = agent.process_text(prompt)

    artifact_path_value = result.get("council_contribution_ledger_artifact")
    artifact_path = Path(artifact_path_value) if artifact_path_value else None

    dataset_manifest = build_dataset() if refresh_dataset else None
    scorecard_payload = (
        export_scorecard(OUTPUT_LEDGER_DIR, ROOT / "ghostgpt-ls-landing" / "src" / "data" / "councilScorecard.json")
        if refresh_scorecard
        else None
    )

    summary = build_demo_summary(
        prompt=prompt,
        llm_mode=llm_mode.value,
        result=result,
        artifact_path=artifact_path,
        dataset_manifest=dataset_manifest,
        scorecard_payload=scorecard_payload,
    )
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fellowship demo path in one reproducible step.")
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Run a council coordination cycle for this operator request",
        help="Prompt to feed into the council cycle.",
    )
    parser.add_argument(
        "--llm-mode",
        choices=[mode.value for mode in CouncilLLMMode],
        default=CouncilLLMMode.AUTO.value,
        help="Choose whether to use a local LLM or dry-run mode.",
    )
    parser.add_argument("--artifact-dir", type=Path, default=ARTIFACT_DIR)
    parser.add_argument("--no-dataset-refresh", action="store_true")
    parser.add_argument("--no-scorecard-refresh", action="store_true")
    args = parser.parse_args()

    summary = run_demo(
        prompt=args.prompt,
        llm_mode=CouncilLLMMode(args.llm_mode),
        artifact_dir=args.artifact_dir,
        refresh_dataset=not args.no_dataset_refresh,
        refresh_scorecard=not args.no_scorecard_refresh,
    )
    print_plain_safe(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
